"""
Hybrid Database System

Supports both PostgreSQL (server mode) and SQLite (local mode).
Automatically switches based on environment configuration.

Usage:
    # In .env:
    SERVER_MODE=1  # Use PostgreSQL
    # or
    SERVER_MODE=0  # Use SQLite (local)
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

# Base for models
Base = declarative_base()


class HybridDatabase:
    """
    Hybrid database that supports both PostgreSQL and SQLite.
    
    Singleton pattern to ensure single connection pool.
    """
    
    _instance: Optional['HybridDatabase'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Determine mode
        self.server_mode = os.getenv("SERVER_MODE", "0") == "1"
        
        if self.server_mode:
            # PostgreSQL (Server Mode)
            self.database_url = os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg2://kiana:kiana_pass@localhost:5432/kiana"
            )
            print("📊 Database Mode: PostgreSQL (Server)")
        else:
            # SQLite (Local Mode)
            db_path = Path.home() / "ki_ana" / "data" / "kiana.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.database_url = f"sqlite:///{db_path}"
            print(f"📊 Database Mode: SQLite (Local)")
            print(f"   Path: {db_path}")
        
        # Create engine
        if self.server_mode:
            # PostgreSQL settings
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10
            )
        else:
            # SQLite settings
            self.engine = create_engine(
                self.database_url,
                connect_args={"check_same_thread": False},  # Important for SQLite
                pool_pre_ping=True
            )
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        print(f"✅ Database initialized: {self.database_url.split('@')[-1] if '@' in self.database_url else self.database_url}")
    
    def create_tables(self):
        """Create all tables if they don't exist."""
        Base.metadata.create_all(bind=self.engine)
        print("✅ Database tables ensured")
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    def get_info(self) -> dict:
        """Get database information."""
        return {
            "mode": "server" if self.server_mode else "local",
            "type": "PostgreSQL" if self.server_mode else "SQLite",
            "url": self.database_url.split('@')[-1] if '@' in self.database_url else self.database_url,
            "server_mode": self.server_mode
        }


# Singleton instance
_db: Optional[HybridDatabase] = None


def get_database() -> HybridDatabase:
    """Get the singleton database instance."""
    global _db
    if _db is None:
        _db = HybridDatabase()
    return _db


def get_session() -> Session:
    """Get a new database session (convenience function)."""
    db = get_database()
    return db.get_session()


def init_database():
    """Initialize database and create tables."""
    db = get_database()
    db.create_tables()
    return db


if __name__ == "__main__":
    # Quick test
    print("🔧 Hybrid Database Test\n")
    
    # Test both modes
    for mode in ["0", "1"]:
        print(f"\n{'='*50}")
        print(f"Testing with SERVER_MODE={mode}")
        print('='*50)
        
        os.environ["SERVER_MODE"] = mode
        
        # Reset singleton
        HybridDatabase._instance = None
        
        # Initialize
        db = init_database()
        
        # Get info
        info = db.get_info()
        print(f"\nDatabase Info:")
        print(f"  Mode: {info['mode']}")
        print(f"  Type: {info['type']}")
        print(f"  URL: {info['url']}")
        
        # Test session
        try:
            session = db.get_session()
            print(f"✅ Session created successfully")
            session.close()
        except Exception as e:
            print(f"❌ Session error: {e}")
    
    print("\n✅ Test complete!")
