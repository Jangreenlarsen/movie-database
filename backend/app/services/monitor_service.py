import asyncio
import platform as platform_module
import shutil
import subprocess
import time
from pathlib import Path

import psutil
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.errors import NotSupportedOnThisPlatformError
from app.models.monitor import ServiceStatus, SystemHealth

# Feature #154 — de tre services DEPLOYMENT.md dokumenterer som produktionens
# komponenter (se "## Komponenter"). Rækkefølgen matcher den dokumenterede.
MONITORED_SERVICES = ["mongod", "caddy", "moviedb-backend"]


def _is_linux() -> bool:
    return platform_module.system() == "Linux"


def _service_status(name: str) -> ServiceStatus:
    """`systemctl is-active` findes kun på Linux — på Windows/macOS (lokal
    dev) er status ukendt, ikke fejlende. Fejler stille ved enhver anden
    uventet fejl også (fx systemd er der, men servicen findes slet ikke) —
    dette er et status-overblik, ikke en handling der må vælte hele siden."""
    if not _is_linux():
        return ServiceStatus(name=name, active=None)
    try:
        result = subprocess.run(
            ["systemctl", "is-active", name], capture_output=True, text=True, timeout=3
        )
        return ServiceStatus(name=name, active=result.stdout.strip() == "active")
    except (OSError, subprocess.SubprocessError):
        return ServiceStatus(name=name, active=None)


def _collect_metrics() -> dict:
    """Synkron og potentielt blokerende (psutil.cpu_percent(interval=...)
    sover bevidst kort for at måle et reelt udsnit) — kaldes derfor via
    asyncio.to_thread fra get_health, så den ikke blokerer event loopet."""
    disk = shutil.disk_usage(".")
    vm = psutil.virtual_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.3),
        "memory_percent": vm.percent,
        "memory_used_mb": round(vm.used / 1024 / 1024),
        "memory_total_mb": round(vm.total / 1024 / 1024),
        "disk_percent": round(disk.used / disk.total * 100, 1),
        "disk_used_gb": round(disk.used / 1024**3, 1),
        "disk_total_gb": round(disk.total / 1024**3, 1),
        "uptime_seconds": round(time.time() - psutil.boot_time()),
    }


async def get_health(db: AsyncIOMotorDatabase) -> SystemHealth:
    mongo_ok = True
    try:
        await db.command("ping")
    except Exception:
        mongo_ok = False

    metrics = await asyncio.to_thread(_collect_metrics)
    services = await asyncio.to_thread(
        lambda: [_service_status(name) for name in MONITORED_SERVICES]
    )

    return SystemHealth(
        platform=platform_module.system(),
        mongo_ok=mongo_ok,
        services=services,
        **metrics,
    )


def restart_service() -> None:
    """Genstarter KUN moviedb-backend + genindlæser Caddy — genbruger den
    eksisterende OTA-deploy-restart-trigger (feature #20) direkte, uden at
    køre selve deploy.sh (intet git pull/npm build undervejs). Samme
    root-ejede, sudo-fri watcher (moviedb-deploy-restart.path) reagerer på
    filen uanset om den blev rørt af deploy.sh eller herfra."""
    if not _is_linux():
        raise NotSupportedOnThisPlatformError("Genstart af tjenesten")
    trigger = Path(settings.deploy_restart_trigger_path)
    trigger.unlink(missing_ok=True)
    trigger.touch()


def trigger_reboot() -> None:
    """Genstarter HELE serveren (fysisk/VM) — nyt, separat root-ejet
    systemd-trigger (feature #154, se DEPLOYMENT.md for engangsopsætningen
    af moviedb-reboot.path/.service), samme sudo-fri mønster som deploy/cert.
    moviedb-backend har NoNewPrivileges=true og kan derfor aldrig selv kalde
    `reboot`, uanset sudoers-opsætning."""
    if not _is_linux():
        raise NotSupportedOnThisPlatformError("Genstart af serveren")
    trigger = Path(settings.reboot_trigger_path)
    trigger.unlink(missing_ok=True)
    trigger.touch()
