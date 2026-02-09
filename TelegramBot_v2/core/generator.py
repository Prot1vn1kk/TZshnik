"""
Основной генератор ТЗ.

Оркестрирует весь процесс генерации:
1. Анализ фото через Vision AI
2. Генерация ТЗ через Text AI
3. Валидация качества
4. Retry при неудаче
"""

import structlog
from dataclasses import dataclass
from typing import Optional, List, Callable, Awaitable

from core.ai_providers.chain import VisionProviderChain, TextProviderChain
from core.validator import TZValidator, ValidationResult
from core.prompts import (
    VISION_ANALYSIS_PROMPT,
    build_tz_prompt,
    build_regeneration_prompt,
)
from core.exceptions import (
    GenerationError,
    VisionAnalysisError,
    TextGenerationError,
    ValidationError,
)


logger = structlog.get_logger()


# Максимальное количество токенов для генерации ТЗ
# 8000 токенов ≈ 24000-32000 символов (достаточно для полного ТЗ с 6+ слайдами)
MAX_GENERATION_TOKENS = 8000

# Тип callback-а для обновления прогресса
# Принимает: номер этапа (0-3), опциональный текст подэтапа
ProgressCallback = Callable[[int, Optional[str]], Awaitable[None]]


@dataclass
class GenerationResult:
    """
    Результат генерации ТЗ.
    
    Attributes:
        success: Успешна ли генерация
        photo_analysis: Результат анализа фото
        tz_text: Текст сгенерированного ТЗ
        quality_score: Оценка качества (0-100)
        validation: Результат валидации
        error_message: Сообщение об ошибке (если есть)
        retry_count: Количество попыток генерации
    """
    success: bool
    photo_analysis: str = ""
    tz_text: str = ""
    quality_score: int = 0
    validation: Optional[ValidationResult] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class TZGenerator:
    """
    Генератор технических заданий для инфографики.
    
    Оркестрирует:
    1. Анализ фото через Vision (Gemini)
    2. Генерацию ТЗ через Text (Gemini)
    3. Валидацию качества результата
    4. Автоматический retry при низком качестве
    """
    
    MAX_RETRIES = 2  # Максимум повторных попыток генерации
    
    def __init__(
        self,
        vision_chain: VisionProviderChain,
        text_chain: TextProviderChain,
        validator: Optional[TZValidator] = None,
    ):
        """
        Args:
            vision_chain: Цепочка Vision провайдеров
            text_chain: Цепочка Text провайдеров
            validator: Валидатор качества (создаётся если не передан)
        """
        self.vision_chain = vision_chain
        self.text_chain = text_chain
        self.validator = validator or TZValidator()
    
    @staticmethod
    def _sanitize_feedback(text: str, max_length: int = 500) -> str:
        """
        Очистка пользовательского ввода для безопасной вставки в промпт.
        
        Предотвращает prompt injection атаки.
        
        Args:
            text: Пользовательский текст
            max_length: Максимальная длина
            
        Returns:
            Очищенный текст
        """
        if not text:
            return ""
        # Ограничиваем длину
        text = text[:max_length]
        # Убираем потенциально опасные конструкции
        text = text.replace("```", "")
        text = text.replace("---", "")
        text = text.replace("###", "")
        # Убираем системные маркеры
        text = text.replace("SYSTEM:", "")
        text = text.replace("USER:", "")
        text = text.replace("ASSISTANT:", "")
        return text.strip()
    
    async def generate(
        self,
        photos: List[bytes],
        category: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """
        Основной метод генерации ТЗ.
        
        Args:
            photos: Список фото в байтах
            category: Категория товара
            progress_callback: Callback для обновления прогресса
            
        Returns:
            GenerationResult: Результат генерации
        """
        logger.info(
            "Starting TZ generation",
            photo_count=len(photos),
            category=category,
        )
        
        try:
            # Этап 0: Анализ фото
            if progress_callback:
                await progress_callback(0, None)
            
            photo_analysis = await self._analyze_photos(photos)
            
            logger.info(
                "Photo analysis completed",
                analysis_length=len(photo_analysis),
            )
            
            # Этап 1: Изучение ЦА (включено в анализ, просто обновляем прогресс)
            if progress_callback:
                await progress_callback(1, None)
            
            # Этап 2-3: Генерация ТЗ с валидацией и retry
            if progress_callback:
                await progress_callback(2, None)
            
            tz_text, validation, retry_count = await self._generate_with_retry(
                photo_analysis=photo_analysis,
                category=category,
                progress_callback=progress_callback,
            )
            
            # Этап 3: Финальная проверка
            if progress_callback:
                await progress_callback(3, None)
            
            logger.info(
                "TZ generation completed",
                tz_length=len(tz_text),
                quality_score=validation.score,
                retry_count=retry_count,
            )
            
            return GenerationResult(
                success=True,
                photo_analysis=photo_analysis,
                tz_text=tz_text,
                quality_score=validation.score,
                validation=validation,
                retry_count=retry_count,
            )
            
        except VisionAnalysisError as e:
            logger.error("Vision analysis failed", error=str(e))
            return GenerationResult(
                success=False,
                error_message=f"Ошибка анализа фото: {str(e)}",
            )
            
        except TextGenerationError as e:
            logger.error("Text generation failed", error=str(e))
            return GenerationResult(
                success=False,
                error_message=f"Ошибка генерации текста: {str(e)}",
            )
            
        except Exception as e:
            logger.exception("Unexpected generation error")
            return GenerationResult(
                success=False,
                error_message=f"Неожиданная ошибка: {str(e)}",
            )
    
    async def regenerate(
        self,
        photo_analysis: str,
        category: str,
        previous_tz: str,
        feedback: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """
        Перегенерация ТЗ на основе предыдущего результата.
        
        Использует сохранённый анализ фото, не делает повторный Vision запрос.
        
        Args:
            photo_analysis: Сохранённый анализ фото
            category: Категория товара
            previous_tz: Предыдущий текст ТЗ
            feedback: Отзыв пользователя (что улучшить)
            progress_callback: Callback для прогресса
            
        Returns:
            GenerationResult: Результат перегенерации
        """
        logger.info(
            "Starting TZ regeneration",
            category=category,
            has_feedback=bool(feedback),
        )
        
        try:
            # Пропускаем этап 0-1 (анализ уже есть)
            if progress_callback:
                await progress_callback(2, None)
            
            # Строим промпт для регенерации
            # Формируем текст проблем из feedback и предыдущего ТЗ
            validation_issues = []
            if feedback:
                # Санитизируем пользовательский ввод для безопасности
                safe_feedback = self._sanitize_feedback(feedback)
                if safe_feedback:
                    validation_issues.append(f"Отзыв пользователя: {safe_feedback}")
            if previous_tz:
                validation_issues.append("Необходимо улучшить качество и полноту ТЗ")
            
            prompt = build_regeneration_prompt(
                product_description=photo_analysis,
                category=category,
                validation_issues="\n".join(validation_issues) if validation_issues else "Недостаточное качество",
            )
            
            # Генерируем с увеличенным лимитом токенов для полного ТЗ
            response = await self.text_chain.generate(
                prompt=prompt,
                max_tokens=MAX_GENERATION_TOKENS,
            )
            
            if not response.success:
                raise TextGenerationError(response.error_message or "Unknown error")
            
            tz_text = response.content
            
            # Валидируем
            if progress_callback:
                await progress_callback(3, None)
            
            validation = self.validator.validate(tz_text)
            
            logger.info(
                "TZ regeneration completed",
                tz_length=len(tz_text),
                quality_score=validation.score,
            )
            
            return GenerationResult(
                success=True,
                photo_analysis=photo_analysis,
                tz_text=tz_text,
                quality_score=validation.score,
                validation=validation,
            )
            
        except Exception as e:
            logger.error("Regeneration failed", error=str(e))
            return GenerationResult(
                success=False,
                error_message=str(e),
            )
    
    async def _analyze_photos(self, photos: List[bytes]) -> str:
        """
        Анализ фотографий через Vision AI.
        
        Args:
            photos: Список фото в байтах
            
        Returns:
            str: Текст анализа
            
        Raises:
            VisionAnalysisError: При ошибке анализа
        """
        # Вызываем Vision - провайдеры принимают bytes и сами конвертируют в base64
        if len(photos) == 1:
            response = await self.vision_chain.analyze_image(
                image_bytes=photos[0],
                prompt=VISION_ANALYSIS_PROMPT,
            )
        else:
            response = await self.vision_chain.analyze_multiple_images(
                images=photos,
                prompt=VISION_ANALYSIS_PROMPT,
            )
        
        if not response.success:
            raise VisionAnalysisError(response.error_message or "Vision analysis failed")
        
        return response.content
    
    async def _generate_with_retry(
        self,
        photo_analysis: str,
        category: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> tuple[str, ValidationResult, int]:
        """
        Генерация ТЗ с автоматическим retry при низком качестве.
        
        ВАЖНО: Сохраняет ЛУЧШИЙ результат из всех попыток, а не последний!
        
        Args:
            photo_analysis: Результат анализа фото
            category: Категория товара
            progress_callback: Callback для прогресса
            
        Returns:
            tuple: (текст ТЗ, результат валидации, количество попыток)
            
        Raises:
            TextGenerationError: Если все попытки неудачны
        """
        # Храним ЛУЧШИЙ результат
        best_tz = ""
        best_validation: Optional[ValidationResult] = None
        best_score = -1
        
        # Текущая попытка для промпта
        current_tz = ""
        current_validation: Optional[ValidationResult] = None
        
        for attempt in range(self.MAX_RETRIES + 1):
            if attempt > 0:
                logger.info(f"Retry attempt {attempt}")
                if progress_callback:
                    await progress_callback(2, f"попытка {attempt + 1}")
            
            # Строим промпт
            if attempt == 0:
                # Первая попытка - обычный промпт
                prompt = build_tz_prompt(
                    product_description=photo_analysis,
                    category=category,
                )
            else:
                # Повторная попытка - улучшенный промпт с учётом ошибок
                # Используем лучший результат для улучшения
                prompt = self._build_improved_prompt(
                    photo_analysis=photo_analysis,
                    category=category,
                    previous_tz=best_tz,
                    validation=best_validation,
                )
            
            # Генерируем с увеличенным лимитом токенов для полного ТЗ
            response = await self.text_chain.generate(
                prompt=prompt,
                max_tokens=MAX_GENERATION_TOKENS,
            )
            
            if not response.success:
                if attempt == self.MAX_RETRIES:
                    # Если есть лучший результат - возвращаем его
                    if best_validation is not None:
                        logger.warning(
                            "Returning best result after failed attempt",
                            score=best_score,
                        )
                        return best_tz, best_validation, attempt
                    raise TextGenerationError(
                        response.error_message or "All generation attempts failed"
                    )
                continue
            
            current_tz = response.content
            
            # Валидируем
            current_validation = self.validator.validate(current_tz)
            
            logger.debug(
                f"Attempt {attempt + 1} validation",
                score=current_validation.score,
                is_valid=current_validation.is_valid,
                tz_length=len(current_tz),
            )
            
            # Обновляем лучший результат, если текущий лучше
            if current_validation.score > best_score:
                best_tz = current_tz
                best_validation = current_validation
                best_score = current_validation.score
                logger.debug(
                    f"New best result",
                    score=best_score,
                    tz_length=len(best_tz),
                )
            
            # Если валидация пройдена - возвращаем сразу
            if current_validation.is_valid:
                return current_tz, current_validation, attempt
            
            # Если качество приемлемое (>50) на последней попытке
            if attempt == self.MAX_RETRIES and best_score >= 50:
                logger.warning(
                    "Returning best TZ with suboptimal quality",
                    score=best_score,
                )
                return best_tz, best_validation, attempt  # type: ignore
        
        # Если дошли сюда - возвращаем лучший результат
        # best_validation гарантированно не None, так как цикл выполнился хотя бы раз
        if best_validation is None:
            raise ValueError("Validation should have been performed")
        logger.info(
            "Returning best result from all attempts",
            score=best_score,
            tz_length=len(best_tz),
        )
        return best_tz, best_validation, self.MAX_RETRIES
    
    def _build_improved_prompt(
        self,
        photo_analysis: str,
        category: str,
        previous_tz: str,
        validation: Optional[ValidationResult],
    ) -> str:
        """
        Построить улучшенный промпт с учётом ошибок валидации.
        
        Args:
            photo_analysis: Анализ фото
            category: Категория
            previous_tz: Предыдущий результат
            validation: Результат валидации
            
        Returns:
            str: Улучшенный промпт
        """
        # Базовый промпт
        base_prompt = build_tz_prompt(
            product_description=photo_analysis,
            category=category,
        )
        
        # Добавляем инструкции по исправлению
        improvements = []
        
        if validation:
            if validation.missing_sections:
                improvements.append(
                    f"ОБЯЗАТЕЛЬНО добавь секции: {', '.join(validation.missing_sections)}"
                )
            
            for warning in validation.warnings:
                if "короткий" in warning:
                    improvements.append(
                        "Сделай ТЗ БОЛЕЕ ПОДРОБНЫМ, минимум 2000 символов"
                    )
                elif "цвет" in warning.lower():
                    improvements.append(
                        "Добавь КОНКРЕТНЫЕ HEX коды цветов (например #FF5722)"
                    )
                elif "шаблон" in warning.lower():
                    improvements.append(
                        "Убери шаблонные фразы, напиши КОНКРЕТНЫЕ тексты"
                    )
        
        if improvements:
            improvement_text = "\n".join(f"- {imp}" for imp in improvements)
            base_prompt = f"{base_prompt}\n\n⚠️ ВАЖНЫЕ ИСПРАВЛЕНИЯ:\n{improvement_text}"
        
        return base_prompt


def create_generator() -> TZGenerator:
    """
    Фабричная функция для создания генератора.
    
    Создаёт генератор с настроенными провайдерами.
    
    Returns:
        TZGenerator: Готовый к использованию генератор
    """
    from core.ai_providers import create_vision_chain, create_text_chain
    
    return TZGenerator(
        vision_chain=create_vision_chain(),
        text_chain=create_text_chain(),
        validator=TZValidator(),
    )
