# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for Driver Docs Extractor
#
# Build command (run from this directory on Windows):
#   pip install -r requirements.txt
#   pip install pyinstaller
#   pyinstaller gui.spec

from PyInstaller.utils.hooks import collect_all

striprtf_datas, striprtf_binaries, striprtf_hiddenimports = collect_all('striprtf')

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=striprtf_binaries,
    datas=striprtf_datas,
    hiddenimports=striprtf_hiddenimports + [
        'markdown',
        'markdown.extensions.tables',
        'markdown.extensions.fenced_code',
        'striprtf',
        'striprtf.striprtf',
        'xml.etree.ElementTree',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
        'tkinter.ttk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DriverDocsExtractor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,    # temporary: show console to diagnose startup errors
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
