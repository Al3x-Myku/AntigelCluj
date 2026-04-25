"""Database engine and session setup for PhishGuard."""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./phishguard.db")

# For SQLite, use check_same_thread=False
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)

# Enable WAL mode for SQLite (better concurrency)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
    """Create all tables and migrate missing columns."""
    from backend.models import campaign, target, login_event, account, osint_result, quarantined_email  # noqa
    Base.metadata.create_all(bind=engine)
    _auto_migrate_columns()


def _auto_migrate_columns():
    """Add any missing columns to existing tables (SQLite ALTER TABLE)."""
    import sqlite3
    from sqlalchemy import inspect as sa_inspect

    if not DATABASE_URL.startswith("sqlite"):
        return

    db_path = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
    if db_path.startswith("./"):
        db_path = db_path[2:]

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        inspector = sa_inspect(engine)
        for table_name in inspector.get_table_names():
            # Get existing columns in DB
            cursor.execute(f"PRAGMA table_info({table_name})")
            db_cols = {row[1] for row in cursor.fetchall()}

            # Get model columns
            model_cols = inspector.get_columns(table_name)
            for col in model_cols:
                if col["name"] not in db_cols:
                    col_type = str(col["type"])
                    nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
                    default = ""
                    if col.get("default") is not None:
                        default = f" DEFAULT {col['default']}"
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col['name']} {col_type} {nullable}{default}"
                    try:
                        cursor.execute(sql)
                        print(f"  📐 Migrated: {table_name}.{col['name']} ({col_type})")
                    except sqlite3.OperationalError:
                        pass  # column already exists

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  ⚠ Auto-migrate skipped: {e}")
