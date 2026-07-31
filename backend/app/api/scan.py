from fastapi import APIRouter

from app.models.scan import ScanLookupRequest, ScanLookupResponse
from app.services import scan_service

router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.post("/lookup", response_model=ScanLookupResponse)
async def scan_lookup(payload: ScanLookupRequest) -> ScanLookupResponse:
    result = await scan_service.lookup_by_barcode(payload.barcode)
    return ScanLookupResponse(**result)
