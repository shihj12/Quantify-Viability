# PyInstaller spec for Quantify Viability — one-folder Windows build.
# Build with:  build_exe.bat   (or:  pyinstaller quantify_viability.spec)
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

_icon = "assets/icon.ico" if os.path.exists("assets/icon.ico") else None

# scikit-image loads submodules lazily — collect them explicitly.
hiddenimports = collect_submodules("skimage")
datas = collect_data_files("skimage") + collect_data_files("pyqtgraph")

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "tkinter", "PyQt5", "PyQt6", "PySide2"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QuantifyViability",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="QuantifyViability",
)
