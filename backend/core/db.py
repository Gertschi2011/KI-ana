from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.core.config import Settings

settings = Settings()
engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def init_db():
    # Import models here if needed, then create tables
    Base.metadata.create_all(bind=engine)
