"""Shared database session for CLI tools."""
import os
import sys

# Allow importing from backend/app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_engine():
    url = os.getenv("DATABASE_URL", "sqlite:///data/investments.db")
    return create_engine(url, connect_args={"check_same_thread": False})


def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()
