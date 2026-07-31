from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_database
from app.services import tag_service

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("", response_model=list[str])
async def list_tags(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await tag_service.list_tag_names(db)
