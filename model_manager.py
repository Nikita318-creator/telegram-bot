import os
import requests
import asyncio
import logging
from enum import Enum
from typing import Optional, Dict
import httpx

# Настройка логирования
logging.basicConfig(filename='bot_analytics.log', level=logging.INFO)

# Перечисление моделей
class AIModelType(Enum):
    MISTRAL = "mistral"
    GEMINI = "gemini"
    GEMINI_15_FLASH_B = "gemini_15_flash_b"
    GEMINI_15_PRO = "gemini_15_pro"
    GEMINI_2_FLASH = "gemini_2_flash"
    GEMINI_2_FLASH_LIGHT = "gemini_2_flash_light"

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

    def get_api_key(self, model: AIModelType) -> str:
        return self.api_keys.get(model, "")

    def get_headers(self, model: AIModelType) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if model == AIModelType.MISTRAL:
            headers["Authorization"] = f"Bearer {self.get_api_key(model)}"
        else:
            headers["x-goog-api-key"] = self.get_api_key(model)
        return headers

    def get_request_body(self, model: AIModelType, user_message: str, system_prompt: str = "") -> Dict:
        if model == AIModelType.MISTRAL:
            return {
                "model": model.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.7,
                "max_tokens": 1024
            }
        else:
            combined_prompt = user_message if not system_prompt else f"{system_prompt}\n\n{user_message}"
            return {
                "contents": [
                    {
                        "parts": [{"text": combined_prompt}],
                        "role": "user"
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1024
                }
            }

    async def reset_model_limit(self, model: AIModelType):
        delay = self.model_reset_delays.get(model, 60.0)
        await asyncio.sleep(delay)
        self.model_limits[model] = True
        logging.info(f"Лимит для модели {model.name} сброшен")

    async def reset_all_models(self):
        await asyncio.sleep(60.0)
        for model in self.model_limits:
            self.model_limits[model] = True
        logging.info("Лимиты всех моделей сброшены")

    def check_gemini_availability(self):
        for model in self.model_limits:
            if model != AIModelType.MISTRAL and self.model_limits[model]:
                return AIModelType.GEMINI_2_FLASH_LIGHT
        return None

    async def query_api_async(self, user_message: str, system_prompt: str = "") -> str:
        if self.current_model == AIModelType.MISTRAL:
            gemini_model = self.check_gemini_availability()
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
        body = self.get_request_body(self.current_model, user_message, system_prompt)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()

            if self.current_model == AIModelType.MISTRAL:
                return switch_message + data.get("choices", [{}])[0].get("message", {}).get("content", "Нет ответа от Mistral")
            else:
                return switch_message + data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "Нет ответа от Gemini")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logging.warning(f"Модель {self.current_model.name} исчерпала лимиты")
                self.model_limits[self.current_model] = False
                asyncio.create_task(self.reset_model_limit(self.current_model))

                self.current_model = next(
                    (model for model, available in self.model_limits.items() if available),
                    AIModelType.MISTRAL
                )
                logging.info(f"Переключились на модель {self.current_model.name}")
                switch_message = f"Переключились на модель: {self.current_model.name}\n"
                return switch_message + await self.query_api_async(user_message, system_prompt)

            elif e.response.status_code == 400:
                logging.warning(f"Ошибка 400 для модели {self.current_model.name}, переключаемся на Mistral")
                for model in self.model_limits:
                    self.model_limits[model] = False
                self.current_model = AIModelType.MISTRAL
                self.model_limits[AIModelType.MISTRAL] = True
                asyncio.create_task(self.reset_all_models())
                switch_message = f"Переключились на модель: {self.current_model.name}\n"
                return switch_message + await self.query_api_async(user_message, system_prompt)
            else:
                return switch_message + f"Ошибка API: {str(e)}"

        except Exception as e:
            return switch_message + f"Ошибка при запросе к API: {str(e)}"

