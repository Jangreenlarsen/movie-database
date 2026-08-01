import subprocess
from pathlib import Path

from app.core.config import settings
from app.core.errors import DeployScriptNotFoundError


def trigger_deploy() -> None:
    """Launches the deploy script as a detached background process and
    returns immediately — see FEATURES.md #20 / ARCHITECTURE.md. The script
    itself later restarts this very backend process (`systemctl restart
    moviedb-backend`), so this must not block waiting for it to finish.
    `start_new_session=True` detaches the child from uvicorn's process
    group, so it survives that restart instead of being killed alongside it."""
    script_path = Path(settings.deploy_script_path)
    if not script_path.is_file():
        raise DeployScriptNotFoundError(settings.deploy_script_path)

    with open(settings.deploy_log_path, "ab") as log_file:
        subprocess.Popen(
            [str(script_path)],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
