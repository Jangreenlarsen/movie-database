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


def clean_bracketed_title(raw_title: str) -> str:
    """Strips cover/edition suffixes like "(DVD)"/"[Blu-ray]" *and* common
    unbracketed retail boilerplate ("Special Edition", "Complete Series",
    "Seasons 1-6", bare "DVD"/"Blu-ray", ...) that UPC/Discogs lookups often
    bake into the product title, so the remainder makes a cleaner TMDb
    search query."""
    cleaned = _BRACKETED_SUFFIX.sub(" ", raw_title)
    cleaned = _BOILERPLATE.sub(" ", cleaned)
    return " ".join(cleaned.split()).strip()
