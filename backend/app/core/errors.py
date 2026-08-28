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


class PreferredAtRequiredError(Exception):
    """Feature #176/#177/#186 — raised by `screening_service.enforce_preferred_at`
    when a screening request is missing `preferred_at` and
    `settings.require_preferred_at` is on (the default). Applies the same
    way to every role since feature #186."""

    def __init__(self):
        super().__init__("Angiv venligst hvornår du gerne vil se den.")


class ClassificationRequiredError(Exception):
    """Feature #196 — "flyt til bibliotek" fra ønskelisten. Samme krav som
    `MovieCreate`/`TvShowCreate`s `require_media_type_and_format_for_library`-
    validator (feature #92), men håndhævet her i update-stien: at flytte en
    ønskeliste-post ind i biblioteket er reelt den samme overgang som at
    OPRETTE biblioteks-posten, blot via PATCH i stedet for POST. Uden denne
    ville kravet kunne omgås ved først at oprette posten på ønskelisten
    (undtaget kravet) og derefter flytte den uden format/medietype sat —
    CLAUDE.md regel 16: håndhæves i backend, ikke kun som UI-bekvemmelighed."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(
            f"{' og '.join(missing)} skal angives for en post i biblioteket "
            "(kun ønskelisten er undtaget)"
        )


class DuplicateBarcodeError(Exception):
    def __init__(self, barcode: str):
        self.barcode = barcode
        super().__init__(f"An item with barcode '{barcode}' already exists")


class SerialNumberConflictError(Exception):
    """BUGS.md #56 — en byt-plads-omnummerering endte alligevel med to poster
    på samme (nummer, serie). Bør ikke ske efter at opslaget blev serie-bevidst,
    men en samtidig skrivning kan stadig nå at optage nummeret mellem tjek og
    skrivning. Oversættes til en pæn 409 frem for en rå 500 (CLAUDE.md regel 16
    — rammeværkets/databasens fejl skal ikke slippe rå ud til brugeren)."""

    def __init__(self, serial_number: int):
        self.serial_number = serial_number
        super().__init__(
            f"Serienummer {serial_number} er allerede i brug — prøv igen."
        )


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


class MustChangePasswordError(Exception):
    """Feature #172 — en admin-nulstilling (#171) tvinger brugeren til selv
    at skifte adgangskoden ved næste kontakt med API'et, i stedet for at
    kunne fortsætte for evigt på den midlertidige kode. Rejst af
    `api.deps.get_current_user`, undtagen for det ene endpoint der skal
    kunne rette tilstanden (se `get_current_user_allow_password_change`) —
    uden den undtagelse ville dette være en permanent lockout (CLAUDE.md
    regel 16)."""

    def __init__(self):
        super().__init__("Du skal skifte din adgangskode før du kan fortsætte.")


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


class WishlistNotPendingError(Exception):
    """Guards approve/reject (feature #144/#165) against being pointed at an
    item that isn't actually a pending wish — e.g. re-clicking reject on an
    already-approved or already-removed wish. Mirrors UserNotPendingError."""

    def __init__(self, item_id: str):
        self.item_id = item_id
        super().__init__(f"Item is not a pending wish: {item_id}")


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


class InvalidBackupError(Exception):
    """BUGS.md #41 — refuses a restore payload that would leave the system
    with no admin able to log in. Every collection list on `SystemBackup`
    has an empty-list default, so a truncated, corrupt or simply wrong file
    used to validate cleanly and then wipe every collection (restore is
    delete-all-then-insert), returning 200 OK with zero counts. Checked
    *before* anything is deleted, so a rejected restore leaves the existing
    data completely untouched."""

    def __init__(self, reason: str):
        super().__init__(reason)


class NotSupportedOnThisPlatformError(Exception):
    """Feature #154 — genstart af tjeneste/server afhænger af systemd og
    findes derfor kun i produktion (Linux), ikke under lokal udvikling
    (Windows/macOS). CPU/RAM/disk-metrikker virker overalt (psutil er
    cross-platform); det er kun selve genstarts-handlingerne der er
    Linux-only."""

    def __init__(self, action: str):
        self.action = action
        super().__init__(f"{action} er kun understøttet i produktion (Linux/systemd), ikke her.")


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


class MessageNotFoundError(Exception):
    """Feature #100 — beskeden findes ikke, eller den aktuelle bruger er
    ikke blandt dens modtagere. Samme fejl for begge tilfælde med vilje:
    hvilke beskeder der findes til andre brugere, er ikke ens egen
    oplysning."""

    def __init__(self, message_id: str):
        super().__init__(f"Besked {message_id} findes ikke")


class NoRecipientsError(Exception):
    """Feature #100 — en rundsendt besked uden nogen at sende til. Typisk
    fordi afsenderen er den eneste aktive bruger; beskeden ville ellers se
    ud som sendt uden at nå nogen."""

    def __init__(self):
        super().__init__("Der er ingen aktive brugere at sende beskeden til")


class ReservationNotFoundError(Exception):
    """Feature #133 — sæde-reservationen findes ikke (eller er allerede
    annulleret/afvist af en anden)."""

    def __init__(self, reservation_id: str):
        self.reservation_id = reservation_id
        super().__init__(f"Sæde-reservation {reservation_id} findes ikke")


class InvalidSeatError(Exception):
    """Feature #133 — et sæde-id der ikke findes i Voldby BIOs faste 14-sæde-sal."""

    def __init__(self, seat_id: str):
        self.seat_id = seat_id
        super().__init__(f"Ukendt sæde: {seat_id}")


class PlexFilterUnavailableError(Exception):
    """Feature #156 — et Plex-filter (badge i biblioteks-filteret) blev
    anvendt, men Plex er ikke konfigureret eller kan ikke nås lige nu. Uden
    denne fejl ville filteret enten stille springes over (viser film der ikke
    reelt er bekræftet) eller give et vilkårligt tomt/fuldt resultat — begge
    dele misvisende for en bruger der eksplicit har bedt om et Plex-filter."""

    def __init__(self):
        super().__init__("Plex er ikke konfigureret eller kan ikke nås — kan ikke filtrere på Plex.")


class AnthemNotConfiguredError(Exception):
    """Feature #183 — AVM 70-diagnostikken kræver `anthem_host` sat under
    Indstillinger → Eksterne API-nøgler, samme "ikke konfigureret"-mønster
    som Plex-importen."""

    def __init__(self):
        super().__init__(
            "Anthem er ikke konfigureret — sæt IP/port under Indstillinger → Eksterne API-nøgler."
        )


class AnthemSessionBusyError(Exception):
    """Feature #183 — AVM 70 accepterer kun én netværksklient ad gangen; et
    andet forsøg på at åbne en diagnostik-stream mens én allerede kører
    skal afvises pænt i stedet for stille at kæmpe om forbindelsen."""

    def __init__(self):
        super().__init__(
            "Der kører allerede en diagnostik-session (fra denne eller en anden fane)."
        )


class SeatTakenError(Exception):
    """Feature #133 — sædet er allerede reserveret/optaget for denne
    fremvisning (eller blokeret af et globalt admin-hold). Oversættes til en
    pæn 409 frem for en rå DuplicateKeyError-500 (CLAUDE.md regel 16 — også
    databasens egne fejl skal fanges), så to gæster der griber samme sæde
    samtidig får en forståelig besked."""

    def __init__(self, seat_number: int):
        self.seat_number = seat_number
        super().__init__(f"Sæde {seat_number} er allerede optaget — vælg et andet.")
