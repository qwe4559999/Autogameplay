# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path.cwd()
datas = [
    (str(project_root / "config"), "config"),
    (str(project_root / "ui" / "resources"), "ui/resources"),
]
hiddenimports = [
    "plugins.maa_arknights.adapter",
    "plugins.maaend_endfield.adapter",
    "plugins.okww_wutheringwaves.adapter",
]
excludes = [
    "IPython",
    "PIL.ImageQt",
    "jupyter",
    "lxml",
    "matplotlib",
    "networkx",
    "openpyxl",
    "pandas",
    "pytest",
    "scipy",
    "sqlalchemy",
    "sympy",
    "tensorboard",
    "tensorflow",
    "torch",
    "torchaudio",
    "torchvision",
]


a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoGamePlay",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AutoGamePlay",
)
