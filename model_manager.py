import os
import requests
import asyncio
from enum import Enum
from typing import Optional, Dict

# Перечисление моделей (без DeepSeek)
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
        self.current_model = AIModelType.GEMINI_2_FLASH_LIGHT
        self.model_limits = {
            AIModelType.MISTRAL: True,
            AIModelType.GEMINI: True,
            AIModelType.GEMINI_15_FLASH_B: True,
            AIModelType.GEMINI_15_PRO: True,
            AIModelType.GEMINI_2_FLASH: True,
            AIModelType.GEMINI_2_FLASH_LIGHT: True,
        }
        self.api_keys = {
            AIModelType.MISTRAL: os.getenv("MISTRAL_API_KEY", ""),
            AIModelType.GEMINI: os.getenv("GEMINI_API_KEY", ""),
            AIModelType.GEMINI_15_FLASH_B: os.getenv("GEMINI_API_KEY", ""),
            AIModelType.GEMINI_15_PRO: os.getenv("GEMINI_API_KEY", ""),
            AIModelType.GEMINI_2_FLASH: os.getenv("GEMINI_API_KEY", ""),
            AIModelType.GEMINI_2_FLASH_LIGHT: os.getenv("GEMINI_API_KEY", ""),
        }

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
                        "parts": [
                            {"text": combined_prompt}
                        ],
                        "role": "user"
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1024
                }
            }

    async def reset_model_limit(self, model: AIModelType, delay: float = 60.0):
        await asyncio.sleep(delay)
        self.model_limits[model] = True
        print(f"Лимит для модели {model.name} сброшен")

    def query_api_sync(self, user_message: str, system_prompt: str = "") -> Optional[str]:
        url = self.current_model.url
        headers = self.get_headers(self.current_model)
        body = self.get_request_body(self.current_model, user_message, system_prompt)

        try:
            resp = requests.post(url, headers=headers, json=body, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            if self.current_model == AIModelType.MISTRAL:
                return data.get("choices", [{}])[0].get("message", {}).get("content", "Нет ответа от Mistral")
            else:
                return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "Нет ответа от Gemini")

        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429:
                print(f"Модель {self.current_model.name} исчерпала лимиты")
                self.model_limits[self.current_model] = False
                asyncio.create_task(self.reset_model_limit(self.current_model))
                
                # Переключаемся на следующую доступную модель
                self.current_model = next(
                    (model for model, available in self.model_limits.items() if available),
                    AIModelType.MISTRAL
                )
                print(f"Переключились на модель {self.current_model.name}")
                return self.query_api_sync(user_message, system_prompt)
            
            elif resp.status_code == 400:
                try:
                    error_data = resp.json()
                    error_status = error_data.get("error", {}).get("status", "")
                    error_message = error_data.get("error", {}).get("message", "")
                    if error_status == "FAILED_PRECONDITION" and "User location is not supported" in error_message:
                        print("Регион не поддерживается, переключаемся на Mistral")
                        for model in self.model_limits:
                            if model != AIModelType.MISTRAL:
                                self.model_limits[model] = False
                        self.current_model = AIModelType.MISTRAL
                        return self.query_api_sync(user_message, system_prompt)
                except ValueError:
                    pass
                return f"Ошибка 400: {resp.text}"
            else:
                return f"Ошибка API: {str(e)}"
        except Exception as e:
            return f"Ошибка при запросе к API: {str(e)}"
