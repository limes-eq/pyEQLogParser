# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['launch.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('resources/spells_us.txt', 'resources'),
        ('web/templates/index.html', 'web/templates'),
    ],
    hiddenimports=[
        'eqlogparser',
        'eqlogparser.config',
        'eqlogparser.data_manager',
        'eqlogparser.date_util',
        'eqlogparser.fight_analyzer',
        'eqlogparser.labels',
        'eqlogparser.log_processor',
        'eqlogparser.models',
        'eqlogparser.player_manager',
        'eqlogparser.record_manager',
        'eqlogparser.stats_util',
        'eqlogparser.text_utils',
        'eqlogparser.parsing',
        'eqlogparser.parsing.cast_line_parser',
        'eqlogparser.parsing.chat_line_parser',
        'eqlogparser.parsing.damage_line_parser',
        'eqlogparser.parsing.healing_line_parser',
        'eqlogparser.parsing.line_modifiers_parser',
        'eqlogparser.parsing.misc_line_parser',
        'eqlogparser.parsing.pre_line_parser',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'PyQt5', 'PyQt6', 'wx', 'IPython'],
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
    name='pyEQLogParser',
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pyEQLogParser',
)
