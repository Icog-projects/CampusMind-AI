"""CampusMind AI - Database Engine and Session Factory.

Manages SQLAlchemy engine creation, connection pooling, and scoped sessions for MySQL.

Responsibilities:
1. get_database_url(): Resolves MySQL connection URL from environment variables.
2. get_engine(): Creates or returns the singleton SQLAlchemy engine with connection pooling.
3. get_session_factory(): Creates or returns the configured SQLAlchemy sessionmaker.
4. get_db_session(): FastAPI generator yielding a scoped database session and closing it on completion.
5. init_db(): Creates all database tables defined on declarative Base metadata.
"""

import os
import logging
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

load_dotenv()
logger = logging.getLogger(__name__)

# Constructs the database connection URL from environment variables, defaulting to the local MySQL instance on port 3306.
def get_database_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "campusmind")

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


Base = declarative_base()

_engine = None
_SessionFactory = None


# Returns or creates the singleton SQLAlchemy engine.
def get_engine():
    global _engine
    if _engine is None:
        url = get_database_url()
        # Pool recycle 3600 prevents stale connections on MySQL wait_timeout
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


# Returns or creates the sessionmaker.
def get_session_factory():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionFactory


# Dependency or context generator that yields a database session and ensures proper closing.
def get_db_session() -> Generator[Session, None, None]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


# Creates all registered database tables and indexes.
def init_db(engine=None):
    # Ensure all models are imported so Base.metadata knows about them
    import app.models.db_models  # noqa: F401
    target_engine = engine or get_engine()
    Base.metadata.create_all(bind=target_engine)
    logger.info("Database tables and indexes initialized successfully.")

