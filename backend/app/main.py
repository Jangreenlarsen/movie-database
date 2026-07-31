import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.core.config import settings
from app.db import close_client, get_client

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("moviedb")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_client()
    logger.info("MongoDB client initialized (%s)", settings.mongo_db_name)
    yield
    await close_client()


app = FastAPI(title="Movie Database API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
