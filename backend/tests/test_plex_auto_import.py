"""Feature #181 (Jan: "jeg tro tilgengæld at vi skal have en automatisk
scan af plex media server for ny film og tv serie, i dag er det en manual
funktion"). Afklaret via opklarende spørgsmål: admin-konfigurerbart
interval, samt en til/fra-kontakt ved siden af den eksisterende manuelle
"Importér fra Plex"-knap (feature #90), som forbliver urørt.
"""

from app.core.config import settings
from app.integrations import plex_client
from app.integrations.plex_client import PlexFetchResult, PlexItem, PlexSectionResult
from app.models.plex import PlexImportRequest
from app.repositories import system_settings_repository
from app.services import plex_service


def _fake_library(items, machine_identifier="abc123", ok=True, error=None):
    return PlexFetchResult(
        ok=ok,
        error=error,
        server_name="Voldby",
        server_version="1.40.0",
        machine_identifier=machine_identifier,
        sections=[
            PlexSectionResult(key="1", title="Film", type="movie", item_count=len(items)),
        ],
        items=items,
    )


def _patch_library(monkeypatch, result):
    async def fake_fetch_library():
        return result

    monkeypatch.setattr(plex_client, "fetch_library", fake_fetch_library)


def _configure(monkeypatch):
    monkeypatch.setattr(settings, "plex_server_url", "http://192.168.1.50:32400")
    monkeypatch.setattr(settings, "plex_token", "tok")


# --- politik: GET/PATCH /api/settings/plex-auto-import ----------------------


async def test_default_policy_is_disabled_with_a_six_hour_interval(client):
    """Default `false` — en helt ny automatiseret handling der selv opretter
    poster skal ikke stille og roligt begynde at køre uden et eksplicit
    admin-tilvalg."""
    response = await client.get("/api/settings/plex-auto-import")
    assert response.status_code == 200
    body = response.json()
    assert body["plex_auto_import_enabled"] is False
    assert body["plex_auto_import_interval_minutes"] == 360
    assert body["plex_import_tag"] == "Plex-import"


async def test_get_and_patch_require_admin(client, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        register = await standard_client.post(
            "/api/auth/register", json={"username": "notadmin181", "password": "testpassword123"}
        )
        await client.patch(f"/api/users/{register.json()['id']}/status", json={"status": "active"})
        await client.patch(f"/api/users/{register.json()['id']}/role", json={"role": "standard"})

        get_response = await standard_client.get("/api/settings/plex-auto-import")
        assert get_response.status_code == 403

        patch_response = await standard_client.patch(
            "/api/settings/plex-auto-import", json={"plex_auto_import_enabled": True}
        )
        assert patch_response.status_code == 403


async def test_updating_the_policy_takes_effect_immediately(client):
    response = await client.patch(
        "/api/settings/plex-auto-import",
        json={"plex_auto_import_enabled": True, "plex_auto_import_interval_minutes": 120},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plex_auto_import_enabled"] is True
    assert body["plex_auto_import_interval_minutes"] == 120
    assert settings.plex_auto_import_enabled is True
    assert settings.plex_auto_import_interval_minutes == 120


async def test_policy_change_is_audit_logged_with_the_actual_values(client):
    await client.patch(
        "/api/settings/plex-auto-import",
        json={"plex_auto_import_enabled": True},
    )

    log = await client.get("/api/audit-log")
    entries = log.json()["entries"]
    matching = [e for e in entries if e["action"] == "plex_auto_import_policy.updated"]
    assert len(matching) == 1
    assert "plex_auto_import_enabled=True" in matching[0]["detail"]


async def test_interval_minutes_has_sanity_bounds(client):
    too_short = await client.patch(
        "/api/settings/plex-auto-import", json={"plex_auto_import_interval_minutes": 5}
    )
    assert too_short.status_code == 422

    too_long = await client.patch(
        "/api/settings/plex-auto-import", json={"plex_auto_import_interval_minutes": 999999}
    )
    assert too_long.status_code == 422


# --- selve scan-cyklussen (_run_one_auto_import_cycle) -----------------------


async def test_one_cycle_does_nothing_when_plex_not_configured(db, monkeypatch):
    monkeypatch.setattr(settings, "plex_server_url", "")
    monkeypatch.setattr(settings, "plex_token", "")

    # Må ikke kaste, og der er intet at rydde op i bagefter — kaldet skal
    # bare stille og roligt returnere.
    await plex_service._run_one_auto_import_cycle(db)


async def test_one_cycle_imports_and_logs_when_something_is_found(db, monkeypatch):
    _configure(monkeypatch)
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)]))

    async def fake_resolve_tmdb_id(kind, title, year):
        return 603  # The Matrix' rigtige TMDb-id, vilkårligt valgt her

    monkeypatch.setattr(plex_service, "_resolve_tmdb_id", fake_resolve_tmdb_id)

    async def fake_create_imported(db, item, tmdb_id, tags, registered_by):
        assert registered_by == "plex-auto-sync"
        return "D-1080"

    monkeypatch.setattr(plex_service, "_create_imported", fake_create_imported)

    await plex_service._run_one_auto_import_cycle(db)

    from app.repositories import audit_log_repository

    entries = await audit_log_repository.list_paginated(db, skip=0, limit=50)
    matching = [e for e in entries if e["action"] == "plex.imported"]
    assert len(matching) == 1
    assert matching[0]["actor"] == "plex-auto-sync"
    assert "Automatisk scan" in matching[0]["detail"]
    assert "1 oprettet" in matching[0]["detail"]


async def test_one_cycle_does_not_log_when_nothing_new_is_found(db, monkeypatch):
    """Regel 19-agtig begrundelse for backend: uden dette ville audit-loggen
    druknes i "0 oprettet"-entries ved hvert eneste interval, hele tiden."""
    _configure(monkeypatch)
    _patch_library(monkeypatch, _fake_library([]))

    await plex_service._run_one_auto_import_cycle(db)

    from app.repositories import audit_log_repository

    entries = await audit_log_repository.list_paginated(db, skip=0, limit=50)
    assert [e for e in entries if e["action"] == "plex.imported"] == []


async def test_one_cycle_never_raises_on_unexpected_errors(db, monkeypatch):
    """CLAUDE.md regel 16 (best-effort) — en uventet fejl her må aldrig
    vælte den evigt-kørende baggrunds-løkke."""
    _configure(monkeypatch)

    async def raise_unexpectedly():
        raise RuntimeError("noget uventet gik galt")

    monkeypatch.setattr(plex_client, "fetch_library", raise_unexpectedly)

    # Skal ikke kaste videre.
    await plex_service._run_one_auto_import_cycle(db)


# --- feature #182: delt tag mellem manuel import og auto-scan ---------------
#
# Jan: "søger for at tag på importerede i auto-scan plex er det tag som er
# difineret under 'importer fra plex'". `_configure`/`_fake_library` m.fl.
# genbruges fra ovenfor.


async def _import_one_movie(db, monkeypatch, tag, dry_run, registered_by="jan"):
    """Fælles opsætning for et enkelt-element-import — genbruges af flere af
    testene nedenfor med forskellige `tag`/`dry_run`/`registered_by`."""
    _configure(monkeypatch)
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)]))

    async def fake_resolve_tmdb_id(kind, title, year):
        return 603

    monkeypatch.setattr(plex_service, "_resolve_tmdb_id", fake_resolve_tmdb_id)

    async def fake_create_imported(db, item, tmdb_id, tags, registered_by):
        return "D-1080"

    monkeypatch.setattr(plex_service, "_create_imported", fake_create_imported)

    return await plex_service.import_from_plex(
        db,
        PlexImportRequest(dry_run=dry_run, include_movies=True, include_shows=False, tag=tag),
        registered_by,
    )


async def test_a_real_manual_import_persists_its_tag_as_the_shared_definition(client, db, monkeypatch):
    result = await _import_one_movie(db, monkeypatch, tag="Fra-Plex-server", dry_run=False)
    assert result.ok is True
    assert settings.plex_import_tag == "Fra-Plex-server"

    # Overlever også en "frisk" læsning fra Mongo, ikke kun in-process settings.
    overrides = await system_settings_repository.get_plex_auto_import_overrides(db)
    assert overrides["plex_import_tag"] == "Fra-Plex-server"

    response = await client.get("/api/settings/plex-auto-import")
    assert response.json()["plex_import_tag"] == "Fra-Plex-server"


async def test_a_preview_does_not_persist_its_tag(db, monkeypatch):
    """En forhåndsvisning (`dry_run: true`) opretter intet — den skal derfor
    heller ikke ændre den delte definition, kun en rigtig import gør."""
    await _import_one_movie(db, monkeypatch, tag="Kun-en-preview", dry_run=True)
    assert settings.plex_import_tag == "Plex-import"


async def test_auto_scan_itself_does_not_overwrite_the_shared_definition(db, monkeypatch):
    """Auto-scan-loopet importerer også med `dry_run: false`, men er ikke en
    admin der aktivt definerer et nyt tag — kun en rigtig, admin-udført
    import (anden `registered_by` end auto-scan-aktøren) må skrive den
    delte definition."""
    await _import_one_movie(
        db, monkeypatch, tag="Plex-import", dry_run=False, registered_by=plex_service._AUTO_IMPORT_ACTOR
    )
    overrides = await system_settings_repository.get_plex_auto_import_overrides(db)
    assert "plex_import_tag" not in overrides


async def test_auto_scan_cycle_uses_the_shared_tag(db, monkeypatch):
    """`_run_one_auto_import_cycle` bygger selv sin `PlexImportRequest` —
    den skal bruge den delte `settings.plex_import_tag`, ikke modellens egen
    hårdkodede default, så en admin der har sat et andet tag under "Importér
    fra Plex" også får det på auto-scannede poster."""
    monkeypatch.setattr(settings, "plex_import_tag", "Mit-eget-tag")
    _configure(monkeypatch)
    _patch_library(monkeypatch, _fake_library([PlexItem("movie", "42", "The Matrix", 1999, None, None)]))

    async def fake_resolve_tmdb_id(kind, title, year):
        return 603

    monkeypatch.setattr(plex_service, "_resolve_tmdb_id", fake_resolve_tmdb_id)

    seen_tags = []

    async def fake_create_imported(db, item, tmdb_id, tags, registered_by):
        seen_tags.append(tags)
        return "D-1080"

    monkeypatch.setattr(plex_service, "_create_imported", fake_create_imported)

    await plex_service._run_one_auto_import_cycle(db)

    assert seen_tags == [["Mit-eget-tag"]]
