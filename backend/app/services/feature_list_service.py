import re
from pathlib import Path

from app.models.feature import FeatureListItem

# Samme rod-opslag som app/core/version_info.py: services/ -> app/ -> backend/
# -> repo-roden. FEATURES.md ligger i repo-roden.
_FEATURES_FILE = Path(__file__).resolve().parents[3] / "FEATURES.md"

# En oversigts-række: "| 114 | Navn | done | 0.90.0 |". Nummer-gruppen kræver
# cifre, så tabellens header (`| # | Feature | ...`) og separator (`|---|`)
# aldrig matcher og dermed springes over.
_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$")


def get_feature_list() -> list[FeatureListItem]:
    """Parser KUN oversigts-tabellen i FEATURES.md (afsnittet før "## Detaljer")
    og returnerer den nyeste-først. Detalje-tabellen — med interne
    implementerings-noter — parses bevidst ikke.

    Mangler filen (fx et afvigende deploy-layout), returneres en tom liste i
    stedet for at kaste, så Nyheder-fanen degraderer pænt (CLAUDE.md regel 16).
    """
    try:
        text = _FEATURES_FILE.read_text(encoding="utf-8")
    except OSError:
        return []

    # Klip detalje-tabellen fra, så dens rækker (samme format) ikke tælles med.
    overview = text.split("## Detaljer", 1)[0]

    items: list[FeatureListItem] = []
    for line in overview.splitlines():
        match = _ROW.match(line)
        if not match:
            continue
        number, name, status, version = match.groups()
        items.append(
            FeatureListItem(
                number=int(number),
                name=name.strip(),
                status=status.strip(),
                version=version.strip(),
            )
        )

    items.sort(key=lambda item: item.number, reverse=True)
    return items
