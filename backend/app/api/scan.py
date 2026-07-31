from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.scan import ScanLookupRequest, ScanLookupResponse
from app.services import scan_service

router = APIRouter(prefix="/api/scan", tags=["scan"], dependencies=[Depends(get_current_user)])


@router.post("/lookup", response_model=ScanLookupResponse)
async def scan_lookup(payload: ScanLookupRequest) -> ScanLookupResponse:
    result = await scan_service.lookup_by_barcode(payload.barcode)
    return ScanLookupResponse(**result)
