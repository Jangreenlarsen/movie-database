import json
import subprocess
from pathlib import Path

from app.core.config import settings
from app.core.errors import DeployScriptNotFoundError


def get_deploy_status() -> dict:
    """Reads the outcome deploy.sh wrote from its last run (BUGS.md #36) —
    `{"outcome": "up-to-date"|"updated", "commit": ..., "at": ...}`. Returns
    `{"outcome": "unknown"}` if the file is missing (fresh install, or the
    production copy of deploy.sh hasn't been updated to write it yet) or
    unparsable — never raises, this is a best-effort status read."""
    status_path = Path(settings.deploy_status_path)
    try:
        return json.loads(status_path.read_text())
    except (OSError, ValueError):
        return {"outcome": "unknown"}


def trigger_deploy(branch: str = "main") -> None:
    """Launches the deploy script as a detached background process and
    returns immediately — see FEATURES.md #20 / ARCHITECTURE.md. The script
    itself later restarts this very backend process (`systemctl restart
    moviedb-backend`), so this must not block waiting for it to finish.
    `start_new_session=True` detaches the child from uvicorn's process
    group, so it survives that restart instead of being killed alongside it.

    Feature #194 — `branch` ("main"/"dev") is passed as the script's sole
    argument; validated upstream by `models.deploy.DeployRequest` (a
    `Literal`), so an unknown value never reaches here."""
    script_path = Path(settings.deploy_script_path)
    if not script_path.is_file():
        raise DeployScriptNotFoundError(settings.deploy_script_path)

    with open(settings.deploy_log_path, "ab") as log_file:
        subprocess.Popen(
            [str(script_path), branch],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
