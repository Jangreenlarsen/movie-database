from pydantic import BaseModel


class FeatureListItem(BaseModel):
    """Feature #115 — én række fra FEATURES.md's oversigts-tabel, gjort synlig
    for portalens brugere. Bevidst kun de fire offentlige kolonner; detalje-
    tabellens interne implementerings-noter eksponeres aldrig."""

    number: int
    name: str
    status: str
    version: str
