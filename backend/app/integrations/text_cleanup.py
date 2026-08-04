import re

_BRACKETED_SUFFIX = re.compile(r"[\[(][^\])]*[\])]")

# Common retail/edition/format boilerplate that UPC/Discogs product titles
# often include *without* brackets — "The Matrix Special Edition DVD" needs
# this trimmed to just "The Matrix" for TMDb search to reliably find it.
# Matched as whole phrases/words (word-boundaried) so real title words are
# never eaten by accident. Found via BUGS.md #20: a raw title of "The
# Americans Complete Series Seasons 1-6" returned 0 TMDb results, while the
# cleaned "The Americans" returned real candidates.
_BOILERPLATE = re.compile(
    r"\b("
    r"special edition|collector'?s edition|director'?s cut|extended edition|"
    r"anniversary edition|ultimate edition|definitive edition|remastered|"
    r"steelbook|complete series|complete collection|complete trilogy|"
    r"trilogy collection|box ?set|seasons? \d+([-–]\d+)?|"
    r"region [12]|widescreen|full screen|"
    r"blu-?ray|4k uhd|uhd|dvd|vhs"
    r")\b",
    re.IGNORECASE,
)

# A bare "- <number>" (or "– <number>") at the very *end* of a product title
# is essentially always a disc/season/volume index a retailer tacked on
# ("The Americans - 6" for Season 6, "Rocky - 2" for disc 2 of a box set),
# never part of the actual title itself — real titles that end in a number
# either have no separator ("Blade Runner 2049", "300") or a word before it
# ("Kill Bill Vol. 1"), so this is safe to strip unconditionally. Found
# 2026-08-04: EAN-Search.org's "Simply HE The Americans - 6" returned zero
# TMDb candidates as a whole string.
_TRAILING_DASH_NUMBER = re.compile(r"\s+[-–]\s*\d+\s*$")


def clean_bracketed_title(raw_title: str) -> str:
    """Strips cover/edition suffixes like "(DVD)"/"[Blu-ray]" *and* common
    unbracketed retail boilerplate ("Special Edition", "Complete Series",
    "Seasons 1-6", bare "DVD"/"Blu-ray", a trailing "- 6" disc/season index,
    ...) that UPC/Discogs/EAN lookups often bake into the product title, so
    the remainder makes a cleaner TMDb search query."""
    cleaned = _BRACKETED_SUFFIX.sub(" ", raw_title)
    cleaned = _BOILERPLATE.sub(" ", cleaned)
    cleaned = _TRAILING_DASH_NUMBER.sub(" ", cleaned)
    return " ".join(cleaned.split()).strip()
