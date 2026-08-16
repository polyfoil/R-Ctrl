# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — R-Ctrl widget (one-folder). Run: packaging/build_widget.ps1"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPEC).resolve().parent.parent

_EXCLUDES = [
    "torch",
    "transformers",
    "onnx",
    "tensorflow",
    "gradio",
    "fastapi",
    "uvicorn",
    "pandas",
    "matplotlib",
    "pytest",
    "sklearn",
    "scipy",
    "rctrl_server",
    "rctrl",
]

a = Analysis(
    [str(ROOT / "launch_widget.py")],
    pathex=[str(ROOT)],
    binaries=collect_dynamic_libs("ctranslate2"),
    datas=collect_data_files("faster_whisper"),
    hiddenimports=[
        "sounddevice",
        "_sounddevice_data",
        "keyboard",
        "pyperclip",
        "onnxruntime",
        "faster_whisper",
        "ctranslate2",
        "ui.brand",
        "ui.i18n",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDES,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="R-Ctrl-Whisperer",
    debug=False,
    console=False,
    uac_admin=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="R-Ctrl-Whisperer",
)
