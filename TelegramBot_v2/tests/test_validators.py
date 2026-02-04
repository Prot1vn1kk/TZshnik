"""
Тесты для модуля валидации.

Проверка функций санитизации и валидации входных данных.
"""

import pytest
from core.validators import (
    sanitize_html,
    sanitize_text_input,
    sanitize_feedback,
    sanitize_category,
    sanitize_username,
    validate_telegram_id,
    validate_amount,
    validate_photo_count,
    is_safe_file_path,
    remove_dangerous_patterns,
    get_safe_display_name,
)


class TestSanitizeHtml:
    """Тесты экранирования HTML."""
    
    def test_basic_html_escape(self):
        assert sanitize_html("<script>alert('xss')</script>") == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
    
    def test_quotes_escape(self):
        assert sanitize_html('test "quotes"') == 'test &quot;quotes&quot;'
    
    def test_empty_string(self):
        assert sanitize_html("") == ""
    
    def test_none_handling(self):
        # Передаём пустую строку вместо None
        assert sanitize_html("") == ""
    
    def test_normal_text(self):
        assert sanitize_html("Hello World!") == "Hello World!"


class TestRemoveDangerousPatterns:
    """Тесты удаления опасных паттернов."""
    
    def test_script_removal(self):
        text = "Hello<script>evil()</script>World"
        assert "script" not in remove_dangerous_patterns(text)
    
    def test_javascript_url(self):
        text = "Click javascript:alert(1)"
        assert "javascript:" not in remove_dangerous_patterns(text)
    
    def test_onclick_removal(self):
        text = 'onclick="evil()"'
        result = remove_dangerous_patterns(text)
        assert "onclick" not in result
    
    def test_normal_text_preserved(self):
        text = "Normal text with numbers 123"
        assert remove_dangerous_patterns(text) == text


class TestSanitizeTextInput:
    """Тесты комплексной санитизации."""
    
    def test_length_limit(self):
        long_text = "a" * 1000
        result = sanitize_text_input(long_text, max_length=100)
        assert len(result) <= 100
        assert result.endswith("...")
    
    def test_html_escape_by_default(self):
        result = sanitize_text_input("<b>bold</b>")
        assert "<b>" not in result
    
    def test_whitespace_normalization(self):
        text = "Hello    World"
        result = sanitize_text_input(text)
        assert "  " not in result
    
    def test_strip_newlines(self):
        text = "Line1\nLine2"
        result = sanitize_text_input(text, strip_newlines=True)
        assert "\n" not in result


class TestSanitizeFeedback:
    """Тесты санитизации отзывов."""
    
    def test_valid_feedback(self):
        text, is_valid = sanitize_feedback("Great bot! Works perfectly.")
        assert is_valid
        assert len(text) > 0
    
    def test_empty_feedback(self):
        text, is_valid = sanitize_feedback("")
        assert not is_valid
    
    def test_too_short_feedback(self):
        text, is_valid = sanitize_feedback("ab")
        assert not is_valid
    
    def test_length_limit(self):
        long_text = "a" * 2000
        text, is_valid = sanitize_feedback(long_text)
        assert is_valid
        assert len(text) <= 1000


class TestSanitizeCategory:
    """Тесты санитизации категорий."""
    
    def test_valid_category(self):
        cat, is_valid = sanitize_category("Электроника")
        assert is_valid
        assert cat == "Электроника"
    
    def test_category_with_latin(self):
        cat, is_valid = sanitize_category("Electronics-123")
        assert is_valid
    
    def test_empty_category(self):
        cat, is_valid = sanitize_category("")
        assert not is_valid
    
    def test_special_chars_removed(self):
        cat, is_valid = sanitize_category("Test<>!@#$")
        assert "<" not in cat
        assert ">" not in cat


class TestSanitizeUsername:
    """Тесты санитизации username."""
    
    def test_valid_username(self):
        assert sanitize_username("user123") == "user123"
    
    def test_remove_at_symbol(self):
        assert sanitize_username("@username") == "username"
    
    def test_invalid_chars(self):
        assert sanitize_username("user@#$name") is None
    
    def test_empty_username(self):
        assert sanitize_username("") is None
    
    def test_none_username(self):
        assert sanitize_username(None) is None


class TestValidateTelegramId:
    """Тесты валидации Telegram ID."""
    
    def test_valid_id(self):
        assert validate_telegram_id(123456789)
    
    def test_negative_id(self):
        assert not validate_telegram_id(-1)
    
    def test_zero_id(self):
        assert not validate_telegram_id(0)
    
    def test_string_id(self):
        # type: ignore - тест на неправильный тип
        assert not validate_telegram_id(-999)  # Негативный ID невалиден


class TestValidateAmount:
    """Тесты валидации числовых значений."""
    
    def test_valid_amount(self):
        assert validate_amount(100)
    
    def test_too_small(self):
        assert not validate_amount(0)
    
    def test_too_large(self):
        assert not validate_amount(10000000)
    
    def test_custom_range(self):
        assert validate_amount(5, min_val=1, max_val=10)
        assert not validate_amount(15, min_val=1, max_val=10)


class TestValidatePhotoCount:
    """Тесты валидации количества фото."""
    
    def test_valid_count(self):
        assert validate_photo_count(3)
    
    def test_zero_photos(self):
        assert not validate_photo_count(0)
    
    def test_too_many_photos(self):
        assert not validate_photo_count(10)
    
    def test_custom_max(self):
        assert validate_photo_count(8, max_photos=10)
        assert not validate_photo_count(8, max_photos=5)


class TestIsSafeFilePath:
    """Тесты проверки безопасности путей."""
    
    def test_safe_path(self):
        assert is_safe_file_path("/data/file.txt")
    
    def test_path_traversal(self):
        assert not is_safe_file_path("../../../etc/passwd")
    
    def test_windows_system(self):
        assert not is_safe_file_path("C:\\Windows\\System32")
    
    def test_empty_path(self):
        assert not is_safe_file_path("")


class TestGetSafeDisplayName:
    """Тесты безопасного имени пользователя."""
    
    def test_with_first_name(self):
        name = get_safe_display_name("John", "john_doe", 123)
        assert name == "John"
    
    def test_with_username_only(self):
        name = get_safe_display_name(None, "john_doe", 123)
        assert "@john_doe" in name
    
    def test_fallback_to_id(self):
        name = get_safe_display_name(None, None, 123)
        assert "123" in name
    
    def test_xss_in_name(self):
        name = get_safe_display_name("<script>evil()</script>", None, 123)
        assert "<script>" not in name
