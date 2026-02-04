# ⚙️ ШАГ 5: ГЕНЕРАЦИЯ ТЗ

> Основная логика генерации ТЗ с прогресс-баром и валидацией

---

## 📋 ЦЕЛЬ ЭТОГО ШАГА

Создать:
- Класс TZGenerator — оркестрация генерации
- Прогресс-бар с обновлением в реальном времени
- Валидатор качества ТЗ
- Handler генерации с полным флоу
- Перегенерация

---

## 📁 СТРУКТУРА ФАЙЛОВ

После этого шага:

```
core/
├── __init__.py
├── exceptions.py
├── prompts.py              # Уже есть
├── ai_providers/           # Уже есть
├── generator.py            # Основной генератор
└── validator.py            # Валидатор качества

utils/
├── __init__.py
└── progress.py             # Прогресс-бар
```

---

## 📝 ПРОМПТ ДЛЯ НЕЙРОСЕТИ

```
Создай модуль генерации ТЗ для Telegram-бота.

КОНТЕКСТ:
После выбора категории пользователь видит прогресс-бар, ТЗ генерируется и отправляется.

ФЛОУ ГЕНЕРАЦИИ:
1. Пользователь выбирает категорию (callback category:electronics)
2. Проверяется баланс
3. Если баланс = 0: показать пакеты для покупки
4. Если баланс > 0:
   a. Списать 1 кредит
   b. Скачать фото (bytes)
   c. Показать прогресс-бар
   d. Анализ фото через Vision (этап 1)
   e. Обновить прогресс (этап 2)
   f. Генерация ТЗ через Text (этап 3)
   g. Валидация качества
   h. Если не прошла валидацию — retry с улучшенным промптом
   i. Обновить прогресс (этап 4)
   j. Сохранить в БД
   k. Отправить результат пользователю

ЗАДАЧА:

1. Создай utils/progress.py:
   - Класс ProgressTracker:
     * __init__(bot, chat_id, message_id)
     * STAGES = [(emoji, text), ...] - 4 этапа
     * async update(stage: int) - обновить сообщение
     * async complete() - финальное сообщение
     * async error(message: str) - сообщение об ошибке
   - Этапы:
     * 0: "📷 Анализирую фото..."
     * 1: "🎯 Изучаю целевую аудиторию..."
     * 2: "✍️ Генерирую тексты..."
     * 3: "✅ Финальная проверка..."

2. Создай core/validator.py:
   - Dataclass ValidationResult:
     * is_valid: bool
     * score: int (0-100)
     * found_sections: List[str]
     * missing_sections: List[str]
     * warnings: List[str]
   - Класс TZValidator:
     * REQUIRED_SECTIONS = ["товар", "целевая аудитория", ...]
     * MIN_LENGTH = 1500
     * validate(tz_text: str) -> ValidationResult
     * _check_sections(text) - проверка наличия секций
     * _calculate_score(text, found_sections) - расчёт оценки

3. Создай core/generator.py:
   - Класс TZGenerator:
     * __init__(vision_chain, text_chain, validator)
     * async generate(
         photos: List[bytes],
         category: str,
         progress_callback: Optional[Callable]
       ) -> GenerationResult
     * async _analyze_photos(photos, prompt) -> str
     * async _generate_tz(analysis, category) -> str
     * async _generate_with_retry(analysis, category, max_retries=2) -> tuple[str, int]
   - Dataclass GenerationResult:
     * success: bool
     * photo_analysis: str
     * tz_text: str
     * quality_score: int
     * error_message: Optional[str]

4. Обнови bot/handlers/generation.py:
   - Callback handler для category:{key}
   - Проверка баланса
   - Скачивание фото через bot.download
   - Создание прогресс-бара
   - Вызов generator.generate()
   - Сохранение в БД
   - Отправка результата (разбивка если > 4000 символов)
   - Callback для regenerate:{id}
   - Callback для feedback:{id}:{rating}

ПРОГРЕСС-БАР ФОРМАТ:
```
⏳ Создаю ТЗ для твоего товара

✅ Анализ фото
✅ Изучение целевой аудитории
🔄 Генерация текстов... (60%)
⬜ Финальная проверка

Примерно 15 секунд...
```

ВАЛИДАЦИЯ ТЗ:
- Проверить наличие 8 секций (по ключевым словам)
- Минимум 1500 символов
- Есть HEX-цвета (regex #[0-9A-Fa-f]{6})
- Есть конкретные заголовки (не "напишите заголовок")
- Score = (found_sections / total * 60) + (length_score * 20) + (quality_bonus * 20)

РАЗБИВКА СООБЩЕНИЯ:
- Telegram лимит 4096 символов
- Разбивать по секциям (## заголовок)
- Или по 3500 символов если секции длинные

ПРАВИЛА:
{Правила из docs/01_RULES_FOR_AI.md}

ТРЕБОВАНИЯ:
1. Async везде
2. Graceful error handling (не падать, показывать пользователю ошибку)
3. Логирование каждого этапа
4. Retry при неудачной генерации
5. Транзакционность (если ошибка после списания — вернуть кредит)

Создай полный код всех файлов.
```

---

## 📦 КЛЮЧЕВЫЕ ФАЙЛЫ

### utils/progress.py

```python
"""
Прогресс-бар для генерации ТЗ.
"""

from typing import Optional, List, Tuple
import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

logger = structlog.get_logger()


class ProgressTracker:
    """
    Отслеживание и отображение прогресса генерации.
    
    Обновляет сообщение в Telegram с текущим статусом.
    """
    
    STAGES: List[Tuple[str, str]] = [
        ("📷", "Анализирую фото..."),
        ("🎯", "Изучаю целевую аудиторию..."),
        ("✍️", "Генерирую тексты..."),
        ("✅", "Финальная проверка...")
    ]
    
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int
    ):
        """
        Args:
            bot: Инстанс бота
            chat_id: ID чата
            message_id: ID сообщения для обновления
        """
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.current_stage = 0
    
    async def update(self, stage: int, substage: Optional[str] = None) -> None:
        """
        Обновить прогресс-бар.
        
        Args:
            stage: Номер этапа (0-3)
            substage: Дополнительная информация (например, "60%")
        """
        self.current_stage = stage
        text = self._build_progress_text(substage)
        
        try:
            await self.bot.edit_message_text(
                text=text,
                chat_id=self.chat_id,
                message_id=self.message_id
            )
        except TelegramBadRequest as e:
            # Игнорируем ошибку "message is not modified"
            if "message is not modified" not in str(e):
                logger.warning("progress_update_failed", error=str(e))
    
    async def complete(self) -> None:
        """Показать что генерация завершена."""
        await self.update(len(self.STAGES))
    
    async def error(self, message: str) -> None:
        """Показать сообщение об ошибке."""
        text = (
            "❌ <b>Ошибка генерации</b>\n\n"
            f"{message}\n\n"
            "Попробуй ещё раз или обратись в поддержку."
        )
        
        try:
            await self.bot.edit_message_text(
                text=text,
                chat_id=self.chat_id,
                message_id=self.message_id
            )
        except TelegramBadRequest:
            pass
    
    def _build_progress_text(self, substage: Optional[str] = None) -> str:
        """Построить текст прогресс-бара."""
        lines = ["⏳ <b>Создаю ТЗ для твоего товара</b>\n"]
        
        for i, (emoji, text) in enumerate(self.STAGES):
            if i < self.current_stage:
                # Этап завершён
                lines.append(f"✅ {text.replace('...', '')}")
            elif i == self.current_stage:
                # Текущий этап
                if substage:
                    lines.append(f"🔄 {text} ({substage})")
                else:
                    lines.append(f"🔄 {text}")
            else:
                # Будущий этап
                lines.append(f"⬜ {text.replace('...', '')}")
        
        # Оценка времени
        remaining = (len(self.STAGES) - self.current_stage) * 5
        if remaining > 0:
            lines.append(f"\n<i>Примерно {remaining} секунд...</i>")
        else:
            lines.append("\n<i>Почти готово...</i>")
        
        return "\n".join(lines)
```

### core/validator.py

```python
"""
Валидатор качества сгенерированного ТЗ.
"""

import re
from dataclasses import dataclass, field
from typing import List

from core.prompts import REQUIRED_SECTIONS, MIN_TZ_LENGTH


@dataclass
class ValidationResult:
    """Результат валидации ТЗ."""
    is_valid: bool
    score: int  # 0-100
    found_sections: List[str] = field(default_factory=list)
    missing_sections: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class TZValidator:
    """
    Валидатор качества технического задания.
    
    Проверяет:
    - Наличие всех 8 обязательных секций
    - Минимальную длину текста
    - Наличие конкретных деталей (цвета, размеры)
    - Качество контента (не шаблонные фразы)
    """
    
    # Паттерны для поиска секций
    SECTION_PATTERNS = {
        "товар": r"(товар|продукт|категория)",
        "целевая аудитория": r"(целевая аудитория|аудитория|ца|для кого)",
        "визуальная концепция": r"(визуальн|концепция|стиль|дизайн)",
        "главное фото": r"(главное фото|первый слайд|обложка)",
        "инфографика": r"(инфографика|слайд\s*\d|карточк)",
        "готовые тексты": r"(готовые тексты|тексты|заголовок|описание)",
        "рекомендации": r"(рекомендаци|важно|нельзя|совет)",
        "a/b тест": r"(a/b|тест|эксперимент)"
    }
    
    # Паттерны качества
    HEX_COLOR_PATTERN = r"#[0-9A-Fa-f]{6}"
    TEMPLATE_PHRASES = [
        "напишите",
        "можно использовать",
        "например",
        "на ваше усмотрение",
        "по желанию"
    ]
    
    def __init__(self, min_length: int = MIN_TZ_LENGTH):
        self.min_length = min_length
    
    def validate(self, tz_text: str) -> ValidationResult:
        """
        Валидировать ТЗ и вернуть результат.
        
        Args:
            tz_text: Текст ТЗ для проверки
            
        Returns:
            ValidationResult с результатами проверки
        """
        warnings = []
        
        # Проверка секций
        found_sections, missing_sections = self._check_sections(tz_text)
        
        # Проверка длины
        if len(tz_text) < self.min_length:
            warnings.append(
                f"Текст слишком короткий: {len(tz_text)} < {self.min_length}"
            )
        
        # Проверка HEX цветов
        hex_colors = re.findall(self.HEX_COLOR_PATTERN, tz_text)
        if len(hex_colors) < 2:
            warnings.append("Мало конкретных цветов (HEX)")
        
        # Проверка шаблонных фраз
        template_count = sum(
            1 for phrase in self.TEMPLATE_PHRASES
            if phrase.lower() in tz_text.lower()
        )
        if template_count > 3:
            warnings.append("Много шаблонных фраз")
        
        # Расчёт оценки
        score = self._calculate_score(
            tz_text=tz_text,
            found_sections=found_sections,
            hex_colors_count=len(hex_colors),
            template_count=template_count
        )
        
        # Определяем валидность
        is_valid = (
            len(missing_sections) <= 1 and
            len(tz_text) >= self.min_length * 0.8 and
            score >= 60
        )
        
        return ValidationResult(
            is_valid=is_valid,
            score=score,
            found_sections=found_sections,
            missing_sections=missing_sections,
            warnings=warnings
        )
    
    def _check_sections(self, text: str) -> tuple[List[str], List[str]]:
        """Проверить наличие обязательных секций."""
        text_lower = text.lower()
        found = []
        missing = []
        
        for section, pattern in self.SECTION_PATTERNS.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                found.append(section)
            else:
                missing.append(section)
        
        return found, missing
    
    def _calculate_score(
        self,
        tz_text: str,
        found_sections: List[str],
        hex_colors_count: int,
        template_count: int
    ) -> int:
        """
        Рассчитать оценку качества (0-100).
        
        Формула:
        - 50% — наличие секций
        - 25% — длина текста
        - 15% — конкретные детали (цвета)
        - 10% — отсутствие шаблонных фраз
        """
        total_sections = len(self.SECTION_PATTERNS)
        
        # Секции (50 баллов)
        section_score = (len(found_sections) / total_sections) * 50
        
        # Длина (25 баллов)
        length_ratio = min(len(tz_text) / self.min_length, 1.5)
        length_score = min(length_ratio * 16.7, 25)
        
        # Детали (15 баллов)
        detail_score = min(hex_colors_count * 3, 15)
        
        # Без шаблонов (10 баллов)
        template_penalty = min(template_count * 2, 10)
        template_score = 10 - template_penalty
        
        total = int(section_score + length_score + detail_score + template_score)
        return max(0, min(100, total))
```

### core/generator.py

```python
"""
Основной генератор ТЗ.
"""

import structlog
from dataclasses import dataclass
from typing import Optional, List, Callable, Awaitable

from core.ai_providers.chain import VisionProviderChain, TextProviderChain
from core.validator import TZValidator, ValidationResult
from core.prompts import (
    VISION_ANALYSIS_PROMPT,
    TZ_SYSTEM_PROMPT,
    build_tz_prompt
)
from core.exceptions import VisionAnalysisError, TextGenerationError, ValidationError

logger = structlog.get_logger()

# Callback для обновления прогресса
ProgressCallback = Callable[[int, Optional[str]], Awaitable[None]]


@dataclass
class GenerationResult:
    """Результат генерации ТЗ."""
    success: bool
    photo_analysis: str = ""
    tz_text: str = ""
    quality_score: int = 0
    validation: Optional[ValidationResult] = None
    error_message: Optional[str] = None


class TZGenerator:
    """
    Генератор технических заданий.
    
    Оркестрирует:
    1. Анализ фото через Vision
    2. Генерацию ТЗ через Text
    3. Валидацию качества
    4. Retry при неудаче
    """
    
    MAX_RETRIES = 2
    
    def __init__(
        self,
        vision_chain: VisionProviderChain,
        text_chain: TextProviderChain,
        validator: Optional[TZValidator] = None
    ):
        self.vision = vision_chain
        self.text = text_chain
        self.validator = validator or TZValidator()
    
    async def generate(
        self,
        photos: List[bytes],
        category: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> GenerationResult:
        """
        Сгенерировать ТЗ по фотографиям товара.
        
        Args:
            photos: Список байтов фотографий
            category: Категория товара (ключ)
            progress_callback: Функция для обновления прогресса
            
        Returns:
            GenerationResult с результатом генерации
        """
        async def update_progress(stage: int, substage: str = None):
            if progress_callback:
                await progress_callback(stage, substage)
        
        try:
            # Этап 1: Анализ фото
            await update_progress(0)
            
            logger.info("generation_started", category=category, photos=len(photos))
            
            photo_analysis = await self._analyze_photos(photos)
            
            if not photo_analysis or len(photo_analysis) < 100:
                raise VisionAnalysisError("Не удалось проанализировать фото")
            
            logger.info("photo_analysis_complete", length=len(photo_analysis))
            
            # Этап 2: Подготовка
            await update_progress(1)
            
            # Этап 3: Генерация ТЗ
            await update_progress(2)
            
            tz_text, quality_score = await self._generate_with_retry(
                photo_analysis=photo_analysis,
                category=category,
                progress_callback=lambda s: update_progress(2, s)
            )
            
            logger.info(
                "tz_generation_complete",
                length=len(tz_text),
                score=quality_score
            )
            
            # Этап 4: Финализация
            await update_progress(3)
            
            # Финальная валидация
            validation = self.validator.validate(tz_text)
            
            return GenerationResult(
                success=True,
                photo_analysis=photo_analysis,
                tz_text=tz_text,
                quality_score=quality_score,
                validation=validation
            )
            
        except VisionAnalysisError as e:
            logger.error("vision_analysis_failed", error=str(e))
            return GenerationResult(
                success=False,
                error_message=f"Ошибка анализа фото: {e}"
            )
            
        except TextGenerationError as e:
            logger.error("text_generation_failed", error=str(e))
            return GenerationResult(
                success=False,
                error_message=f"Ошибка генерации текста: {e}"
            )
            
        except Exception as e:
            logger.error("generation_failed", error=str(e))
            return GenerationResult(
                success=False,
                error_message=f"Неизвестная ошибка: {e}"
            )
    
    async def _analyze_photos(self, photos: List[bytes]) -> str:
        """Анализировать фотографии через Vision."""
        try:
            response = await self.vision.analyze_multiple_images(
                images=photos,
                prompt=VISION_ANALYSIS_PROMPT
            )
            
            if not response.success:
                raise VisionAnalysisError(response.error_message or "Unknown error")
            
            return response.content
            
        except RuntimeError as e:
            raise VisionAnalysisError(str(e))
    
    async def _generate_with_retry(
        self,
        photo_analysis: str,
        category: str,
        progress_callback: Optional[Callable] = None
    ) -> tuple[str, int]:
        """
        Генерация ТЗ с retry при низком качестве.
        
        Returns:
            (tz_text, quality_score)
        """
        last_validation = None
        
        for attempt in range(self.MAX_RETRIES + 1):
            if progress_callback:
                progress = f"{(attempt + 1) * 30}%"
                await progress_callback(progress)
            
            # Формируем промпт
            prompt = build_tz_prompt(
                product_description=photo_analysis,
                category=category
            )
            
            # Если это retry — добавляем информацию о проблемах
            if attempt > 0 and last_validation:
                prompt = self._enhance_prompt_for_retry(
                    prompt=prompt,
                    validation=last_validation
                )
            
            # Генерируем
            try:
                response = await self.text.generate(
                    prompt=prompt,
                    system_prompt=TZ_SYSTEM_PROMPT,
                    max_tokens=4000,
                    temperature=0.7
                )
                
                if not response.success:
                    raise TextGenerationError(response.error_message or "Unknown error")
                
                tz_text = response.content
                
            except RuntimeError as e:
                raise TextGenerationError(str(e))
            
            # Валидируем
            validation = self.validator.validate(tz_text)
            last_validation = validation
            
            logger.info(
                "generation_attempt",
                attempt=attempt + 1,
                score=validation.score,
                is_valid=validation.is_valid,
                missing=validation.missing_sections
            )
            
            # Если качество достаточное — возвращаем
            if validation.is_valid or attempt == self.MAX_RETRIES:
                return tz_text, validation.score
        
        # Не должны сюда попасть, но на всякий случай
        return tz_text, last_validation.score if last_validation else 0
    
    def _enhance_prompt_for_retry(
        self,
        prompt: str,
        validation: ValidationResult
    ) -> str:
        """Улучшить промпт на основе ошибок валидации."""
        additions = []
        
        if validation.missing_sections:
            sections = ", ".join(validation.missing_sections)
            additions.append(
                f"ВАЖНО: В предыдущей версии отсутствовали секции: {sections}. "
                f"Обязательно добавь их!"
            )
        
        if "Текст слишком короткий" in str(validation.warnings):
            additions.append(
                "ВАЖНО: Текст должен быть минимум 2000 символов. "
                "Добавь больше деталей!"
            )
        
        if additions:
            return prompt + "\n\n" + "\n".join(additions)
        
        return prompt
```

### bot/handlers/generation.py (основная часть)

```python
"""
Обработчик генерации ТЗ.
"""

import io
import structlog
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from bot.keyboards import (
    get_generation_result_keyboard,
    get_packages_keyboard
)
from bot.states import GenerationStates
from database import crud
from database.models import User
from core.generator import TZGenerator, GenerationResult
from core.ai_providers import create_vision_chain, create_text_chain
from utils.progress import ProgressTracker

router = Router(name="generation")
logger = structlog.get_logger()

# Создаём генератор
generator = TZGenerator(
    vision_chain=create_vision_chain(),
    text_chain=create_text_chain()
)


@router.callback_query(F.data.startswith("category:"))
async def handle_category_selection(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    bot: Bot
) -> None:
    """Обработка выбора категории и запуск генерации."""
    await callback.answer()
    
    category = callback.data.split(":")[1]
    data = await state.get_data()
    photos = data.get("photos", [])
    
    if not photos:
        await callback.message.edit_text("⚠️ Фото не найдены. Начни сначала.")
        await state.clear()
        return
    
    # Проверяем баланс
    if user.balance <= 0:
        await callback.message.edit_text(
            "💰 У тебя закончились кредиты!\n\n"
            "Выбери пакет для пополнения:",
            reply_markup=get_packages_keyboard()
        )
        return
    
    # Списываем кредит
    success = await crud.decrease_balance(callback.from_user.id, 1)
    if not success:
        await callback.message.edit_text(
            "⚠️ Не удалось списать кредит. Попробуй позже."
        )
        return
    
    # Устанавливаем состояние генерации
    await state.set_state(GenerationStates.generating)
    
    # Показываем прогресс-бар
    progress_msg = await callback.message.edit_text(
        "⏳ <b>Создаю ТЗ для твоего товара</b>\n\n"
        "🔄 Начинаю анализ..."
    )
    
    progress = ProgressTracker(
        bot=bot,
        chat_id=callback.message.chat.id,
        message_id=progress_msg.message_id
    )
    
    try:
        # Скачиваем фото
        photo_bytes_list = []
        for photo_data in photos:
            file = await bot.get_file(photo_data["file_id"])
            photo_bytes = io.BytesIO()
            await bot.download_file(file.file_path, photo_bytes)
            photo_bytes_list.append(photo_bytes.getvalue())
        
        # Запускаем генерацию
        result: GenerationResult = await generator.generate(
            photos=photo_bytes_list,
            category=category,
            progress_callback=progress.update
        )
        
        if not result.success:
            # Возвращаем кредит при ошибке
            await crud.increase_balance(callback.from_user.id, 1)
            await progress.error(result.error_message or "Неизвестная ошибка")
            await state.clear()
            return
        
        # Сохраняем в БД
        photo_file_ids = [
            (p["file_id"], p["file_unique_id"]) 
            for p in photos
        ]
        
        generation = await crud.create_generation(
            user_id=user.id,
            category=category,
            photo_analysis=result.photo_analysis,
            tz_text=result.tz_text,
            quality_score=result.quality_score,
            photo_file_ids=photo_file_ids,
            is_free=(user.balance == 0)  # Было бесплатное
        )
        
        # Увеличиваем счётчик
        await crud.increment_total_generated(callback.from_user.id)
        
        # Завершаем прогресс
        await progress.complete()
        
        # Отправляем результат
        await send_generation_result(
            callback=callback,
            tz_text=result.tz_text,
            generation_id=generation.id,
            quality_score=result.quality_score
        )
        
        logger.info(
            "generation_successful",
            user_id=callback.from_user.id,
            generation_id=generation.id,
            score=result.quality_score
        )
        
    except Exception as e:
        # Возвращаем кредит при ошибке
        await crud.increase_balance(callback.from_user.id, 1)
        await progress.error(str(e))
        logger.error("generation_error", error=str(e))
    
    finally:
        await state.clear()


async def send_generation_result(
    callback: CallbackQuery,
    tz_text: str,
    generation_id: int,
    quality_score: int
) -> None:
    """Отправить результат генерации пользователю."""
    # Разбиваем на части если нужно
    MAX_LENGTH = 3500  # С запасом для форматирования
    
    parts = split_text_by_sections(tz_text, MAX_LENGTH)
    
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            # Последняя часть — с клавиатурой
            await callback.message.answer(
                part,
                reply_markup=get_generation_result_keyboard(generation_id)
            )
        else:
            # Промежуточные части — без клавиатуры
            await callback.message.answer(part)
    
    # Сообщение об экономии
    await callback.message.answer(
        f"✨ <b>ТЗ готово!</b>\n\n"
        f"📊 Качество: {quality_score}/100\n"
        f"⏱ Ты сэкономил примерно 2.5 часа работы!\n\n"
        f"Оцени результат: 👍 или 👎"
    )


def split_text_by_sections(text: str, max_length: int) -> list[str]:
    """Разбить текст на части по секциям."""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    # Разбиваем по заголовкам секций
    sections = text.split("\n## ")
    
    for i, section in enumerate(sections):
        if i > 0:
            section = "## " + section
        
        if len(current_part) + len(section) + 1 <= max_length:
            current_part += ("\n" if current_part else "") + section
        else:
            if current_part:
                parts.append(current_part)
            current_part = section
    
    if current_part:
        parts.append(current_part)
    
    return parts


@router.callback_query(F.data.startswith("feedback:"))
async def handle_feedback(callback: CallbackQuery, user: User) -> None:
    """Обработка оценки ТЗ."""
    await callback.answer("Спасибо за оценку! 🙏")
    
    parts = callback.data.split(":")
    generation_id = int(parts[1])
    rating = int(parts[2])
    
    # Проверяем нет ли уже фидбека
    if await crud.has_feedback(generation_id):
        return
    
    # Сохраняем фидбек
    await crud.create_feedback(
        generation_id=generation_id,
        user_id=user.id,
        rating=rating
    )
    
    if rating == 1:
        await callback.message.answer(
            "🎉 Рады что ТЗ понравилось!\n\n"
            "Расскажи о нас друзьям — получи бонусные кредиты!"
        )
    else:
        await callback.message.answer(
            "😔 Жаль что не понравилось.\n\n"
            "Напиши что было не так — мы улучшим сервис!\n"
            "Ты можешь бесплатно перегенерировать это ТЗ."
        )


@router.callback_query(F.data.startswith("regenerate:"))
async def handle_regenerate(
    callback: CallbackQuery,
    user: User,
    bot: Bot
) -> None:
    """Перегенерация ТЗ."""
    generation_id = int(callback.data.split(":")[1])
    
    # Получаем генерацию
    generation = await crud.get_generation_by_id(generation_id)
    if not generation:
        await callback.answer("ТЗ не найдено", show_alert=True)
        return
    
    # Проверяем количество перегенераций
    if generation.regenerations >= 1:
        # Нужен кредит
        if user.balance <= 0:
            await callback.answer(
                "Бесплатная перегенерация уже использована. Нужен кредит.",
                show_alert=True
            )
            return
        
        # Списываем кредит
        await crud.decrease_balance(callback.from_user.id, 1)
    
    await callback.answer("Перегенерирую ТЗ...")
    
    # Увеличиваем счётчик
    await crud.increment_regenerations(generation_id)
    
    # Показываем прогресс
    progress_msg = await callback.message.answer(
        "🔄 Перегенерирую ТЗ..."
    )
    
    progress = ProgressTracker(
        bot=bot,
        chat_id=callback.message.chat.id,
        message_id=progress_msg.message_id
    )
    
    try:
        # Используем сохранённый анализ фото
        from core.prompts import TZ_SYSTEM_PROMPT, build_tz_prompt
        from core.ai_providers import create_text_chain
        from core.validator import TZValidator
        
        text_chain = create_text_chain()
        validator = TZValidator()
        
        await progress.update(2)
        
        prompt = build_tz_prompt(
            product_description=generation.photo_analysis,
            category=generation.category
        )
        
        response = await text_chain.generate(
            prompt=prompt,
            system_prompt=TZ_SYSTEM_PROMPT
        )
        
        if not response.success:
            await progress.error("Ошибка генерации")
            return
        
        await progress.update(3)
        
        validation = validator.validate(response.content)
        
        # Обновляем в БД
        await crud.update_generation_tz(
            generation_id=generation_id,
            tz_text=response.content,
            quality_score=validation.score
        )
        
        await progress.complete()
        
        # Отправляем результат
        await send_generation_result(
            callback=callback,
            tz_text=response.content,
            generation_id=generation_id,
            quality_score=validation.score
        )
        
    except Exception as e:
        await progress.error(str(e))
        logger.error("regeneration_error", error=str(e))
```

---

## ✅ ЧЕКЛИСТ ВЫПОЛНЕНИЯ

- [ ] `utils/progress.py` создан и работает
- [ ] `core/validator.py` корректно валидирует ТЗ
- [ ] `core/generator.py` успешно генерирует
- [ ] Прогресс-бар обновляется в реальном времени
- [ ] ТЗ сохраняется в БД
- [ ] Перегенерация работает
- [ ] Кредит возвращается при ошибке

---

## 🧪 ТЕСТИРОВАНИЕ

1. Отправь фото товара
2. Выбери категорию
3. Наблюдай прогресс-бар
4. Получи ТЗ
5. Попробуй перегенерировать
6. Оцени 👍 или 👎

---

## ➡️ СЛЕДУЮЩИЙ ШАГ

После успешного выполнения переходи к [STEP_06_PAYMENTS.md](STEP_06_PAYMENTS.md)

---

*Шаг 5 из 7*
