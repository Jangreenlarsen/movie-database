from typing import Literal

from pydantic import BaseModel

# Feature #194 — Jan: "vi skal have en mulighed for at opdater fra github på
# Main eller Dev på portal sådan det giver mening med main og dev versioner".
# Kun disse to eksisterer som reelle, deploybare grene (se DEPLOYMENT.md) —
# et ukendt navn afvises af Pydantic/FastAPI som en 422 frem for at blive
# sendt videre til scripts/deploy.sh, som selv ville afvise det, men senere
# og mindre tydeligt.
DeployBranch = Literal["main", "dev"]


class DeployRequest(BaseModel):
    # Default "main" bevarer den hidtidige, sikre opførsel uændret for enhver
    # kalder der ikke eksplicit sender et branch-navn (CLAUDE.md regel 16 —
    # sikre standardværdier).
    branch: DeployBranch = "main"
