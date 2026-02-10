"""
SQLAlchemy Async Database Configuration.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.models.base import Base  # Import from models package

settings = get_settings()

# Async Engine with connection pool configuration
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_size=20,          # Increased for high concurrency (was 10)
    max_overflow=80,       # Allow more burst connections (was 20)
    pool_timeout=10,       # Fail fast instead of blocking for 30s
    pool_recycle=900,      # Recycle connections every 15 minutes (was 30m)
    pool_pre_ping=True,    # Verify connections before use
)

# Async Session Factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Dependency for FastAPI routes to get database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
