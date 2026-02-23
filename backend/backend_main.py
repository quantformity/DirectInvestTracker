"""
PyInstaller entry point for the Qf Direct Invest Tracker backend.

Build with:
    cd backend
    pyinstaller backend.spec

The resulting binary is in dist/investments-backend/investments-backend (macOS/Linux)
or dist/investments-backend/investments-backend.exe (Windows).
"""
import multiprocessing
import os
import sys


if __name__ == "__main__":
    multiprocessing.freeze_support()

    # When frozen by PyInstaller, add the bundle dir so `app` package is importable
    if getattr(sys, "frozen", False):
        sys.path.insert(0, sys._MEIPASS)

    # Ensure the SQLite database directory exists before SQLAlchemy tries to create the DB
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("sqlite:///"):
        db_path = db_url[len("sqlite:///"):]
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    import uvicorn
    from app.main import app as fastapi_app  # explicit import → PyInstaller traces the chain

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="info")
