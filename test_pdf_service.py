"""Testy integracyjne dla pdf_service — generacja, metadane, szyfrowanie."""
from __future__ import annotations

import pathlib
import pytest
from pypdf import PdfReader

import pdf_service
from obliczenia import calculate_decompression_valves


@pytest.fixture(scope="module")
def generated_pdf(tmp_path_factory) -> pathlib.Path:
    """Generuje jeden PDF raz na moduł — wielokrotnie odczytywany w testach."""
    out_dir = tmp_path_factory.mktemp("pdfs")
    dst = out_dir / "raport.pdf"

    V, tp, tz, ic, F = 150.0, -25.0, -27.0, 2, 12500.0
    result = calculate_decompression_valves(V, tp, tz, F * ic)

    pdf_service.generate_pdf(
        pdf_path=str(dst),
        result=result,
        V=V,
        temp_przed=tp,
        temp_za=tz,
        ilosc_chlodnic=ic,
        F_total=F * ic,
        owner_password="test-owner-pwd",
    )
    assert dst.exists(), "Plik PDF nie powstał"
    return dst


def test_pdf_file_is_non_empty(generated_pdf: pathlib.Path):
    assert generated_pdf.stat().st_size > 1000, "PDF jest podejrzanie mały"


def test_pdf_is_encrypted(generated_pdf: pathlib.Path):
    reader = PdfReader(str(generated_pdf))
    assert reader.is_encrypted, "PDF powinien być zaszyfrowany"


def test_pdf_has_exactly_one_page(generated_pdf: pathlib.Path):
    reader = PdfReader(str(generated_pdf))
    # Domyślne hasło użytkownika = "" (puste) — AES-256 + pusty user pwd.
    reader.decrypt("")
    assert len(reader.pages) == 1, f"Oczekiwano 1 strony, jest {len(reader.pages)}"


def test_pdf_contains_valve_model_text(generated_pdf: pathlib.Path):
    reader = PdfReader(str(generated_pdf))
    reader.decrypt("")
    text = reader.pages[0].extract_text() or ""
    assert "Maxi Elebar" in text, (
        f"W treści PDF brak nazwy modelu zaworu. Fragment: {text[:200]!r}"
    )


def test_pdf_owner_password_unlocks(tmp_path: pathlib.Path):
    """Owner password musi dawać pełny dostęp (odczyt + metadane)."""
    dst = tmp_path / "owner.pdf"
    V, tp, tz, F = 100.0, -20.0, -24.0, 10000.0
    result = calculate_decompression_valves(V, tp, tz, F)
    pdf_service.generate_pdf(
        pdf_path=str(dst), result=result, V=V, temp_przed=tp, temp_za=tz,
        ilosc_chlodnic=1, F_total=F, owner_password="strong-owner",
    )
    reader = PdfReader(str(dst))
    assert reader.is_encrypted
    # Zarówno user (puste) jak i owner powinny działać.
    assert reader.decrypt("strong-owner") != 0
