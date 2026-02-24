# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Investment Vibe FastAPI backend.
#
# Build:  cd backend && pyinstaller backend.spec
# Output: dist/investments-backend/  (directory bundle — fast startup, no extraction)

from PyInstaller.utils.hooks import collect_all

import os as _os
datas = [
    # Bundle the repo-root VERSION file so the packaged binary can read it
    (_os.path.join(_os.path.dirname(SPECPATH), "VERSION"), "."),
]
binaries = []
hiddenimports = []

# curl_cffi ships native C extensions and TLS data; collect everything
tmp = collect_all("curl_cffi")
datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

# pandas/numpy ship many optional C extensions
tmp = collect_all("pandas")
datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

a = Analysis(
    ["backend_main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        # uvicorn internals that are imported dynamically
        "uvicorn.main",
        "uvicorn.config",
        "uvicorn.logging",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.middleware.proxy_headers",
        # SQLAlchemy SQLite dialect
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.sqlite.pysqlite",
        # APScheduler
        "apscheduler.schedulers.background",
        "apscheduler.triggers.interval",
        "apscheduler.triggers.cron",
        "apscheduler.jobstores.memory",
        "apscheduler.executors.pool",
        # pydantic
        "pydantic_settings",
        # multipart (required by FastAPI for form/file uploads)
        "multipart",
        # matplotlib non-interactive backend (used for chart generation)
        "matplotlib.backends.backend_agg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "test", "unittest", "_pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # onedir mode — binaries placed in COLLECT output
    name="investments-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # keep console for log output; set False to silence on Windows
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="investments-backend",
)
