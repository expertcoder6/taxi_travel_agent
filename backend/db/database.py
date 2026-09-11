from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.config import settings
from backend.db.models import Base

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from sqlalchemy import text

def init_db():
    Base.metadata.create_all(bind=engine)
    # Ensure newly added columns exist in sqlite tables
    with engine.connect() as conn:
        for table, col, col_type in [
            ("rides", "passenger_count", "INTEGER DEFAULT 1"),
            ("rides", "scheduled_time", "VARCHAR(100) DEFAULT 'Immediate'"),
            ("rides", "requested_driver", "VARCHAR(100)"),
            ("conversation_state", "passenger_count", "INTEGER DEFAULT 1"),
            ("conversation_state", "scheduled_time", "VARCHAR(100) DEFAULT 'Immediate'"),
            ("conversation_state", "requested_driver", "VARCHAR(100)"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass  # Column already exists

def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
