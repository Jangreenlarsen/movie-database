import base64
import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


def _self_sign(common_name: str, private_key=None):
    """Builds a self-signed cert (mimicking what an external CA would return
    for a CSR) — good enough for exercising the public-key-match check
    without a real CA in tests."""
    private_key = private_key or ec.generate_private_key(ec.SECP256R1())
    now = datetime.datetime.now(datetime.timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=730))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False)
        .sign(private_key, hashes.SHA256())
    )
    return private_key, cert


def _pem(cert) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def _setup_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "cert_staging_dir", str(tmp_path / "staging"))
    monkeypatch.setattr(settings, "cert_live_path", str(tmp_path / "live" / "movie.ll.lan.crt"))
    monkeypatch.setattr(settings, "cert_install_trigger_path", str(tmp_path / "trigger"))
    monkeypatch.setattr(settings, "cert_common_name", "movie.ll.lan")


async def test_cert_status_reports_nothing_when_none_installed_or_staged(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    response = await client.get("/api/system/cert")
    assert response.status_code == 200
    assert response.json() == {
        "installed": False,
        "staged": False,
        "common_name": None,
        "subject_alt_names": [],
        "valid_from": None,
        "valid_until": None,
        "days_until_expiry": None,
    }


async def test_cert_endpoints_require_admin(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as standard_client:
        await standard_client.post(
            "/api/auth/register", json={"username": "notadmin", "password": "testpassword123"}
        )
        assert (await standard_client.get("/api/system/cert")).status_code == 403
        assert (await standard_client.post("/api/system/cert/csr")).status_code == 403
        assert (
            await standard_client.post(
                "/api/system/cert/csr/complete", json={"certificate_pem": "x"}
            )
        ).status_code == 403
        assert (
            await standard_client.post(
                "/api/system/cert/pkcs12", json={"pkcs12_base64": "", "passphrase": ""}
            )
        ).status_code == 403
        assert (
            await standard_client.post(
                "/api/system/cert/install", json={"current_password": "x"}
            )
        ).status_code == 403


async def test_generate_csr_returns_valid_pem(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    response = await client.post("/api/system/cert/csr")
    assert response.status_code == 200
    csr_pem = response.json()["csr_pem"]

    csr = x509.load_pem_x509_csr(csr_pem.encode())
    cn = csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    assert cn == "movie.ll.lan"


async def test_complete_csr_without_prior_csr_returns_409(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    _, cert = _self_sign("movie.ll.lan")
    response = await client.post(
        "/api/system/cert/csr/complete", json={"certificate_pem": _pem(cert)}
    )
    assert response.status_code == 409


async def test_complete_csr_with_matching_key_stages_it(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    csr_response = await client.post("/api/system/cert/csr")
    csr_pem = csr_response.json()["csr_pem"]
    csr = x509.load_pem_x509_csr(csr_pem.encode())

    # Simulate the external CA signing our CSR's actual public key (can't
    # re-derive the private key from the CSR — instead, self-sign with a
    # cert builder that reuses the CSR's own public key, matching what
    # stage_signed_certificate actually checks: the *public* key match).
    staged_key_path = tmp_path / "staging" / "key.pem"
    private_key = serialization.load_pem_private_key(staged_key_path.read_bytes(), password=None)
    _, cert = _self_sign("movie.ll.lan", private_key=private_key)

    response = await client.post(
        "/api/system/cert/csr/complete", json={"certificate_pem": _pem(cert)}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["staged"] is True
    assert data["installed"] is False
    assert data["common_name"] == "movie.ll.lan"
    assert data["subject_alt_names"] == ["movie.ll.lan"]
    assert data["days_until_expiry"] > 700


async def test_complete_csr_with_mismatched_key_returns_400(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    await client.post("/api/system/cert/csr")

    # A cert signed with a completely different, unrelated key.
    _, wrong_cert = _self_sign("movie.ll.lan")
    response = await client.post(
        "/api/system/cert/csr/complete", json={"certificate_pem": _pem(wrong_cert)}
    )
    assert response.status_code == 400


async def test_import_pkcs12_stages_cert_and_key(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    private_key, cert = _self_sign("movie.ll.lan")
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"movie.ll.lan",
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(b"testpass123"),
    )
    payload = {
        "pkcs12_base64": base64.b64encode(p12_bytes).decode(),
        "passphrase": "testpass123",
    }
    response = await client.post("/api/system/cert/pkcs12", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["staged"] is True
    assert data["common_name"] == "movie.ll.lan"


async def test_import_pkcs12_wrong_passphrase_returns_400(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    private_key, cert = _self_sign("movie.ll.lan")
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"movie.ll.lan",
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(b"testpass123"),
    )
    payload = {
        "pkcs12_base64": base64.b64encode(p12_bytes).decode(),
        "passphrase": "wrong-passphrase",
    }
    response = await client.post("/api/system/cert/pkcs12", json=payload)
    assert response.status_code == 400


async def test_install_without_anything_staged_returns_409(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    response = await client.post(
        "/api/system/cert/install", json={"current_password": "testpassword123"}
    )
    assert response.status_code == 409


async def test_install_rejects_wrong_password(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    private_key, cert = _self_sign("movie.ll.lan")
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"x", key=private_key, cert=cert, cas=None,
        encryption_algorithm=serialization.NoEncryption(),
    )
    await client.post(
        "/api/system/cert/pkcs12",
        json={"pkcs12_base64": base64.b64encode(p12_bytes).decode(), "passphrase": ""},
    )

    response = await client.post(
        "/api/system/cert/install", json={"current_password": "wrong-password"}
    )
    assert response.status_code == 401
    assert not (tmp_path / "trigger").exists()


async def test_install_with_staged_cert_and_correct_password_touches_trigger(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    private_key, cert = _self_sign("movie.ll.lan")
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"x", key=private_key, cert=cert, cas=None,
        encryption_algorithm=serialization.NoEncryption(),
    )
    await client.post(
        "/api/system/cert/pkcs12",
        json={"pkcs12_base64": base64.b64encode(p12_bytes).decode(), "passphrase": ""},
    )

    response = await client.post(
        "/api/system/cert/install", json={"current_password": "testpassword123"}
    )
    assert response.status_code == 202
    assert (tmp_path / "trigger").exists()


async def test_cert_status_reports_installed_when_live_cert_readable(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    live_path = tmp_path / "live" / "movie.ll.lan.crt"
    live_path.parent.mkdir(parents=True, exist_ok=True)
    _, cert = _self_sign("movie.ll.lan")
    live_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    response = await client.get("/api/system/cert")
    assert response.status_code == 200
    data = response.json()
    assert data["installed"] is True
    assert data["staged"] is False
    assert data["common_name"] == "movie.ll.lan"


async def test_cert_actions_are_audit_logged(client, tmp_path, monkeypatch):
    _setup_paths(tmp_path, monkeypatch)
    await client.post("/api/system/cert/csr")

    log = await client.get("/api/audit-log")
    actions = [e["action"] for e in log.json()["entries"]]
    assert "tls_cert.csr_generated" in actions
