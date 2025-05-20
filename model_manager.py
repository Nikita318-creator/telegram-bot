import os
import asyncio
import logging
import time
from enum import Enum
from typing import Dict, Optional
import httpx
from telegram import Update

# Кастомный обработчик логов для отправки в Telegram
class TelegramLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.update = None

    def set_update(self, update: Optional[Update]):
        self.update = update

    def emit(self, record):
        if self.update and os.getenv("DEBUG_TO_USER", "0") == "1":
            log_message = self.format(record)
            # Отправляем лог пользователю асинхронно
            asyncio.create_task(self.update.message.reply_text(log_message))

# Настройка логирования
logger = logging.getLogger()
logger.setLevel(logging.DEBUG if os.getenv("DEBUG_TO_USER", "0") == "1" else logging.INFO)
telegram_handler = TelegramLogHandler()
telegram_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(telegram_handler)

# Перечисление моделей (порядок важен для перебора)
class AIModelType(Enum):
    GEMINI_15_PRO = "gemini_15_pro"
    GEMINI_2_FLASH = "gemini_2_flash"
    GEMINI_2_FLASH_LIGHT = "gemini_2_flash_light"
    GEMINI_15_FLASH_B = "gemini_15_flash_b"
    GEMINI = "gemini"
    MISTRAL = "mistral"

    @property
    def url(self) -> str:
        return {
            AIModelType.MISTRAL: "https://api.mistral.ai/v1/chat/completions",
            AIModelType.GEMINI: "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent",
            AIModelType.GEMINI_15_FLASH_B: "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash-8b:generateContent",
            AIModelType.GEMINI_15_PRO: "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro:generateContent",
            AIModelType.GEMINI_2_FLASH: "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent",
            AIModelType.GEMINI_2_FLASH_LIGHT: "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash-lite:generateContent",
        }[self]

    @property
    def model(self) -> str:
        return {
            AIModelType.MISTRAL: "mistral-tiny",
            AIModelType.GEMINI: "gemini-1.5-flash",
            AIModelType.GEMINI_15_FLASH_B: "gemini-1.5-flash-8b",
            AIModelType.GEMINI_15_PRO: "gemini-1.5-pro",
            AIModelType.GEMINI_2_FLASH: "gemini-2.0-flash",
            AIModelType.GEMINI_2_FLASH_LIGHT: "gemini-2.0-flash-lite",
        }[self]

# Класс для управления моделями
class AIModelManager:
    def __init__(self):
        self.current_model = AIModelType.GEMINI_15_PRO
        self.model_limits = {model: True for model in AIModelType}
        self.api_keys = {
            model: os.getenv("GEMINI_API_KEY" if "GEMINI" in model.name else "MISTRAL_API_KEY", "")
            for model in AIModelType
        }
        self.model_reset_delays = {model: 60.0 for model in AIModelType}
        self.model_reset_tasks = {}
        self.current_update = None  # Храним текущий update для логов

    def get_api_key(self, model: AIModelType) -> str:
        return self.api_keys.get(model, "")

    def get_headers(self, model: AIModelType) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if model == AIModelType.MISTRAL:
            headers["Authorization"] = f"Bearer {self.get_api_key(model)}"
        else:
            headers["x-goog-api-key"] = self.get_api_key(model)
        return headers

    def get_request_body(self, model: AIModelType, user_message: str) -> Dict:
        if model == AIModelType.MISTRAL:
            return {
                "model": model.model,
                "messages": [{"role": "user", "content": user_message}],
                "temperature": 0.7,
                "max_tokens": 1024
            }
        return {
            "contents": [{"parts": [{"text": user_message}], "role": "user"}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
        }

    async def reset_model_limit(self, model: AIModelType):
        delay = self.model_reset_delays.get(model, 60.0)
        start_time = time.time()
        await asyncio.sleep(delay)
        self.model_limits[model] = True
        elapsed = time.time() - start_time
        logging.info(f"Лимит для модели {model.name} сброшен через {elapsed:.2f} секунд")
        self.model_reset_tasks.pop(model, None)

    async def reset_all_models(self):
        start_time = time.time()
        await asyncio.sleep(60.0)
        for model in self.model_limits:
            self.model_limits[model] = True
            self.model_reset_tasks.pop(model, None)
        elapsed = time.time() - start_time
        logging.info(f"Лимиты всех моделей сброшены через {elapsed:.2f} секунд")
        self.model_reset_tasks.pop("reset_all", None)

    def get_next_gemini_model(self):
        """Возвращает первую доступную Gemini-модель или None"""
        gemini_models = [m for m in AIModelType if m != AIModelType.MISTRAL]
        for model in gemini_models:
            if self.model_limits[model]:
                return model
        return None

    async def query_api_async(self, user_message: str, update: Optional[Update] = None) -> str:
        # Сохраняем update для логов
        self.current_update = update
        telegram_handler.set_update(update)

        # Логируем текущий статус моделей
        logging.debug(f"Статус моделей перед запросом: { {m.name: self.model_limits[m] for m in AIModelType} }")

        # Если текущая модель — Mistral, проверяем доступность Gemini
        if self.current_model == AIModelType.MISTRAL:
            gemini_model = self.get_next_gemini_model()
            if gemini_model:
                self.current_model = gemini_model
                logging.info(f"Переключились обратно на модель {self.current_model.name}")
                switch_message = f"Переключились на модель: {self.current_model.name}\n"
            else:
                switch_message = ""
        else:
            switch_message = ""

        url = self.current_model.url
        headers = self.get_headers(self.current_model)
        body = self.get_request_body(self.current_model, user_message)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()

            if self.current_model == AIModelType.MISTRAL:
                return switch_message + data.get("choices", [{}])[0].get("message", {}).get("content", "Нет ответа от Mistral")
            return switch_message + data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "Нет ответа от Gemini")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logging.warning(f"Модель {self.current_model.name} исчерпала лимиты")
                self.model_limits[self.current_model] = False
                if self.current_model not in self.model_reset_tasks:
                    self.model_reset_tasks[self.current_model] = asyncio.create_task(self.reset_model_limit(self.current_model))

                # Пробуем следующую Gemini-модель
                next_model = self.get_next_gemini_model()
                if next_model:
                    self.current_model = next_model
                else:
                    self.current_model = AIModelType.MISTRAL
                    self.model_limits[AIModelType.MISTRAL] = True

                logging.info(f"Переключились на модель {self.current_model.name}")
                switch_message = f"Переключились на модель: {self.current_model.name}\n"
                return switch_message + await self.query_api_async(user_message, update)

            elif e.response.status_code == 400:
                logging.warning(f"Ошибка 400 для модели {self.current_model.name}, переключаемся на Mistral")
                for model in self.model_limits:
                    self.model_limits[model] = False
                self.current_model = AIModelType.MISTRAL
                self.model_limits[AIModelType.MISTRAL] = True
                if "reset_all" not in self.model_reset_tasks:
                    self.model_reset_tasks["reset_all"] = asyncio.create_task(self.reset_all_models())
                switch_message = f"Переключились на модель: {self.current_model.name}\n"
                return switch_message + await self.query_api_async(user_message, update)

            return switch_message + f"Ошибка API: {str(e)}"

        except Exception as e:
            return switch_message + f"Ошибка при запросе к API: {str(e)}"

        finally:
            # Очищаем update после запроса
            self.current_update = None
            telegram_handler.set_update(None)
