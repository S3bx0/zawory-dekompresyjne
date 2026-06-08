# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — buduje jeden plik .exe dla Windows.

Użycie:
    pip install -e ".[build]"
    pyinstaller zawory_dekompresyjne.spec --clean --noconfirm

Artefakt: dist/ZaworyDekompresyjne.exe  (standalone, bez konsoli).
"""
from pathlib import Path

BASE = Path(SPECPATH).resolve()           # noqa: F821  (wstrzykiwane przez PyInstaller)
RES = BASE / "resources"

# Wszystkie pliki z resources/ pakujemy do ./resources/ wewnątrz .exe.
_datas = [(str(p), "resources") for p in RES.glob("*") if p.is_file()]

block_cipher = None


a = Analysis(                              # noqa: F821
    ["gui.py"],
    pathex=[str(BASE)],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        # ttkbootstrap ładuje tematy dynamicznie
        "ttkbootstrap",
        "ttkbootstrap.themes.standard",
        # cryptography backend wymagany przez pypdf dla AES-256
        "cryptography",
        "cryptography.hazmat.backends.openssl",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Nie pakuj narzędzi deweloperskich
        "pytest",
        "tkinter.test",
        "unittest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)   # noqa: F821

exe = EXE(                                              # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ZaworyDekompresyjne",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,              # GUI bez okna konsoli
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(RES / "icon.ico") if (RES / "icon.ico").exists() else None,
)
