from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.services import deploy_service

router = APIRouter(prefix="/api/system", tags=["system"])


@router.post("/deploy", status_code=202, dependencies=[Depends(require_admin)])
async def deploy() -> dict:
    deploy_service.trigger_deploy()
    return {"status": "started"}
