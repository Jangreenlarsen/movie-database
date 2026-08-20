"""Delt af film- og TV-repositoriet (feature #184, Jan: "i sortering skal
det være muligt at ignorerer 'the' i starten af titel navn").

Ren streng-transformation, ingen database-adgang — samme lille delt
hjælper-i-repositories/-mønster som text_search.py. Bruges til at udlede
`sort_title`/`sort_name` (se movie_service.py/tv_show_service.py), et
gemt felt der bruges i stedet for `title`/`name` når brugeren vælger
sorteringsvalget "Titel/Navn (uden 'The')" — MongoDB kan ikke sortere på et
udtryk beregnet ved forespørgselstidspunkt uden en aggregation-pipeline, så
værdien beregnes og gemmes i stedet ved hver oprettelse/titel-ændring
(samme "afledt felt, holdt ved lige ved skrivning"-mønster som
`tags_normalized`).
"""

import re

# Kræver mindst ét whitespace-tegn efter "the" for at undgå at klippe i ord
# der selv starter med bogstaverne (fx "Thereafter", "Theory") — de har intet
# mellemrum lige efter "the" og rammes derfor aldrig af mønsteret.
_LEADING_ARTICLE_RE = re.compile(r"^the\s+", re.IGNORECASE)


def strip_leading_article(title: str) -> str:
    """"The Matrix" -> "Matrix". Titler uden en foranstillet "the" — eller
    hvor "the" er hele titlen, uden noget bagefter — returneres uændret."""
    return _LEADING_ARTICLE_RE.sub("", title, count=1)
