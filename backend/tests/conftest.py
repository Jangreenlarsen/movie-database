import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.db import get_database
from app.main import app
from app.repositories import movie_repository, tag_repository, tv_show_repository, user_repository


@pytest_asyncio.fixture
async def db():
    test_db = AsyncMongoMockClient()["test_moviedb"]
    await movie_repository.ensure_indexes(test_db)
    await tv_show_repository.ensure_indexes(test_db)
    await tag_repository.ensure_indexes(test_db)
    await user_repository.ensure_indexes(test_db)
    return test_db


@pytest_asyncio.fixture
async def raw_client(db):
    """AsyncClient with no logged-in user — for testing auth gating itself."""
    app.dependency_overrides[get_database] = lambda: db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(raw_client):
    """AsyncClient logged in as a default test user (cookie persists via httpx's jar)."""
    await raw_client.post(
        "/api/auth/register", json={"username": "testuser", "password": "testpassword123"}
    )
    yield raw_client
