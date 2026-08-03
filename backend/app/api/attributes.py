from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.db import get_database
from app.services import attribute_service

# Cross-resource attribute suggestions (owner/location values already in
# use across both movies and TV shows) — flat top-level resources, same
# pattern as /api/tags (FEATURES.md #58).
router = APIRouter(prefix="/api", tags=["attributes"], dependencies=[Depends(get_current_user)])


@router.get("/owners", response_model=list[str])
async def list_owners(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await attribute_service.list_owners(db)


@router.get("/locations", response_model=list[str])
async def list_locations(db: AsyncIOMotorDatabase = Depends(get_database)):
    return await attribute_service.list_locations(db)
