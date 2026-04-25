"""Database engine and session — MySQL/MariaDB."""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:@localhost:3306/breezetech")

def ensure_database_exists(db_url):
    """Attempt to create the database if it doesn't exist."""
    try:
        if "mysql" in db_url:
            # Extract base URL (without db name) and db name
            import urllib.parse
            parsed = urllib.parse.urlparse(db_url)
            db_name = parsed.path.lstrip('/')
            base_url = db_url.rsplit('/', 1)[0]
            
            # Connect to base URL
            temp_engine = create_engine(base_url)
            with temp_engine.connect() as conn:
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {db_name}"))
            temp_engine.dispose()
    except Exception as e:
        print(f"[WARN] Could not auto-create database. Is MySQL running? Error: {e}")

ensure_database_exists(DATABASE_URL)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    import backend.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
