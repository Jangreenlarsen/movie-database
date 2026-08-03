from datetime import datetime

from pydantic import BaseModel, Field


class CertStatus(BaseModel):
    """Feature #73 — describes either the currently-installed production
    certificate or a staged-but-not-yet-installed one. Deliberately only
    ever carries public certificate fields (subject/SAN/validity dates) —
    never the private key or any passphrase, matching CLAUDE.md regel 6's
    "write-only secrets" principle extended to key material in general."""

    installed: bool
    staged: bool = False
    common_name: str | None = None
    subject_alt_names: list[str] = Field(default_factory=list)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    days_until_expiry: int | None = None


class CsrResult(BaseModel):
    csr_pem: str


class CertSignedComplete(BaseModel):
    certificate_pem: str


class Pkcs12Import(BaseModel):
    # Base64 rather than raw bytes — this is a JSON API, not multipart.
    pkcs12_base64: str
    passphrase: str = ""


class CertInstallConfirm(BaseModel):
    """Same pattern as `DatabaseResetConfirm` (feature #67) — a broken
    install can take production HTTPS offline entirely, at least as
    irreversible as a database reset, so confirmation is the admin's own
    password, not just a click."""

    current_password: str
