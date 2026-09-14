# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# API-set DLL names are contracts implemented by Windows itself. Some build
# environments put compatibility copies on PATH; bundling those copies beside
# the application can shadow the operating-system implementation and make
# QtCore fail with "The specified procedure could not be found".
def is_windows_compatibility_dll(entry):
    name = entry[0].lower()
    return (
        name.startswith('api-ms-win-')
        or name == 'icuuc.dll'
        or name.startswith('icudt')
        or name.startswith('icuin')
    )


a.binaries = [entry for entry in a.binaries if not is_windows_compatibility_dll(entry)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='UART-CAN-Host',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
