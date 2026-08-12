from collections import Counter
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.analytics import VisitCreate, VisitStats
from app.models.movie import NamedCount
from app.repositories import visit_repository

# Sentinel-navn for anonyme (ikke-indloggede) besøg. Frontend oversætter det
# til "Gæst"; rigtige brugernavne vises som de er.
GUEST_SENTINEL = "__guest__"

PER_DAY_WINDOW = 14
TOP_TITLES = 10
TOP_USERS = 10


async def record_visit(
    db: AsyncIOMotorDatabase, payload: VisitCreate, username: str | None
) -> None:
    document = {
        "at": datetime.now(timezone.utc),
        "page": payload.page[:64],
        "kind": payload.kind,
        # None = gæst. Aldrig fra payloaden (kun serverens egen bruger-opslag),
        # så et besøg ikke kan tilskrives en forkert bruger.
        "username": username,
    }
    if payload.kind == "title":
        document["resource_kind"] = payload.resource_kind
        document["resource_id"] = payload.resource_id
        document["title"] = (payload.title or "").strip() or None
    await visit_repository.insert(db, document)


def _visit_date(value) -> "datetime.date | None":
    """`at` er en tz-aware `datetime` ved skrivning; mongomock kan gemme den
    som naiv. `.date()` er robust mod begge (dropper tzinfo hvis den findes)."""
    if isinstance(value, datetime):
        return value.date()
    return None


async def get_visit_stats(db: AsyncIOMotorDatabase) -> VisitStats:
    visits = await visit_repository.find_all(db)
    today = datetime.now(timezone.utc).date()

    per_day: Counter = Counter()
    per_page: Counter = Counter()
    per_title: Counter = Counter()
    per_user: Counter = Counter()
    named_users: set[str] = set()
    guest_visits = 0

    for visit in visits:
        day = _visit_date(visit.get("at"))
        if day is not None:
            per_day[day] += 1

        if visit.get("kind") == "title":
            per_title[visit.get("title") or "(ukendt titel)"] += 1
        else:
            per_page[visit.get("page") or "(ukendt)"] += 1

        username = visit.get("username")
        if username:
            named_users.add(username)
            per_user[username] += 1
        else:
            guest_visits += 1
            per_user[GUEST_SENTINEL] += 1

    # Kontinuerlig serie over de sidste PER_DAY_WINDOW dage, så 0-dage også
    # tegnes (en trend med huller er sværere at læse end en med nuller).
    per_day_series = [
        NamedCount(name=(today - timedelta(days=offset)).isoformat(), count=per_day.get(today - timedelta(days=offset), 0))
        for offset in range(PER_DAY_WINDOW - 1, -1, -1)
    ]

    return VisitStats(
        total_visits=len(visits),
        visits_today=per_day.get(today, 0),
        unique_users=len(named_users),
        guest_visits=guest_visits,
        per_day=per_day_series,
        per_page=[NamedCount(name=name, count=count) for name, count in per_page.most_common()],
        top_titles=[NamedCount(name=name, count=count) for name, count in per_title.most_common(TOP_TITLES)],
        per_user=[NamedCount(name=name, count=count) for name, count in per_user.most_common(TOP_USERS)],
    )
