from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.services import auth_service


async def _register_standalone(username: str, password: str):
    """Fresh, unauthenticated client — used where a registration is
    expected to be rejected by the currently-configured policy, so it must
    not go through the shared `client` fixture (already-registered admin)."""
    transport = ASGITransport(app=app)
    ac = AsyncClient(transport=transport, base_url="http://test")
    response = await ac.post(
        "/api/auth/register", json={"username": username, "password": password}
    )
    await ac.aclose()
    return response


async def test_password_policy_requires_admin(client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadminpolicy", "password": "testpassword123"}
        )
        get_response = await standard_client.get("/api/settings/password-policy")
        patch_response = await standard_client.patch(
            "/api/settings/password-policy", json={"password_min_length": 20}
        )
        assert get_response.status_code == 403
        assert patch_response.status_code == 403


async def test_default_policy_matches_the_historical_fixed_behaviour(client):
    response = await client.get("/api/settings/password-policy")
    assert response.status_code == 200
    assert response.json() == {
        "password_min_length": 8,
        "password_require_uppercase": False,
        "password_require_lowercase": False,
        "password_require_digit": False,
    }


async def test_raising_min_length_takes_effect_immediately(client):
    patch = await client.patch(
        "/api/settings/password-policy", json={"password_min_length": 12}
    )
    assert patch.status_code == 200
    assert patch.json()["password_min_length"] == 12
    assert settings.password_min_length == 12

    too_short = await _register_standalone("shortpw1", "onlyeleven1")
    assert too_short.status_code == 422
    # FastAPI's own 422s carry `detail` as a *list* of {loc, msg, type}
    # (unlike our own HTTPExceptions, whose `detail` is a plain string —
    # see BUGS.md #54, the exact same shape mismatch the frontend already
    # has to handle via readableDetail()).
    assert "mindst 12 tegn" in too_short.json()["detail"][0]["msg"]

    long_enough = await _register_standalone("longenoughpw", "exactlytwelve1")
    assert long_enough.status_code == 201


async def test_require_uppercase_enforced_on_registration(client):
    await client.patch(
        "/api/settings/password-policy", json={"password_require_uppercase": True}
    )

    rejected = await _register_standalone("nouppercase1", "alllowercase1")
    assert rejected.status_code == 422
    assert "stort bogstav" in rejected.json()["detail"][0]["msg"]

    accepted = await _register_standalone("hasuppercase1", "hasUppercase1")
    assert accepted.status_code == 201


async def test_require_lowercase_enforced_on_registration(client):
    await client.patch(
        "/api/settings/password-policy", json={"password_require_lowercase": True}
    )

    rejected = await _register_standalone("nolowercase1", "ALLUPPERCASE1")
    assert rejected.status_code == 422
    assert "lille bogstav" in rejected.json()["detail"][0]["msg"]


async def test_require_digit_enforced_on_registration(client):
    await client.patch("/api/settings/password-policy", json={"password_require_digit": True})

    rejected = await _register_standalone("nodigit1", "NoDigitsHere")
    assert rejected.status_code == 422
    assert "tal" in rejected.json()["detail"][0]["msg"]

    accepted = await _register_standalone("hasdigit1", "HasADigit1")
    assert accepted.status_code == 201


async def test_policy_also_applies_to_self_service_password_change(client):
    """Not just registration — CLAUDE.md regel 16's "regler der kun gælder
    én gren"-advarsel gælder direkte her: en politik der kun håndhæves ved
    oprettelse ville lade enhver bruger omgå den ved bagefter selv at
    skifte til noget svagere."""
    await client.patch(
        "/api/settings/password-policy", json={"password_require_digit": True}
    )

    response = await client.post(
        "/api/users/me/password",
        json={"current_password": "testpassword123", "new_password": "noDigitsAtAll"},
    )
    assert response.status_code == 422
    assert "tal" in response.json()["detail"][0]["msg"]

    response = await client.post(
        "/api/users/me/password",
        json={"current_password": "testpassword123", "new_password": "hasADigit1"},
    )
    assert response.status_code == 204


async def test_omitted_fields_are_left_untouched(client):
    await client.patch(
        "/api/settings/password-policy",
        json={"password_min_length": 10, "password_require_uppercase": True},
    )

    response = await client.patch(
        "/api/settings/password-policy", json={"password_require_digit": True}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["password_min_length"] == 10
    assert body["password_require_uppercase"] is True
    assert body["password_require_digit"] is True


async def test_policy_change_is_audit_logged_with_actual_values(client):
    """Modsat feature #171's adgangskode-nulstilling er politik-værdierne
    her ikke hemmelige (bare tal/booleans) — audit-loggen må derfor gerne
    (og skal) vise dem, i modsætning til regel 6-undtagelsen for selve
    adgangskoder."""
    await client.patch(
        "/api/settings/password-policy", json={"password_min_length": 15}
    )

    log = await client.get("/api/audit-log")
    entries = log.json()["entries"]
    matching = [e for e in entries if e["action"] == "password_policy.updated"]
    assert len(matching) == 1
    assert "password_min_length=15" in matching[0]["detail"]


async def test_invalid_min_length_is_rejected(client):
    too_low = await client.patch(
        "/api/settings/password-policy", json={"password_min_length": 3}
    )
    assert too_low.status_code == 422

    too_high = await client.patch(
        "/api/settings/password-policy", json={"password_min_length": 999}
    )
    assert too_high.status_code == 422


# Feature #174 — den admin-genererede midlertidige kode (#171) skal selv
# overholde politikken, ikke kun de to almindelige veje ovenfor.


async def test_admin_reset_temporary_password_satisfies_a_strict_policy(client):
    second, body = None, None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second_client:
        register = await second_client.post(
            "/api/auth/register", json={"username": "resetpolicytarget", "password": "testpassword123"}
        )
        body = register.json()
    await client.patch(f"/api/users/{body['id']}/status", json={"status": "active"})

    await client.patch(
        "/api/settings/password-policy",
        json={
            "password_min_length": 20,
            "password_require_uppercase": True,
            "password_require_lowercase": True,
            "password_require_digit": True,
        },
    )

    reset = await client.post(f"/api/users/{body['id']}/reset-password")
    assert reset.status_code == 200
    new_password = reset.json()["new_password"]

    # BUGS.md #75 — den udleverede kode skal matche den konfigurerede
    # længde PRÆCIST, ikke bare være mindst så lang.
    assert len(new_password) == 20
    assert any(c.isupper() for c in new_password)
    assert any(c.islower() for c in new_password)
    assert any(c.isdigit() for c in new_password)


async def test_generated_temporary_password_matches_a_low_configured_minimum(client):
    """BUGS.md #75 (Jan, testet live: satte min-længden til 6, men fik
    stadig en 12-tegns kode). Ingen skjult bundgrænse længere — den
    udleverede kode skal matche den konfigurerede politik præcist, også når
    den er lavere end den tidligere faste værdi på 12."""
    await client.patch("/api/settings/password-policy", json={"password_min_length": 6})

    password = auth_service._generate_temporary_password()
    assert len(password) == 6
