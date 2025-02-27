# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['word_search.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('context', 'word_search_context'),  # 仅暴露word_search_context目录
    ],
    hiddenimports=['pickle'],  # 添加pickle模块支持
    exclude_binaries=True,  # 排除其他二进制文件
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
    name='word_search',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,  # 禁用临时目录，使用系统缓存目录
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
