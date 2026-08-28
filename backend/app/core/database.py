from collections.abc import AsyncIterator, Awaitable, Callable

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url.get_secret_value(),
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=settings.db_pool_recycle_seconds,
)
SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


async def execute_read_only_with_retry[ReadResult](
    session: AsyncSession,
    operation: Callable[[], Awaitable[ReadResult]],
) -> ReadResult:
    """Retry one idempotent read once after an explicit transient disconnect.

    Callers must opt in per read operation. Write repositories never pass through
    this helper, so allocation, ledger, distribution and operational decisions are
    not replayed automatically.
    """

    try:
        return await operation()
    except Exception as error:
        if not is_transient_disconnect(error):
            raise
        await session.invalidate()
        return await operation()


def is_transient_disconnect(error: BaseException) -> bool:
    if isinstance(error, DBAPIError) and error.connection_invalidated:
        return True

    current: BaseException | None = error
    visited: set[int] = set()
    transient_names = {"ConnectionDoesNotExistError"}
    transient_messages = (
        "connection was closed in the middle of operation",
        "decryption_failed_or_bad_record_mac",
        "connection is closed",
    )
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if type(current).__name__ in transient_names:
            return True
        message = str(current).casefold()
        if any(marker in message for marker in transient_messages):
            return True
        current = current.__cause__ or current.__context__
    return False
