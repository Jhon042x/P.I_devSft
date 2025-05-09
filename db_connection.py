from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
import os
import dj_database_url
from dotenv import load_dotenv
load_dotenv()

DATABASES = {
    'default': dj_database_url.config(default=os.environ['DATABASE_URL'])
}

SQLALCHEMY_DATABASE_URL = os.getenv('SQLALCHEMY_DATABASE_URL')

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