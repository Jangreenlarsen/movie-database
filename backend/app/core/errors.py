class MovieNotFoundError(Exception):
    def __init__(self, movie_id: str):
        self.movie_id = movie_id
        super().__init__(f"Movie not found: {movie_id}")


class TvShowNotFoundError(Exception):
    def __init__(self, tv_show_id: str):
        self.tv_show_id = tv_show_id
        super().__init__(f"TV show not found: {tv_show_id}")


class ScreeningRequestNotFoundError(Exception):
    def __init__(self, request_id: str):
        self.request_id = request_id
        super().__init__(f"Screening request not found: {request_id}")


class ScreeningNotFoundError(Exception):
    def __init__(self, screening_id: str):
        self.screening_id = screening_id
        super().__init__(f"Screening not found: {screening_id}")


class DuplicateBarcodeError(Exception):
    def __init__(self, barcode: str):
        self.barcode = barcode
        super().__init__(f"An item with barcode '{barcode}' already exists")


class TmdbNotFoundError(Exception):
    """Covers both /movie/{id} and /tv/{id} 404s — reused by
    tmdb_client.get_movie_details, get_tv_show_details and
    get_season_details (feature #47), so the message stays media-agnostic
    rather than hardcoding "movie"."""

    def __init__(self, tmdb_id: int):
        self.tmdb_id = tmdb_id
        super().__init__(f"TMDb-ressource ikke fundet: {tmdb_id}")


class TmdbUnavailableError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class TmdbRateLimitedError(Exception):
    """Distinct from TmdbUnavailableError so callers doing bulk TMDb work
    (movie_service.sync_all_from_tmdb) can stop early instead of treating a
    429 as N independent per-movie failures."""

    def __init__(self):
        super().__init__("TMDb rate-limit ramt (429)")


class UsernameTakenError(Exception):
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"Username '{username}' is already taken")


class InvalidCredentialsError(Exception):
    def __init__(self):
        super().__init__("Invalid username or password")


class NotAuthenticatedError(Exception):
    def __init__(self):
        super().__init__("Not authenticated")


class NotAuthorizedError(Exception):
    def __init__(self, message: str = "Admin rights required"):
        super().__init__(message)


class AccountPendingError(Exception):
    def __init__(self):
        super().__init__("Din konto afventer godkendelse fra en administrator.")


class AccountRejectedError(Exception):
    def __init__(self):
        super().__init__("Din konto er blevet afvist. Kontakt en administrator.")


class AccountDisabledError(Exception):
    """Feature #80 — distinct message from AccountRejectedError, since this
    means an admin locked an already-active account, not that a
    registration was declined."""

    def __init__(self):
        super().__init__("Din konto er blevet deaktiveret af en administrator.")


class UserNotPendingError(Exception):
    """Guards approve/reject (feature #66) against being pointed at a user
    who isn't actually pending — e.g. re-clicking reject on an already-active
    admin would otherwise silently lock them out."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"User is not pending approval: {user_id}")


class InvalidUserStatusTransitionError(Exception):
    """Feature #80 — guards the broadened status endpoint against nonsensical
    transitions (e.g. "activating" a rejected user, or "disabling" a
    pending one) that the plain Literal type on UserStatusUpdate can't
    express on its own."""

    def __init__(self, current_status: str, requested_status: str):
        self.current_status = current_status
        self.requested_status = requested_status
        super().__init__(
            f"Kan ikke skifte status fra '{current_status}' til '{requested_status}'."
        )


class UserNotFoundError(Exception):
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"User not found: {user_id}")


class CannotTargetSelfError(Exception):
    """Feature #80 — an admin can't disable/delete their own account via
    this panel (must use a different admin account), avoiding an easy
    self-inflicted lockout mistake."""

    def __init__(self):
        super().__init__("Du kan ikke udføre denne handling på din egen konto.")


class LastAdminError(Exception):
    def __init__(self):
        super().__init__("Cannot remove the last remaining admin")


class DeployScriptNotFoundError(Exception):
    def __init__(self, path: str):
        self.path = path
        super().__init__(
            f"Deploy-script ikke fundet eller ikke eksekverbart: {path} — se DEPLOYMENT.md"
        )


class NoPendingCsrError(Exception):
    """Feature #73 — raised if an admin tries to upload a signed certificate
    without ever having generated a CSR (no pending private key to pair it
    with)."""

    def __init__(self):
        super().__init__("Ingen ventende CSR fundet — generér en CSR først.")


class CertKeyMismatchError(Exception):
    """Feature #73 — the uploaded signed certificate's public key doesn't
    match the pending private key it's meant to pair with. Same check Claude
    performed manually via SSH under BUGS.md #23, now automated."""

    def __init__(self):
        super().__init__(
            "Certifikatets offentlige nøgle matcher ikke den ventende private nøgle."
        )


class Pkcs12ImportError(Exception):
    def __init__(self, reason: str):
        super().__init__(f"Kunne ikke læse PKCS12-filen: {reason}")


class NoCertStagedError(Exception):
    """Feature #73 — raised if `install` is triggered with nothing actually
    staged (neither a completed CSR nor an imported PKCS12)."""

    def __init__(self):
        super().__init__("Intet certifikat er klar til installation.")
