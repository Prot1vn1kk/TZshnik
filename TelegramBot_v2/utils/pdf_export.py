"""
PDF экспорт технических заданий.

Использует reportlab для создания PDF с поддержкой кириллицы.
В качестве fallback использует fpdf2 или текстовый файл.
"""

import io
import re
from pathlib import Path
from datetime import datetime
from typing import Optional
import urllib.request

import structlog


logger = structlog.get_logger()


# Категории на русском
CATEGORY_NAMES = {
    "clothes": "Одежда и аксессуары",
    "electronics": "Электроника",
    "cosmetics": "Косметика и уход",
    "home": "Товары для дома",
    "kids": "Детские товары",
    "sports": "Спорт и отдых",
    "other": "Другое",
}

# Путь для хранения шрифтов
FONTS_DIR = Path(__file__).parent.parent / "data" / "fonts"


def clean_text_for_pdf(text: str) -> str:
    """
    Очищает текст от markdown для PDF.
    
    Args:
        text: Исходный текст с markdown
        
    Returns:
        str: Очищенный текст
    """
    # Убираем markdown заголовки (## Заголовок -> ЗАГОЛОВОК)
    text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)
    
    # Убираем bold/italic маркеры
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    
    # Убираем ссылки [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Убираем code блоки
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Преобразуем markdown списки
    text = re.sub(r'^[-*+]\s+', '• ', text, flags=re.MULTILINE)
    
    # Убираем горизонтальные линии markdown
    text = re.sub(r'^---+$', '─' * 40, text, flags=re.MULTILINE)
    text = re.sub(r'^\*\*\*+$', '─' * 40, text, flags=re.MULTILINE)
    
    return text.strip()


def ensure_fonts() -> bool:
    """Скачивает шрифты если нужно."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)

    # Используем CDN для более надёжной загрузки шрифтов
    urls = {
        "DejaVuSans.ttf": "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf": "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans-Bold.ttf",
    }

    for font_name, url in urls.items():
        font_path = FONTS_DIR / font_name
        if not font_path.exists():
            try:
                logger.info(f"Downloading font {font_name}...")
                urllib.request.urlretrieve(url, font_path)
                logger.info(f"Font {font_name} downloaded")
            except (urllib.error.URLError, urllib.error.HTTPError) as e:
                logger.error(
                    f"Failed to download {font_name}",
                    error_type="URLError",
                    error=str(e),
                )
                return False
            except OSError as e:
                logger.error(
                    f"Failed to save {font_name}",
                    error_type="OSError",
                    error=str(e),
                )
                return False
    return True


class ReportLabPDFExporter:
    """
    Экспорт ТЗ в PDF с использованием reportlab.
    Основной метод экспорта с полной поддержкой кириллицы.
    """
    
    def __init__(self):
        """Инициализация экспортера."""
        self._available = False
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            self._available = True
        except ImportError:
            logger.warning("reportlab not installed")
    
    def is_available(self) -> bool:
        return self._available
    
    async def export(
        self,
        tz_text: str,
        category: str,
        generation_id: int,
        created_at: Optional[datetime] = None,
    ) -> bytes:
        """Экспортирует ТЗ в PDF."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib import colors

        if created_at is None:
            created_at = datetime.now()

        # Регистрируем шрифты
        font_name = "Helvetica"
        font_bold = "Helvetica-Bold"

        if ensure_fonts():
            try:
                if "DejaVuSans" not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont("DejaVuSans", str(FONTS_DIR / "DejaVuSans.ttf")))
                    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(FONTS_DIR / "DejaVuSans-Bold.ttf")))
                font_name = "DejaVuSans"
                font_bold = "DejaVuSans-Bold"
            except (OSError, IOError) as e:
                logger.error(
                    "Failed to register fonts",
                    error_type="FontError",
                    error=str(e),
                )

        # Создаём PDF в памяти
        buffer = io.BytesIO()

        # Создаём документ
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm,
        )

        # Стили
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontName=font_bold,
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=10,
        )

        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=12,
            alignment=TA_CENTER,
            textColor=colors.gray,
            spaceAfter=5,
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName=font_bold,
            fontSize=14,
            spaceBefore=15,
            spaceAfter=8,
        )

        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            leading=14,
            spaceAfter=3,
        )

        bullet_style = ParagraphStyle(
            'CustomBullet',
            parent=body_style,
            leftIndent=15,
        )

        footer_style = ParagraphStyle(
            'CustomFooter',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=9,
            alignment=TA_CENTER,
            textColor=colors.gray,
        )

        # Собираем контент
        story = []

        # Заголовок
        category_name = CATEGORY_NAMES.get(category, category)
        story.append(Paragraph(f"Техническое задание #{generation_id}", title_style))
        story.append(Paragraph(f"Категория: {category_name}", subtitle_style))
        story.append(Paragraph(f"Дата: {created_at.strftime('%d.%m.%Y %H:%M')}", subtitle_style))
        story.append(Spacer(1, 15))

        # Разделитель
        story.append(Paragraph("─" * 60, body_style))
        story.append(Spacer(1, 10))

        # Очищаем текст
        clean_text = clean_text_for_pdf(tz_text)

        # Парсим и добавляем контент
        lines = clean_text.split("\n")
        for line in lines:
            line = line.strip()

            if not line:
                story.append(Spacer(1, 5))
                continue

            # Экранируем HTML-подобные символы для Paragraph
            safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            # Определяем тип строки
            if line.startswith("━") or line.startswith("─"):
                story.append(Paragraph("─" * 60, body_style))
            elif line.isupper() and len(line) < 50 and len(line) > 3:
                # Заголовок секции (всё заглавными)
                story.append(Paragraph(safe_line, heading_style))
            elif line.startswith("• ") or line.startswith("- "):
                # Маркированный список
                bullet_text = safe_line[2:] if line.startswith("• ") else safe_line[2:]
                story.append(Paragraph(f"• {bullet_text}", bullet_style))
            else:
                story.append(Paragraph(safe_line, body_style))

        # Футер
        story.append(Spacer(1, 20))
        story.append(Paragraph("─" * 60, body_style))
        story.append(Paragraph("Создано в ТЗшник — генератор ТЗ для маркетплейсов", footer_style))

        # Генерируем PDF
        try:
            doc.build(story)
        except (ValueError, TypeError) as e:
            logger.error(
                "PDF build failed",
                error_type="BuildError",
                error=str(e),
                generation_id=generation_id,
            )
            raise

        return buffer.getvalue()


class FPDF2Exporter:
    """
    Fallback экспортер на базе fpdf2.
    Используется если reportlab недоступен.
    """
    
    def __init__(self):
        self._available = False
        try:
            from fpdf import FPDF
            self._available = True
        except ImportError:
            logger.warning("fpdf2 not installed")
    
    def is_available(self) -> bool:
        return self._available
    
    async def export(
        self,
        tz_text: str,
        category: str,
        generation_id: int,
        created_at: Optional[datetime] = None,
    ) -> bytes:
        """Экспортирует ТЗ в PDF."""
        from fpdf import FPDF
        
        if created_at is None:
            created_at = datetime.now()
        
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Загружаем шрифты
        font_name = "helvetica"
        if ensure_fonts():
            try:
                pdf.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
                pdf.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
                font_name = "DejaVu"
            except (OSError, RuntimeError) as e:
                logger.error(
                    "Failed to load fonts",
                    error_type="FontLoadError",
                    error=str(e),
                )
        
        pdf.add_page()
        
        # Заголовок
        pdf.set_font(font_name, "B", 16)
        pdf.cell(0, 10, f"Техническое задание #{generation_id}", ln=True, align="C")
        
        # Категория
        category_name = CATEGORY_NAMES.get(category, category)
        pdf.set_font(font_name, "", 12)
        pdf.cell(0, 8, f"Категория: {category_name}", ln=True, align="C")
        
        # Дата
        pdf.set_font(font_name, "", 10)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 6, f"Дата: {created_at.strftime('%d.%m.%Y %H:%M')}", ln=True, align="C")
        pdf.set_text_color(0, 0, 0)
        
        # Разделитель
        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        # Основной текст
        pdf.set_font(font_name, "", 10)
        clean_text = clean_text_for_pdf(tz_text)
        
        lines = clean_text.split("\n")
        for line in lines:
            line = line.strip()
            
            if not line:
                pdf.ln(3)
                continue
            
            try:
                if line.startswith("━") or line.startswith("─"):
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                    pdf.ln(3)
                elif line.isupper() and len(line) < 50 and len(line) > 3:
                    pdf.ln(5)
                    pdf.set_font(font_name, "B", 12)
                    pdf.multi_cell(0, 6, line)
                    pdf.set_font(font_name, "", 10)
                elif line.startswith("• "):
                    pdf.multi_cell(0, 5, f"   {line}")
                else:
                    pdf.multi_cell(0, 5, line)
            except (ValueError, RuntimeError) as e:
                logger.warning(
                    "Failed to render line",
                    error_type="RenderError",
                    error=str(e),
                    line_preview=line[:50],
                )
                continue
        
        # Футер
        pdf.ln(10)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font(font_name, "", 9)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 5, "Создано в ТЗшник — генератор ТЗ для маркетплейсов", align="C")
        
        # Сохраняем - fpdf2 возвращает bytes напрямую
        return bytes(pdf.output())


class TextExporter:
    """
    Fallback экспорт в текстовый файл.
    Используется если PDF библиотеки недоступны.
    """
    
    def is_available(self) -> bool:
        return True
    
    async def export(
        self,
        tz_text: str,
        category: str,
        generation_id: int,
        created_at: Optional[datetime] = None,
    ) -> bytes:
        """Экспортирует ТЗ в текстовый файл."""
        if created_at is None:
            created_at = datetime.now()
        
        category_name = CATEGORY_NAMES.get(category, category)
        clean_text = clean_text_for_pdf(tz_text)
        
        content = f"""{'=' * 60}
ТЕХНИЧЕСКОЕ ЗАДАНИЕ #{generation_id}
Категория: {category_name}
Дата: {created_at.strftime('%d.%m.%Y %H:%M')}
{'=' * 60}

{clean_text}

{'=' * 60}
Создано в ТЗшник — генератор ТЗ для маркетплейсов
"""
        return content.encode("utf-8")


class PDFExporter:
    """
    Главный класс экспорта PDF.
    Автоматически выбирает лучший доступный метод.
    """
    
    def __init__(self):
        self._reportlab = ReportLabPDFExporter()
        self._fpdf = FPDF2Exporter()
        self._text = TextExporter()
        
        # Определяем какой экспортер использовать
        if self._reportlab.is_available():
            self._primary = self._reportlab
            logger.info("Using reportlab for PDF export")
        elif self._fpdf.is_available():
            self._primary = self._fpdf
            logger.info("Using fpdf2 for PDF export")
        else:
            self._primary = self._text
            logger.warning("No PDF library available, using text export")
    
    async def export_tz(
        self,
        tz_text: str,
        category: str,
        generation_id: int,
        created_at: Optional[datetime] = None,
    ) -> bytes:
        """
        Экспортирует ТЗ в PDF или текстовый файл.
        
        Args:
            tz_text: Текст технического задания
            category: Категория товара
            generation_id: ID генерации
            created_at: Дата создания
            
        Returns:
            bytes: Файл в байтах
        """
        try:
            return await self._primary.export(
                tz_text=tz_text,
                category=category,
                generation_id=generation_id,
                created_at=created_at,
            )
        except Exception as e:
            logger.error(f"Primary export failed: {e}")
            
            # Fallback to next available
            if self._primary != self._fpdf and self._fpdf.is_available():
                try:
                    logger.info("Trying fpdf2 fallback...")
                    return await self._fpdf.export(
                        tz_text=tz_text,
                        category=category,
                        generation_id=generation_id,
                        created_at=created_at,
                    )
                except Exception as e2:
                    logger.error(f"FPDF2 fallback failed: {e2}")
            
            # Final fallback to text
            try:
                logger.info("Falling back to text export...")
                return await self._text.export(
                    tz_text=tz_text,
                    category=category,
                    generation_id=generation_id,
                    created_at=created_at,
                )
            except Exception as e3:
                logger.error(f"Text export also failed: {e3}")
                raise


# Синглтон экспортера
pdf_exporter = PDFExporter()


async def export_generation_to_pdf(
    tz_text: str,
    category: str,
    generation_id: int,
    created_at: Optional[datetime] = None,
) -> bytes:
    """
    Функция-обёртка для экспорта в PDF.
    
    Args:
        tz_text: Текст ТЗ
        category: Категория товара
        generation_id: ID генерации
        created_at: Дата создания
        
    Returns:
        bytes: PDF файл
    """
    return await pdf_exporter.export_tz(
        tz_text=tz_text,
        category=category,
        generation_id=generation_id,
        created_at=created_at,
    )
