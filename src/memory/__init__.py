from contextlib import AbstractAsyncContextManager, asynccontextmanager

from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from core.settings import DatabaseType, settings
from memory.mongodb import get_mongo_saver
from memory.postgres import pg_manager, get_postgres_saver, get_postgres_store
from memory.sqlite import get_sqlite_saver, get_sqlite_store


@asynccontextmanager
async def initialize_database():
    """
    Initialize the appropriate database checkpointer based on configuration.
    Returns an initialized AsyncCheckpointer instance.
    """
    if settings.DATABASE_TYPE == DatabaseType.POSTGRES:
        # 使用连接池管理器
        if pg_manager.pool is None:
            await pg_manager.setup()
        yield pg_manager.get_saver()
    elif settings.DATABASE_TYPE == DatabaseType.MONGO:
        async with get_mongo_saver() as saver:
            yield saver
    else:  # Default to SQLite
        async with get_sqlite_saver() as saver:
            yield saver


@asynccontextmanager
async def initialize_store():
    """
    Initialize the appropriate store based on configuration.
    Returns an async context manager for the initialized store.
    """
    if settings.DATABASE_TYPE == DatabaseType.POSTGRES:
        # 使用连接池管理器
        if pg_manager.pool is None:
            await pg_manager.setup()
        yield pg_manager.get_store()
    # TODO: Add Mongo store - https://pypi.org/project/langgraph-store-mongodb/
    else:  # Default to SQLite
        async with get_sqlite_store() as store:
            yield store


__all__ = ["initialize_database", "initialize_store"]
