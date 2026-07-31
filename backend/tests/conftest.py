import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.db import get_database
from app.main import app
from app.repositories import movie_repository, tag_repository


@pytest_asyncio.fixture
async def db():
    test_db = AsyncMongoMockClient()["test_moviedb"]
    await movie_repository.ensure_indexes(test_db)
    await tag_repository.ensure_indexes(test_db)
    return test_db


@pytest_asyncio.fixture
async def client(db):
    app.dependency_overrides[get_database] = lambda: db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
