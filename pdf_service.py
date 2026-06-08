"""Serwis generowania, watermarkowania i szyfrowania plików PDF."""
from __future__ import annotations

import logging
import os
import pathlib
import tempfile
import warnings
from typing import Optional

from pypdf import PdfReader, PdfWriter

from reportlab.lib.colors import black, grey, lightgrey
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from obliczenia import CalculationResult

_BASE_DIR = pathlib.Path(__file__).resolve().parent
_logger = logging.getLogger(__name__)

# ── Czcionka (najpierw resources/ obok modułu, fallback do lokalizacji autora) ─
_FONT_CANDIDATES = [
    _BASE_DIR / "resources" / "DejaVuSans.ttf",
    _BASE_DIR.parent / "TPOF" / "dejavu-fonts-ttf-2.37" / "ttf" / "DejaVuSans.ttf",
]
FONT_NAME = "DejaVuSans"
FONT_AVAILABLE = False
for _candidate in _FONT_CANDIDATES:
    try:
        if _candidate.exists():
            pdfmetrics.registerFont(TTFont(FONT_NAME, str(_candidate)))
            FONT_AVAILABLE = True
            break
    except Exception:  # pragma: no cover
        continue

if not FONT_AVAILABLE:
    FONT_NAME = "Helvetica"
    warnings.warn(
        "Nie znaleziono czcionki DejaVuSans. PDF użyje Helvetica — polskie znaki "
        "mogą być renderowane niepoprawnie."
    )

# ── Ścieżki ────────────────────────────────────────────────────────────────
_WATERMARK_CANDIDATES = [
    _BASE_DIR / "resources" / "watermark.png",
    _BASE_DIR / "resources" / "PUCH.TIF",
    _BASE_DIR.parent.parent / "_Logo" / "PUCH (300ppi) - TIFF.TIF",
]


def _find_watermark() -> Optional[str]:
    for p in _WATERMARK_CANDIDATES:
        if p.exists():
            return str(p)
    return None


WATERMARK_PATH: Optional[str] = _find_watermark()
AUTHOR_TEXT = "Autor:\nSebastian Milczarek\nMD-Puch Sp. z o.o."

# Hasło właściciela PDF (chroni przed edycją, nie przed otwarciem).
PDF_PASSWORD: Optional[str] = os.environ.get("PDF_OWNER_PASSWORD")
if not PDF_PASSWORD:
    warnings.warn(
        "Zmienna środowiskowa PDF_OWNER_PASSWORD nie jest ustawiona. "
        "PDF nie będzie chroniony hasłem właściciela.",
        stacklevel=1,
    )


# ── Formatowanie wyników ──────────────────────────────────────────────────
def format_result_rows(
    result: CalculationResult,
    V: float,
    temp_przed: float,
    temp_za: float,
    ilosc_chlodnic: int,
    F_total: float,
) -> list[list[str]]:
    """Zamienia obiekt wyniku na listę par [label, value] dla tabeli PDF."""
    return [
        ["Objętość V", f"{V:.2f} m³"],
        ["Temperatura przed chłodnicą", f"{temp_przed:.2f} °C"],
        ["Temperatura za chłodnicą", f"{temp_za:.2f} °C"],
        ["Ilość chłodnic", f"{ilosc_chlodnic}"],
        ["Przepływ całkowity F", f"{F_total:.2f} m³/h"],
        ["Dynamika komory ΔT", f"{result.delta_T:.2f} °C/min"],
        ["Wymagany przepływ Q", f"{result.Q:.2f} l/min"],
        ["Typ zaworu", f"{result.typ_zaworu} ({result.przeplyw_zaworu} l/min)"],
        ["Ilość zaworów", f"{result.ilosc_zaworow} szt."],
    ]


# ── Rysowanie stron (znak wodny + numer strony) ───────────────────────────
def _draw_page_furniture(c: canvas.Canvas, doc, watermark_path: Optional[str]) -> None:
    c.saveState()
    if watermark_path:
        try:
            img = ImageReader(watermark_path)
            iw, ih = img.getSize()
            pw, ph = doc.pagesize
            scale = min(pw / iw, ph / ih) * 0.8
            w, h = iw * scale, ih * scale
            x = (pw - w) / 2
            y = (ph - h) / 2
            c.setFillAlpha(0.12)
            c.drawImage(
                img, x, y, width=w, height=h, mask="auto",
                preserveAspectRatio=True,
            )
            c.setFillAlpha(1.0)
        except Exception:
            _logger.warning(
                "Nie udało się nałożyć znaku wodnego: %s",
                watermark_path, exc_info=True,
            )
    c.setFont(FONT_NAME, 9)
    pw, _ph = doc.pagesize
    c.drawRightString(pw - 2 * cm, 1.2 * cm, f"Strona {c.getPageNumber()}")
    c.restoreState()


def generate_pdf(
    pdf_path: str,
    result: CalculationResult,
    V: float,
    temp_przed: float,
    temp_za: float,
    ilosc_chlodnic: int,
    F_total: float,
    *,
    watermark_path: Optional[str] = None,
    owner_password: Optional[str] = None,
) -> str:
    """
    Generuje raport PDF w jednym kroku (znak wodny + szyfrowanie).
    Zapis atomowy przez plik tymczasowy. Zwraca ścieżkę docelową.
    """
    if watermark_path is None:
        watermark_path = WATERMARK_PATH

    _styles = getSampleStyleSheet()  # noqa: F841 (inicjalizacja stylów domyślnych)
    title_style = ParagraphStyle(
        name="TitleStyle", fontName=FONT_NAME, fontSize=16,
        alignment=TA_CENTER, spaceAfter=18,
    )
    author_style = ParagraphStyle(
        name="AuthorStyle", fontName=FONT_NAME, fontSize=10,
        alignment=TA_CENTER, textColor=black, spaceBefore=24,
    )
    note_style = ParagraphStyle(
        name="NoteStyle", fontName=FONT_NAME, fontSize=8,
        alignment=TA_LEFT, textColor=grey, spaceBefore=6,
    )

    story = [
        Paragraph("Wyniki obliczeń zaworów dekompresyjnych", title_style),
        Spacer(1, 12),
    ]
    rows = format_result_rows(result, V, temp_przed, temp_za, ilosc_chlodnic, F_total)
    table = Table(rows, colWidths=[7 * cm, 9 * cm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (0, -1), lightgrey),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Paragraph(
        "Wynik zaokrąglony do pełnej liczby zaworów w górę (math.ceil). "
        "Wartości pośrednie (ΔT, Q) liczone bez zaokrągleń, prezentowane z 2 miejscami.",
        note_style,
    ))
    story.append(Paragraph(AUTHOR_TEXT.replace("\n", "<br/>"), author_style))

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(tmp_fd)
    try:
        doc = SimpleDocTemplate(
            tmp_path, pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm, bottomMargin=2 * cm,
            title="Raport zaworów dekompresyjnych",
            author="MD-Puch",
        )

        def _on_page(c, d):
            _draw_page_furniture(c, d, watermark_path)

        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)

        if owner_password is None:
            owner_password = PDF_PASSWORD
        _encrypt_and_move(tmp_path, pdf_path, owner_password)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return pdf_path


def _encrypt_and_move(src: str, dst: str, owner_password: Optional[str]) -> None:
    """
    Dodaje szyfrowanie owner (AES-256 jeśli dostępne) i atomowo zastępuje plik docelowy.
    Jeśli owner_password jest None/pusty — zapisuje bez szyfrowania.
    """
    reader = PdfReader(src)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    if owner_password:
        _apply_encryption(writer, owner_password)

    # Plik tymczasowy tworzony w katalogu docelowym — zapewnia że os.replace()
    # działa na tym samym wolumenie (inaczej [WinError 17] na Windows).
    dst_dir = os.path.dirname(os.path.abspath(dst)) or "."
    tmp_fd, tmp_out = tempfile.mkstemp(suffix=".pdf", dir=dst_dir)
    try:
        with os.fdopen(tmp_fd, "wb") as fh:
            writer.write(fh)
        os.replace(tmp_out, dst)
    except Exception:
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except OSError:
                pass
        raise


def _apply_encryption(writer: PdfWriter, owner_password: str) -> None:
    """
    Nakłada szyfrowanie na writer pypdf.
    Pozwolenia: druk + dostępność (extract for accessibility).
    Blokada: edycja treści i formularzy.
    """
    try:
        from pypdf.constants import UserAccessPermissions as _UAP
        permissions = (
            _UAP.PRINT
            | _UAP.PRINT_TO_REPRESENTATION
            | _UAP.EXTRACT_FOR_ACCESSIBILITY
        )
    except Exception:
        permissions = -1  # pypdf: -1 = default pozwolenia

    for algo in ("AES-256", "AES-128", "RC4-128"):
        try:
            writer.encrypt(
                user_password="",
                owner_password=owner_password,
                permissions_flag=permissions,
                algorithm=algo,
            )
            return
        except (TypeError, ValueError, NotImplementedError):
            continue
    # Ostateczny fallback — bez parametrów dodatkowych
    writer.encrypt(user_password="", owner_password=owner_password)


# ── Kompatybilność wsteczna (deprecated) ──────────────────────────────────
def add_watermark(pdf_path: str, watermark_path: str, results_text: str) -> str:  # pragma: no cover
    """Deprecated — użyj generate_pdf()."""
    warnings.warn(
        "add_watermark() jest deprecated. Użyj generate_pdf(result=...).",
        DeprecationWarning, stacklevel=2,
    )
    data_lines = [line for line in results_text.split("\n") if line.strip()]
    rows = []
    for line in data_lines:
        parts = line.split(" = ", 1)
        rows.append(parts if len(parts) == 2 else [line, ""])

    title_style = ParagraphStyle(
        name="TitleStyle", fontName=FONT_NAME, fontSize=16, alignment=TA_CENTER,
    )
    story = [
        Paragraph("Wyniki obliczeń zaworów dekompresyjnych", title_style),
        Spacer(1, 18),
    ]
    tbl = Table(rows, colWidths=[7 * cm, 9 * cm])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, grey),
    ]))
    story.append(tbl)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(tmp_fd)
    try:
        doc = SimpleDocTemplate(
            tmp_path, pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm, bottomMargin=2 * cm,
        )
        doc.build(
            story,
            onFirstPage=lambda c, d: _draw_page_furniture(c, d, watermark_path),
            onLaterPages=lambda c, d: _draw_page_furniture(c, d, watermark_path),
        )
        os.replace(tmp_path, pdf_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    return pdf_path


def add_password_to_pdf(input_path: str, output_path: str, password: Optional[str]) -> None:
    """Deprecated — użyj generate_pdf(owner_password=...)."""
    warnings.warn(
        "add_password_to_pdf() jest deprecated. Użyj generate_pdf(owner_password=...).",
        DeprecationWarning, stacklevel=2,
    )
    _encrypt_and_move(input_path, output_path, password)
