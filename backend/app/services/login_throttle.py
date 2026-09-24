"""BUGS.md #106 — værn mod gættede adgangskoder på det offentlige login.

Appen er nåbar fra internettet (movie.laces.dk), og hverken nginx-proxyen
eller appen begrænsede tidligere antallet af login-forsøg. Tælles pr.
(normaliseret) brugernavn, ikke pr. IP: bag nginx → Caddy → uvicorn ser
backenden kun 127.0.0.1 (uvicorn kører uden proxy-headers), så en IP-nøgle
ville låse ALLE ude på én gang.

Efter `MAX_FAILURES` forkerte forsøg inden for `WINDOW_SECONDS` afvises
yderligere forsøg på det brugernavn — også med den rigtige adgangskode, ellers
kunne en angriber blot fortsætte og se hvornår et gæt rammer — indtil det
ældste forsøg falder ud af vinduet. Et vellykket login nulstiller tælleren.
Ukendte brugernavne tælles på samme måde, så svaret ikke afslører om et
brugernavn findes.

Afvejningen: en angriber kan holde én bestemt bruger ude i op til
`WINDOW_SECONDS` ad gangen. For en husstands-app er det langt at foretrække
frem for ubegrænsede gæt. Tilstanden lever i hukommelsen: backenden kører som
én uvicorn-proces (DEPLOYMENT.md), og en genstart nulstiller blot tællerne."""

import time
from collections import deque

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60
# Loft over antal sporede brugernavne, så en strøm af tilfældige navne ikke
# kan få hukommelsen til at vokse ubegrænset.
_MAX_TRACKED = 10_000

_failures: dict[str, deque[float]] = {}


def _now() -> float:
    return time.monotonic()


def _recent(key: str, now: float) -> deque[float] | None:
    attempts = _failures.get(key)
    if attempts is None:
        return None
    while attempts and attempts[0] <= now - WINDOW_SECONDS:
        attempts.popleft()
    if not attempts:
        del _failures[key]
        return None
    return attempts


def retry_after_seconds(key: str) -> int | None:
    """Sekunder til næste forsøg er tilladt, eller None hvis det er tilladt nu."""
    now = _now()
    attempts = _recent(key, now)
    if attempts is None or len(attempts) < MAX_FAILURES:
        return None
    return max(1, int(attempts[0] + WINDOW_SECONDS - now) + 1)


def record_failure(key: str) -> None:
    now = _now()
    if key not in _failures and len(_failures) >= _MAX_TRACKED:
        for stale in [k for k in list(_failures) if _recent(k, now) is None]:
            _failures.pop(stale, None)
        if len(_failures) >= _MAX_TRACKED:
            # Stadig fuldt af aktive forsøg: glem det ældste brugernavn frem
            # for at vokse videre.
            _failures.pop(next(iter(_failures)))
    _failures.setdefault(key, deque()).append(now)


def clear(key: str) -> None:
    _failures.pop(key, None)


def reset() -> None:
    """Kun til test-isolation."""
    _failures.clear()
