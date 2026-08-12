"""LiveTrans Voice — 数据库连接"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import (DATABASE_URL, DB_MAX_OVERFLOW, DB_POOL_RECYCLE_SECONDS,
                    DB_POOL_SIZE, DB_POOL_TIMEOUT_SECONDS)

engine = create_engine(
    DATABASE_URL,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT_SECONDS,
    pool_recycle=DB_POOL_RECYCLE_SECONDS,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
