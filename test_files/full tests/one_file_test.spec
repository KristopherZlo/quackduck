# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['one_file_test.py'],
    pathex=[],
    binaries=[],
    datas=[('languages/lang_en.json', 'languages'), ('languages/lang_ru.json', 'languages'), ('assets/images/heart.png', 'assets/images'), ('assets/images/settings.ico', 'assets/images'), ('assets/images/white-quackduck-hidden.ico', 'assets/images'), ('assets/images/white-quackduck-visible.ico', 'assets/images'), ('assets/skins/default/config.json', 'assets/skins/default'), ('assets/skins/default/spritesheet.png', 'assets/skins/default'), ('assets/skins/default/wuak.wav', 'assets/skins/default')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='one_file_test',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\images\\white-quackduck-visible.ico'],
)
