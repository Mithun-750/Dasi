# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/assets', 'assets'),  # Include assets directory
    ],
    hiddenimports=[
        'langchain_google_genai',
        'pyautogui',
        'pynput',
        'pynput.keyboard._xorg',
        'pynput.mouse._xorg',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'qdarktheme',
        'google.generativeai',
        'google.api_core',
        'google.auth',
        'pydantic.deprecated.decorator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='dasi',
    debug=False,  # Enable debug mode
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Temporarily enable console for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/assets/Dasi.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='dasi'
)
