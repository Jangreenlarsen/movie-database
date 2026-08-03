import base64
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from app.core.config import settings
from app.core.errors import (
    CertKeyMismatchError,
    NoCertStagedError,
    NoPendingCsrError,
    Pkcs12ImportError,
)
from app.models.cert import CertStatus, CsrResult

# Feature #73 — TLS certificate management for production's Caddy-served
# `movie.ll.lan` (see DEPLOYMENT.md/BUGS.md #23). `moviedb-backend` can
# neither write to /etc/caddy/certs (root:caddy, 640) nor use sudo
# (ProtectSystem=strict + NoNewPrivileges=true) — so this service only ever
# stages a new key/cert pair inside its own writable area and touches a
# trigger file; a separate, root-owned systemd path-unit (mirroring
# moviedb-deploy-restart.path/.service, BUGS.md #18) does the actual
# privileged install. Never returns a private key or passphrase to the
# frontend at any point.

_KEY_FILENAME = "key.pem"
_CERT_FILENAME = "cert.pem"


def _staging_dir() -> Path:
    path = Path(settings.cert_staging_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _staged_key_path() -> Path:
    return _staging_dir() / _KEY_FILENAME


def _staged_cert_path() -> Path:
    return _staging_dir() / _CERT_FILENAME


def _cert_to_status(cert: x509.Certificate, *, installed: bool, staged: bool) -> CertStatus:
    common_names = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    common_name = common_names[0].value if common_names else None

    sans: list[str] = []
    try:
        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        sans = san_ext.value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        pass

    valid_until = cert.not_valid_after_utc
    days_until_expiry = (valid_until - datetime.now(timezone.utc)).days

    return CertStatus(
        installed=installed,
        staged=staged,
        common_name=common_name,
        subject_alt_names=sans,
        valid_from=cert.not_valid_before_utc,
        valid_until=valid_until,
        days_until_expiry=days_until_expiry,
    )


def get_status() -> CertStatus:
    """Reports on the currently *installed* production certificate (read
    from `cert_live_path`) if the backend can read it, or a *staged* one
    (prepared but not yet installed) as a fallback — never both/neither
    ambiguously. Never raises: missing/unreadable files just mean nothing
    to report yet."""
    live_path = Path(settings.cert_live_path)
    try:
        cert = x509.load_pem_x509_certificate(live_path.read_bytes())
        return _cert_to_status(cert, installed=True, staged=False)
    except (OSError, ValueError):
        pass

    staged_cert_path = _staged_cert_path()
    try:
        cert = x509.load_pem_x509_certificate(staged_cert_path.read_bytes())
        return _cert_to_status(cert, installed=False, staged=True)
    except (OSError, ValueError):
        pass

    return CertStatus(installed=False, staged=False)


def generate_csr() -> CsrResult:
    """Generates a fresh ECDSA P-256 key + CSR for `cert_common_name`,
    matching the manual process from BUGS.md #23. The key is written to the
    staging area (never returned) — only the CSR (public, safe to display/
    copy/download) is returned. Overwrites any previous not-yet-completed
    CSR attempt; only one can be pending at a time."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, settings.cert_common_name)]))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(settings.cert_common_name)]), critical=False
        )
        .sign(private_key, hashes.SHA256())
    )

    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    _staged_key_path().write_bytes(key_pem)
    _staged_key_path().chmod(0o600)
    # Clear any previously-staged cert — it belonged to whatever key/CSR
    # came before this one and can no longer be paired with anything.
    _staged_cert_path().unlink(missing_ok=True)

    csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode()
    return CsrResult(csr_pem=csr_pem)


def stage_signed_certificate(certificate_pem: str) -> CertStatus:
    """Pairs an externally-signed certificate with the pending private key
    from `generate_csr()`. Verifies the public keys actually match — the
    same check Claude performed manually via SSH under BUGS.md #23 — before
    staging it for install."""
    key_path = _staged_key_path()
    if not key_path.is_file():
        raise NoPendingCsrError()

    private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)

    try:
        cert = x509.load_pem_x509_certificate(certificate_pem.encode())
    except ValueError as exc:
        raise Pkcs12ImportError(str(exc)) from exc

    if cert.public_key().public_numbers() != private_key.public_key().public_numbers():
        raise CertKeyMismatchError()

    _staged_cert_path().write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return _cert_to_status(cert, installed=False, staged=True)


def stage_pkcs12(pkcs12_base64: str, passphrase: str) -> CertStatus:
    """Parses an uploaded PKCS12 (.pfx/.p12) bundle and stages its cert+key
    pair for install. The passphrase is used only transiently to decrypt —
    never logged or persisted anywhere."""
    try:
        raw = base64.b64decode(pkcs12_base64)
    except Exception as exc:
        raise Pkcs12ImportError("ugyldig base64-data") from exc

    try:
        private_key, cert, _ = pkcs12.load_key_and_certificates(raw, passphrase.encode())
    except ValueError as exc:
        raise Pkcs12ImportError(str(exc)) from exc

    if private_key is None or cert is None:
        raise Pkcs12ImportError("PKCS12-filen mangler enten certifikat eller privat nøgle")

    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    _staged_key_path().write_bytes(key_pem)
    _staged_key_path().chmod(0o600)
    _staged_cert_path().write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    return _cert_to_status(cert, installed=False, staged=True)


def trigger_install() -> None:
    """Touches the install-trigger file, picked up by the root-owned
    `moviedb-cert-install.path`/`.service` systemd units (see
    DEPLOYMENT.md) — same detached, fire-and-forget shape as
    `deploy_service.trigger_deploy()`. Raises if nothing is actually staged,
    so a stray click can't trigger an install of nothing."""
    if not _staged_key_path().is_file() or not _staged_cert_path().is_file():
        raise NoCertStagedError()

    Path(settings.cert_install_trigger_path).touch()
