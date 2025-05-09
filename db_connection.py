from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
import os
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(default=os.environ['DATABASE_URL'])
}

SQLALCHEMY_DATABASE_URL = ("postgresql://p_i_devsft_user:lWFXVUGa62sOw6dwq7m67cwMd4ftBzlB@dpg-d0enlhumcj7s7380n7ig-a.virginia-postgres.render.com/p_i_devsft")

def get_engine():
    return create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)

AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=get_engine(),
    class_=AsyncSession,
)

async def get_db_session():
    async with AsyncSessionLocal() as session:
        yield session