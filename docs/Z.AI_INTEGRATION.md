# 🔷 ИНТЕГРАЦИЯ Z.AI (GLM) - ОФИЦИАЛЬНАЯ БИБЛИОТЕКА

> Полная инструкция по использованию официальной библиотеки zhipuai для работы с GLM-4 и GLM-4.6V

---

## 📦 УСТАНОВКА

### Официальная библиотека Z.ai

```bash
pip install zhipuai>=2.1.5.20250131
```

**ВАЖНО:** 
- ✅ Используй **ТОЛЬКО** официальную библиотеку `zhipuai`
- ❌ НЕ используй `openai` для GLM
- ❌ НЕ используй прямые HTTP-запросы через `httpx` к GLM API
- ❌ НЕ используй `anthropic` или другие обёртки

---

## 🔑 ПОЛУЧЕНИЕ API КЛЮЧА

1. Зарегистрируйся на https://z.ai
2. Перейди в https://z.ai/manage-apikey/apikey-list
3. Создай новый API ключ
4. Добавь в `.env`:
   ```env
   GLM_API_KEY=your_api_key_here
   ```

---

## 🤖 ДОСТУПНЫЕ МОДЕЛИ

| Модель | Тип | Назначение | Особенности |
|--------|-----|-----------|-------------|
| `glm-4-6v` | Vision | Анализ изображений | Лучшее качество, новейшая версия |
| `glm-4v-flash` | Vision | Анализ изображений | Быстрая, экономичная |
| `glm-4-plus` | Text | Генерация текста | Высокое качество |
| `glm-4-air` | Text | Генерация текста | Баланс качества/скорости |
| `glm-4-flash` | Text | Генерация текста | Быстрая, экономичная |

---

## 📖 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### 1. Базовая инициализация

```python
from zhipuai import ZhipuAI

# Создание клиента
client = ZhipuAI(api_key="your_api_key_here")
```

---

### 2. Простая текстовая генерация (синхронная)

```python
from zhipuai import ZhipuAI

client = ZhipuAI(api_key="ваш_ключ")

# Генерация текста
response = client.chat.completions.create(
    model="glm-4-plus",
    messages=[
        {"role": "system", "content": "Ты эксперт по маркетингу"},
        {"role": "user", "content": "Придумай слоган для товара"}
    ],
    temperature=0.7,
    max_tokens=500
)

# Получение результата
result = response.choices[0].message.content
print(result)

# Информация о токенах
print(f"Использовано токенов: {response.usage.total_tokens}")
```

---

### 3. Асинхронная генерация (для aiogram)

**ВАЖНО:** Библиотека zhipuai - **синхронная**, но её можно использовать асинхронно через `asyncio.loop.run_in_executor()`:

```python
import asyncio
from zhipuai import ZhipuAI

client = ZhipuAI(api_key="ваш_ключ")

async def generate_async(prompt: str) -> str:
    """Асинхронная генерация текста."""
    loop = asyncio.get_event_loop()
    
    # Запускаем синхронный метод в executor
    response = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model="glm-4-plus",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
    )
    
    return response.choices[0].message.content

# Использование
async def main():
    result = await generate_async("Привет!")
    print(result)

asyncio.run(main())
```

---

### 4. Анализ одного изображения (Vision)

```python
import base64
from zhipuai import ZhipuAI

client = ZhipuAI(api_key="ваш_ключ")

# Читаем изображение
with open("photo.jpg", "rb") as f:
    image_data = f.read()

# Конвертируем в base64
image_base64 = base64.b64encode(image_data).decode("utf-8")

# Анализ изображения
response = client.chat.completions.create(
    model="glm-4-6v",  # Vision модель
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Опиши этот товар детально для создания карточки на маркетплейсе"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]
        }
    ],
    temperature=0.3
)

description = response.choices[0].message.content
print(description)
```

---

### 5. Анализ нескольких изображений

GLM-4.6V поддерживает анализ нескольких изображений в одном запросе (до 5):

```python
import base64
from zhipuai import ZhipuAI

client = ZhipuAI(api_key="ваш_ключ")

# Читаем несколько изображений
image_files = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
images_base64 = []

for img_file in image_files:
    with open(img_file, "rb") as f:
        img_data = f.read()
        img_b64 = base64.b64encode(img_data).decode("utf-8")
        images_base64.append(img_b64)

# Формируем content с несколькими изображениями
content = [
    {
        "type": "text",
        "text": "Проанализируй все фото товара и дай полное описание"
    }
]

for img_b64 in images_base64:
    content.append({
        "type": "image_url",
        "image_url": {
            "url": f"data:image/jpeg;base64,{img_b64}"
        }
    })

# Анализ
response = client.chat.completions.create(
    model="glm-4-6v",
    messages=[{"role": "user", "content": content}],
    temperature=0.3,
    max_tokens=2000
)

description = response.choices[0].message.content
print(description)
```

---

### 6. Асинхронный Vision (для Telegram-бота)

```python
import asyncio
import base64
from typing import List
from zhipuai import ZhipuAI

client = ZhipuAI(api_key="ваш_ключ")

async def analyze_images_async(
    images_bytes: List[bytes], 
    prompt: str
) -> str:
    """
    Асинхронный анализ изображений.
    
    Args:
        images_bytes: Список байтов изображений
        prompt: Промпт для анализа
    
    Returns:
        Описание товара
    """
    # Формируем content
    content = [{"type": "text", "text": prompt}]
    
    for img_bytes in images_bytes[:5]:  # Максимум 5 фото
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img_b64}"
            }
        })
    
    # Асинхронный вызов через executor
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model="glm-4-6v",
            messages=[{"role": "user", "content": content}],
            temperature=0.3,
            max_tokens=2000
        )
    )
    
    return response.choices[0].message.content

# Использование в aiogram хендлере
async def handler(message: Message):
    # Скачиваем фото
    photo_bytes = await message.bot.download(message.photo[-1].file_id)
    
    # Анализируем
    description = await analyze_images_async(
        [photo_bytes.read()],
        "Опиши товар на фото"
    )
    
    await message.answer(description)
```

---

### 7. Обработка ошибок

```python
from zhipuai import ZhipuAI
import logging

client = ZhipuAI(api_key="ваш_ключ")

async def safe_generate(prompt: str) -> str:
    """Генерация с обработкой ошибок."""
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="glm-4-plus",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
        )
        return response.choices[0].message.content
        
    except Exception as e:
        logging.error(f"Ошибка GLM API: {e}")
        return None
```

---

## 🏗️ ИНТЕГРАЦИЯ В ПРОЕКТ

### GLMProvider класс (полная реализация)

```python
# core/ai_providers/glm.py

import asyncio
import base64
import structlog
from typing import Optional, List
from zhipuai import ZhipuAI

from core.ai_providers.base import (
    BaseVisionProvider, 
    BaseTextProvider, 
    ProviderResponse
)

logger = structlog.get_logger()


class GLMProvider(BaseVisionProvider, BaseTextProvider):
    """
    Провайдер Z.AI GLM.
    
    Использует официальную библиотеку zhipuai>=2.1.5.20250131
    Документация: https://open.bigmodel.cn/dev/api
    """
    
    name = "glm"
    
    # Модели
    VISION_MODEL = "glm-4-6v"      # GLM-4.6V (лучшее качество)
    VISION_FAST = "glm-4v-flash"   # Быстрый Vision
    TEXT_MODEL = "glm-4-plus"      # Качественный Text
    TEXT_FAST = "glm-4-flash"      # Быстрый Text
    
    def __init__(
        self, 
        api_key: str,
        use_fast_models: bool = False
    ):
        """
        Инициализация провайдера.
        
        Args:
            api_key: API ключ Z.AI
            use_fast_models: Использовать flash модели (быстрее)
        """
        self.api_key = api_key
        self.use_fast_models = use_fast_models
        self._client = ZhipuAI(api_key=api_key)
        
        # Выбор моделей
        self.vision_model = self.VISION_FAST if use_fast_models else self.VISION_MODEL
        self.text_model = self.TEXT_FAST if use_fast_models else self.TEXT_MODEL
        
        logger.info(
            "glm_provider_initialized",
            vision_model=self.vision_model,
            text_model=self.text_model
        )
    
    async def analyze_image(
        self, 
        image_bytes: bytes,
        prompt: Optional[str] = None
    ) -> ProviderResponse:
        """Анализ одного изображения."""
        return await self.analyze_multiple_images([image_bytes], prompt)
    
    async def analyze_multiple_images(
        self,
        images: List[bytes],
        prompt: Optional[str] = None
    ) -> ProviderResponse:
        """Анализ нескольких изображений (до 5)."""
        if not prompt:
            prompt = "Опиши подробно что изображено на фото."
        
        # Формируем content с изображениями
        content = [{"type": "text", "text": prompt}]
        
        for img_bytes in images[:5]:
            base64_image = base64.b64encode(img_bytes).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })
        
        try:
            # Асинхронный вызов через executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.chat.completions.create(
                    model=self.vision_model,
                    messages=[{"role": "user", "content": content}],
                    temperature=0.3,
                    max_tokens=2000
                )
            )
            
            result_text = response.choices[0].message.content
            tokens_used = getattr(response.usage, 'total_tokens', None)
            
            logger.info(
                "glm_vision_success",
                model=self.vision_model,
                images_count=len(images),
                tokens=tokens_used
            )
            
            return ProviderResponse(
                success=True,
                content=result_text,
                provider_name=self.name,
                tokens_used=tokens_used
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error("glm_vision_error", error=error_msg)
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg
            )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        """Генерация текста."""
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        try:
            # Асинхронный вызов через executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.chat.completions.create(
                    model=self.text_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            )
            
            result_text = response.choices[0].message.content
            tokens_used = getattr(response.usage, 'total_tokens', None)
            
            logger.info(
                "glm_text_success",
                model=self.text_model,
                tokens=tokens_used
            )
            
            return ProviderResponse(
                success=True,
                content=result_text,
                provider_name=self.name,
                tokens_used=tokens_used
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error("glm_text_error", error=error_msg)
            return ProviderResponse(
                success=False,
                content="",
                provider_name=self.name,
                error_message=error_msg
            )
    
    async def close(self):
        """Закрыть клиент (не требуется для zhipuai)."""
        pass
```

---

## ✅ ПРЕИМУЩЕСТВА ОФИЦИАЛЬНОЙ БИБЛИОТЕКИ

1. **Простота использования** - не нужно разбираться с HTTP-запросами
2. **Полная поддержка моделей** - все актуальные GLM модели
3. **Встроенная обработка ошибок** - стабильнее работает
4. **Официальная поддержка** - обновления от Z.ai
5. **Совместимость с aiogram** - через `run_in_executor()`
6. **Меньше кода** - чище и понятнее

---

## 🧪 ТЕСТИРОВАНИЕ

```python
# test_glm.py
import asyncio
from core.ai_providers.glm import GLMProvider

async def test_glm():
    provider = GLMProvider(api_key="your_key")
    
    # Тест текстовой генерации
    response = await provider.generate("Скажи привет")
    print(f"Text: {response.content}")
    
    # Тест Vision (с реальным изображением)
    with open("test.jpg", "rb") as f:
        img_bytes = f.read()
    
    response = await provider.analyze_image(img_bytes)
    print(f"Vision: {response.content}")

asyncio.run(test_glm())
```

---

## 📚 ПОЛЕЗНЫЕ ССЫЛКИ

- **Официальная документация:** https://open.bigmodel.cn/dev/api
- **Python SDK:** https://github.com/zhipuai/zhipuai-sdk-python-v4
- **Получить API ключ:** https://z.ai/manage-apikey/apikey-list
- **Модели и цены:** https://open.bigmodel.cn/pricing

---

*Документация обновлена: 2 февраля 2026*
