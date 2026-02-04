"""
Валидатор качества сгенерированного ТЗ.

Проверяет ТЗ на соответствие требованиям:
- Наличие всех обязательных секций
- Минимальную длину текста
- Наличие конкретных деталей (цвета, размеры)
- Качество контента (без шаблонных фраз)
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple

import structlog

from core.prompts import MIN_TZ_LENGTH, REQUIRED_SECTIONS


logger = structlog.get_logger()


@dataclass
class ValidationResult:
    """
    Результат валидации ТЗ.
    
    Attributes:
        is_valid: Прошло ли ТЗ валидацию
        score: Оценка качества (0-100)
        found_sections: Найденные секции
        missing_sections: Отсутствующие секции
        warnings: Предупреждения о качестве
    """
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
    - Наличие конкретных деталей (HEX цвета)
    - Качество контента (не шаблонные фразы)
    """
    
    # Паттерны для поиска секций (регистронезависимые)
    SECTION_PATTERNS = {
        "ТОВАР": r"(##?\s*(?:1\.?\s*)?товар|продукт|категория\s+товара)",
        "ЦЕЛЕВАЯ АУДИТОРИЯ": r"(##?\s*(?:2\.?\s*)?целевая аудитория|аудитория|ца\b|для кого)",
        "ВИЗУАЛЬНАЯ КОНЦЕПЦИЯ": r"(##?\s*(?:3\.?\s*)?визуальн|концепция|стиль\s+оформления|дизайн)",
        "ГЛАВНОЕ ФОТО": r"(##?\s*(?:4\.?\s*)?главное фото|первый слайд|обложка)",
        "ИНФОГРАФИКА": r"(##?\s*(?:5\.?\s*)?инфографика|слайд\s*[2-9]|карточк)",
        "ГОТОВЫЕ ТЕКСТЫ": r"(##?\s*(?:6\.?\s*)?готовые тексты|тексты|заголовок)",
        "РЕКОМЕНДАЦИИ ДИЗАЙНЕРУ": r"(##?\s*(?:7\.?\s*)?рекомендаци|важно\b|нельзя|совет|дизайнеру)",
        "A/B ТЕСТ": r"(##?\s*(?:8\.?\s*)?a/?b|тест|эксперимент)",
    }
    
    # Паттерн для HEX цветов
    HEX_COLOR_PATTERN = r"#[0-9A-Fa-f]{6}\b"
    
    # Шаблонные фразы (плохой признак)
    TEMPLATE_PHRASES = [
        "напишите здесь",
        "можно добавить",
        "на ваше усмотрение",
        "по желанию заказчика",
        "вставить текст",
        "[ваш текст]",
        "укажите",
        "заполните",
    ]
    
    # Хорошие признаки качества
    QUALITY_INDICATORS = [
        r"#[0-9A-Fa-f]{6}",  # HEX цвета
        r"\d+\s*(мм|см|м|кг|г|мл|л)\b",  # Размеры
        r"(бесплатная доставка|гарантия|в подарок)",  # УТП
        r"(premium|люкс|эко|натуральн)",  # Качество
    ]
    
    def __init__(self, min_length: int = MIN_TZ_LENGTH):
        """
        Args:
            min_length: Минимальная длина ТЗ в символах
        """
        self.min_length = min_length
    
    def validate(self, tz_text: str) -> ValidationResult:
        """
        Валидировать ТЗ и вернуть результат.
        
        Args:
            tz_text: Текст ТЗ для проверки
            
        Returns:
            ValidationResult: Результат валидации
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
            warnings.append("Мало конкретных цветов (нужны HEX коды)")
        
        # Проверка шаблонных фраз
        template_count = self._count_template_phrases(tz_text)
        if template_count > 3:
            warnings.append(f"Много шаблонных фраз: {template_count}")
        
        # Проверка качественных индикаторов
        quality_count = self._count_quality_indicators(tz_text)
        
        # Расчёт оценки
        score = self._calculate_score(
            tz_text=tz_text,
            found_sections=found_sections,
            hex_colors_count=len(hex_colors),
            template_count=template_count,
            quality_count=quality_count,
        )
        
        # Определяем валидность
        # ТЗ считается валидным если:
        # - Не более 1 пропущенной секции
        # - Длина >= 80% от минимума
        # - Score >= 60
        is_valid = (
            len(missing_sections) <= 1 and
            len(tz_text) >= self.min_length * 0.8 and
            score >= 60
        )
        
        result = ValidationResult(
            is_valid=is_valid,
            score=score,
            found_sections=found_sections,
            missing_sections=missing_sections,
            warnings=warnings,
        )
        
        logger.debug(
            "Validation completed",
            is_valid=is_valid,
            score=score,
            found_sections=len(found_sections),
            missing_sections=len(missing_sections),
        )
        
        return result
    
    def _check_sections(self, text: str) -> Tuple[List[str], List[str]]:
        """
        Проверить наличие обязательных секций.
        
        Args:
            text: Текст ТЗ
            
        Returns:
            Tuple: (найденные секции, пропущенные секции)
        """
        text_lower = text.lower()
        found = []
        missing = []
        
        for section, pattern in self.SECTION_PATTERNS.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                found.append(section)
            else:
                missing.append(section)
        
        return found, missing
    
    def _count_template_phrases(self, text: str) -> int:
        """Подсчитать количество шаблонных фраз."""
        text_lower = text.lower()
        return sum(
            1 for phrase in self.TEMPLATE_PHRASES
            if phrase.lower() in text_lower
        )
    
    def _count_quality_indicators(self, text: str) -> int:
        """Подсчитать количество качественных индикаторов."""
        count = 0
        for pattern in self.QUALITY_INDICATORS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            count += len(matches)
        return count
    
    def _calculate_score(
        self,
        tz_text: str,
        found_sections: List[str],
        hex_colors_count: int,
        template_count: int,
        quality_count: int,
    ) -> int:
        """
        Рассчитать оценку качества (0-100).
        
        Формула:
        - 50% — наличие секций
        - 25% — длина текста
        - 15% — конкретные детали (цвета, размеры)
        - 10% — отсутствие шаблонных фраз
        """
        total_sections = len(self.SECTION_PATTERNS)
        
        # Секции (50 баллов макс)
        section_score = (len(found_sections) / total_sections) * 50
        
        # Длина (25 баллов макс)
        length_ratio = min(len(tz_text) / self.min_length, 1.5)
        length_score = min(length_ratio * 16.7, 25)
        
        # Детали (15 баллов макс)
        # HEX цвета + качественные индикаторы
        detail_score = min(hex_colors_count * 2 + quality_count * 1, 15)
        
        # Без шаблонов (10 баллов макс)
        template_penalty = min(template_count * 2.5, 10)
        template_score = 10 - template_penalty
        
        total = int(section_score + length_score + detail_score + template_score)
        return max(0, min(100, total))


def validate_tz(tz_text: str) -> ValidationResult:
    """
    Удобная функция для быстрой валидации.
    
    Args:
        tz_text: Текст ТЗ
        
    Returns:
        ValidationResult: Результат валидации
    """
    validator = TZValidator()
    return validator.validate(tz_text)
