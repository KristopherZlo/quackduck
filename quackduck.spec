# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['quackduck.py'],
             pathex=[],
             binaries=[],
             datas=[
                 ('./ducky_spritesheet.png', '.'),
                 ('./heart.png', '.'),
                 ('./wuak.mp3', '.'),
                 ('./duck_icon.png', '.'),
             ],
             hiddenimports=['pygame'],  # Include pygame in hidden imports
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='quackduck',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          icon='duck_icon.png',
          onefile=True)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='quackduck')
