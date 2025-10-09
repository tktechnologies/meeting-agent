"""
Database connection module with PostgreSQL/SQLite support
Automatically uses PostgreSQL if DATABASE_URL is set, otherwise falls back to SQLite
"""
import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

# Base class for all models
Base = declarative_base()


def get_database_url():
    """
    Get database URL from environment or fall back to SQLite for local dev
    
    Returns:
        str: Database connection URL
    """
    db_url = os.getenv("DATABASE_URL")
    
    if db_url:
        # PostgreSQL (Azure Container Apps or cloud)
        print(f"🗄️  Using PostgreSQL: {db_url.split('@')[1] if '@' in db_url else 'cloud'}")
        return db_url
    else:
        # SQLite fallback (local development)
        from .config import DB_PATH
        print(f"🗄️  Using SQLite: {DB_PATH}")
        return f"sqlite:///{DB_PATH}"


def create_db_engine():
    """
    Create SQLAlchemy engine with appropriate configuration
    
    Returns:
        Engine: Configured SQLAlchemy engine
    """
    database_url = get_database_url()
    is_sqlite = database_url.startswith("sqlite")
    
    if is_sqlite:
        # SQLite-specific configuration
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        
        # Enable foreign keys for SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    else:
        # PostgreSQL configuration
        engine = create_engine(
            database_url,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,  # Recycle connections after 1 hour
            echo=False
        )
    
    return engine


# Create global engine and session factory
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Dependency for FastAPI endpoints
    
    Yields:
        Session: Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database schema
    Creates all tables defined in models
    """
    from . import models  # Import models to register them
    Base.metadata.create_all(bind=engine)
    print("✓ Database schema initialized")


def get_db_connection():
    """
    Get a database session for direct use
    
    Returns:
        Session: Database session (remember to close!)
    """
    return SessionLocal()
