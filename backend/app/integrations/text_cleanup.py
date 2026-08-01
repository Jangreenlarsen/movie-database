import re

_BRACKETED_SUFFIX = re.compile(r"[\[(][^\])]*[\])]")


def clean_bracketed_title(raw_title: str) -> str:
    """Strips cover/edition suffixes like "(DVD)"/"[Blu-ray]" that UPC/Discogs
    lookups often bake into the product title, so the remainder makes a
    cleaner TMDb search query."""
    cleaned = _BRACKETED_SUFFIX.sub(" ", raw_title)
    return " ".join(cleaned.split()).strip()
