import logging
from typing import Optional
from urllib.parse import quote

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore

from core.settings import settings

logger = logging.getLogger(__name__)


class PostgresConnectionManager:
    """管理PostgreSQL连接池和相关组件的单例类"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        if not self.initialized:
            self.pool: Optional[AsyncConnectionPool] = None
            self.saver: Optional[AsyncPostgresSaver] = None
            self.store: Optional[AsyncPostgresStore] = None
            self.initialized = True
    
    def get_connection_string(self) -> str:
        """构建PostgreSQL连接字符串"""
        if settings.POSTGRES_PASSWORD is None:
            raise ValueError("POSTGRES_PASSWORD is not set")
        
        encoded_password = quote(settings.POSTGRES_PASSWORD.get_secret_value(), safe='')
        
        # 检测是否使用Supabase Pooler
        if settings.POSTGRES_HOST and "pooler.supabase.com" in settings.POSTGRES_HOST:
            logger.info("Detected Supabase Pooler, using optimized configuration")
            # Supabase Pooler优化配置 - 注意：pgbouncer不是psycopg的参数，而是连接模式标记
            return (
                f"postgresql://{settings.POSTGRES_USER}:"
                f"{encoded_password}@"
                f"{settings.POSTGRES_HOST}:6543/"  # 使用6543端口
                f"{settings.POSTGRES_DB}?"
                f"sslmode=require"
                # prepare_threshold在connection_kwargs中设置
            )
        else:
            # 标准PostgreSQL连接
            return (
                f"postgresql://{settings.POSTGRES_USER}:"
                f"{encoded_password}@"
                f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/"
                f"{settings.POSTGRES_DB}?sslmode=require"
            )
    
    async def setup(self):
        """初始化连接池和相关组件"""
        if self.pool is not None:
            logger.warning("Connection pool already initialized")
            return
        
        validate_postgres_config()
        conn_string = self.get_connection_string()
        
        logger.info("Initializing PostgreSQL connection pool...")
        
        # 连接池配置
        connection_kwargs = {
            "autocommit": True,
            "row_factory": dict_row,
        }
        
        # 如果是Supabase Pooler，禁用prepared statements
        if settings.POSTGRES_HOST and "pooler.supabase.com" in settings.POSTGRES_HOST:
            connection_kwargs["prepare_threshold"] = None  # 完全禁用prepared statements
        
        # 创建连接池 - 使用open=False避免弃用警告
        self.pool = AsyncConnectionPool(
            conninfo=conn_string,
            min_size=2,
            max_size=10,
            timeout=30.0,
            max_lifetime=300.0,  # 5分钟
            max_idle=60.0,
            kwargs=connection_kwargs,
            open=False,  # 不在构造函数中打开连接池
        )
        
        # 显式打开连接池
        await self.pool.open()
        
        # 初始化saver和store
        self.saver = AsyncPostgresSaver(self.pool)
        self.store = AsyncPostgresStore(self.pool)
        
        # 设置数据库表
        await self.saver.setup()
        await self.store.setup()
        
        logger.info("PostgreSQL connection pool initialized successfully")
    
    async def cleanup(self):
        """清理连接池"""
        if self.pool:
            logger.info("Closing PostgreSQL connection pool...")
            await self.pool.close()
            self.pool = None
            self.saver = None
            self.store = None
            logger.info("PostgreSQL connection pool closed")
    
    def get_saver(self) -> AsyncPostgresSaver:
        """获取saver实例"""
        if self.saver is None:
            raise RuntimeError("Connection pool not initialized. Call setup() first.")
        return self.saver
    
    def get_store(self) -> AsyncPostgresStore:
        """获取store实例"""
        if self.store is None:
            raise RuntimeError("Connection pool not initialized. Call setup() first.")
        return self.store


# 保留原有函数以保持兼容性
def validate_postgres_config() -> None:
    """验证PostgreSQL配置"""
    required_vars = [
        "POSTGRES_USER",
        "POSTGRES_PASSWORD", 
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
    ]
    
    missing = [var for var in required_vars if not getattr(settings, var, None)]
    if missing:
        raise ValueError(
            f"Missing required PostgreSQL configuration: {', '.join(missing)}. "
            "These environment variables must be set to use PostgreSQL persistence."
        )


def get_postgres_connection_string() -> str:
    """Build and return the PostgreSQL connection string from settings."""
    # 使用连接管理器的方法
    return pg_manager.get_connection_string()


# 全局连接管理器实例
pg_manager = PostgresConnectionManager()


def get_postgres_saver():
    """获取PostgreSQL saver（保持向后兼容）"""
    return pg_manager.get_saver()


def get_postgres_store():
    """获取PostgreSQL store（保持向后兼容）"""
    return pg_manager.get_store()