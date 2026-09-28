"""
Database session and connection management for OpsWingman.
Supports synchronous and asynchronous engines with lazy initialization.
"""

import os
from typing import AsyncGenerator, Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/opswingman",
)

DATABASE_SYNC_URL = os.getenv(
    "DATABASE_SYNC_URL",
    "postgresql://postgres:postgres@localhost:5432/opswingman",
)

_sync_engine = None
_SessionLocal = None
_async_engine = None
_AsyncSessionLocal = None


def get_sync_engine():
    """Returns the cached synchronous SQLAlchemy engine."""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            DATABASE_SYNC_URL,
            pool_pre_ping=True,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )
    return _sync_engine


def get_sessionmaker():
    """Returns the cached synchronous SessionLocal factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_sync_engine(),
        )
    return _SessionLocal


def SessionLocal() -> Session:
    """Instantiates a new synchronous database session."""
    factory = get_sessionmaker()
    return factory()


def get_async_engine():
    """Returns the cached asynchronous SQLAlchemy engine."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )
    return _async_engine


def get_async_sessionmaker():
    """Returns the cached asynchronous AsyncSessionLocal factory."""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            bind=get_async_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _AsyncSessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI synchronous dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI asynchronous dependency for database session."""
    factory = get_async_sessionmaker()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()
