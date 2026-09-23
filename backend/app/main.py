import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    analytics,
    anthem,
    attributes,
    audit_log,
    auth,
    health,
    library_backup,
    messages,
    monitor,
    movies,
    plex,
    polls,
    posters,
    reservations,
    scan,
    screening_requests,
    screenings,
    settings as settings_api,
    system,
    tags,
    tv_shows,
    users,
)
from app.api.deps import COOKIE_NAME
from app.core.config import settings
from app.core.security import create_access_token, decode_access_token
from app.core.errors import (
    AccountDisabledError,
    AnthemNotConfiguredError,
    AnthemSessionBusyError,
    AccountPendingError,
    AccountRejectedError,
    CannotTargetSelfError,
    CertKeyMismatchError,
    DeployScriptNotFoundError,
    InvalidBackupError,
    ClassificationRequiredError,
    DuplicateBarcodeError,
    DuplicatePollCandidateError,
    InvalidCredentialsError,
    InvalidResetTokenError,
    InvalidUserStatusTransitionError,
    InvalidMessageTemplateError,
    LastAdminError,
    MessageNotFoundError,
    MessageTemplateNotFoundError,
    MovieNotFoundError,
    MustChangePasswordError,
    InvalidSeatError,
    NoCertStagedError,
    NoRecipientsError,
    NoPendingCsrError,
    NotAuthenticatedError,
    NotAuthorizedError,
    NotSupportedOnThisPlatformError,
    InvalidPollCandidateError,
    PasswordResetUnavailableError,
    Pkcs12ImportError,
    PlexFilterUnavailableError,
    PollCandidateSuggestionNotFoundError,
    PollNotFoundError,
    PollNotOpenError,
    PollNotPendingError,
    PreferredAtRequiredError,
    ReservationNotFoundError,
    ReservationTargetError,
    SeatTakenError,
    SerialNumberConflictError,
    ScreeningNotFoundError,
    ScreeningRequestNotFoundError,
    TestModeActiveError,
    TmdbNotFoundError,
    TmdbRateLimitedError,
    TmdbUnavailableError,
    TvShowNotFoundError,
    UserNotFoundError,
    UserNotPendingError,
    UsernameTakenError,
    WishlistNotPendingError,
)
from app.db import close_client, get_client, get_database
from app.repositories import (
    audit_log_repository,
    message_repository,
    movie_repository,
    poll_repository,
    poster_cache_repository,
    reservation_repository,
    screening_repository,
    screening_request_repository,
    tag_repository,
    tv_show_repository,
    user_repository,
    visit_repository,
)
from app.services import plex_service, system_settings_service

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("moviedb")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.using_insecure_jwt_secret:
        logger.warning(
            "JWT_SECRET_KEY er ikke sat — bruger den usikre standard-vaerdi. "
            "Saet en unik hemmelighed i .env foer denne app naar udenfor lokal udvikling "
            "(python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
        )

    get_client()
    db = get_database()
    await system_settings_service.apply_overrides_on_startup(db)
    await movie_repository.ensure_indexes(db)
    await tv_show_repository.ensure_indexes(db)
    await tag_repository.ensure_indexes(db)
    await user_repository.ensure_indexes(db)
    await screening_request_repository.ensure_indexes(db)
    await screening_repository.ensure_indexes(db)
    await audit_log_repository.ensure_indexes(db)
    await message_repository.ensure_indexes(db)
    await visit_repository.ensure_indexes(db)
    await reservation_repository.ensure_indexes(db)
    await poster_cache_repository.ensure_indexes(db)
    await poll_repository.ensure_indexes(db)
    logger.info("MongoDB client initialized (%s)", settings.mongo_db_name)

    # Feature #181 (Jan: "vi skal have en automatisk scan af plex media
    # server for ny film og tv serie"). Én baggrunds-task for hele appens
    # levetid — annulleres eksplicit ved nedlukning, ellers ville en
    # ventende `asyncio.sleep` (op til `plex_auto_import_interval_minutes`
    # lang) forsinke en ren shutdown.
    auto_import_task = asyncio.create_task(plex_service.run_auto_import_loop())

    yield

    auto_import_task.cancel()
    await close_client()


app = FastAPI(title="Movie Database API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Feature #148 — 8 timers skydende idle-timeout. Har requesten en gyldig
# session-cookie, gen-udstedes den med en frisk 8-timers levetid, så en aktiv
# bruger aldrig smides ud midt i arbejdet; 8 timers inaktivitet lader den
# udløbe. Undtaget: /api/auth (login/register sætter cookien selv, logout
# sletter den — en refresh her ville genoplive en udlogget session) og
# baggrunds-polls markeret med X-Background-Poll (fx besked-pollen hvert 20.
# sek, feature #135), så et åbent men uovervåget vindue faktisk timeouter.
BACKGROUND_POLL_HEADER = "x-background-poll"


@app.middleware("http")
async def _sliding_session(request: Request, call_next):
    response = await call_next(request)
    if (
        not request.url.path.startswith("/api/auth")
        and request.headers.get(BACKGROUND_POLL_HEADER) != "1"
    ):
        token = request.cookies.get(COOKIE_NAME)
        if token:
            payload = decode_access_token(token)
            if payload and payload.get("sub"):
                response.set_cookie(
                    key=COOKIE_NAME,
                    value=create_access_token(payload["sub"]),
                    httponly=True,
                    secure=settings.cookie_secure,
                    samesite="lax",
                    max_age=settings.jwt_expire_minutes * 60,
                    path="/",
                )
    return response


@app.exception_handler(MovieNotFoundError)
async def movie_not_found_handler(request: Request, exc: MovieNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(TvShowNotFoundError)
async def tv_show_not_found_handler(request: Request, exc: TvShowNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ScreeningRequestNotFoundError)
async def screening_request_not_found_handler(
    request: Request, exc: ScreeningRequestNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ScreeningNotFoundError)
async def screening_not_found_handler(request: Request, exc: ScreeningNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(PollNotFoundError)
async def poll_not_found_handler(request: Request, exc: PollNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(PollNotOpenError)
async def poll_not_open_handler(request: Request, exc: PollNotOpenError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidPollCandidateError)
async def invalid_poll_candidate_handler(request: Request, exc: InvalidPollCandidateError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(PollNotPendingError)
async def poll_not_pending_handler(request: Request, exc: PollNotPendingError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(DuplicatePollCandidateError)
async def duplicate_poll_candidate_handler(
    request: Request, exc: DuplicatePollCandidateError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(PollCandidateSuggestionNotFoundError)
async def poll_candidate_suggestion_not_found_handler(
    request: Request, exc: PollCandidateSuggestionNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(PreferredAtRequiredError)
async def preferred_at_required_handler(
    request: Request, exc: PreferredAtRequiredError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ClassificationRequiredError)
async def classification_required_handler(
    request: Request, exc: ClassificationRequiredError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(DuplicateBarcodeError)
async def duplicate_barcode_handler(request: Request, exc: DuplicateBarcodeError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(SerialNumberConflictError)
async def serial_number_conflict_handler(
    request: Request, exc: SerialNumberConflictError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(TmdbNotFoundError)
async def tmdb_not_found_handler(request: Request, exc: TmdbNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(TmdbUnavailableError)
async def tmdb_unavailable_handler(request: Request, exc: TmdbUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(TmdbRateLimitedError)
async def tmdb_rate_limited_handler(request: Request, exc: TmdbRateLimitedError) -> JSONResponse:
    """Without this handler the exception propagated unhandled into a raw
    500 on every endpoint except sync_all_from_tmdb (which catches it
    itself) — verified empirically across 4 endpoints during the 2026-08-02
    code review (BUGS.md #24)."""
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.exception_handler(UsernameTakenError)
async def username_taken_handler(request: Request, exc: UsernameTakenError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidCredentialsError)
async def invalid_credentials_handler(
    request: Request, exc: InvalidCredentialsError
) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(InvalidResetTokenError)
async def invalid_reset_token_handler(request: Request, exc: InvalidResetTokenError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(PasswordResetUnavailableError)
async def password_reset_unavailable_handler(
    request: Request, exc: PasswordResetUnavailableError
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(NotAuthenticatedError)
async def not_authenticated_handler(request: Request, exc: NotAuthenticatedError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(NotAuthorizedError)
async def not_authorized_handler(request: Request, exc: NotAuthorizedError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(AccountPendingError)
async def account_pending_handler(request: Request, exc: AccountPendingError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(AccountRejectedError)
async def account_rejected_handler(request: Request, exc: AccountRejectedError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(AccountDisabledError)
async def account_disabled_handler(request: Request, exc: AccountDisabledError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(MustChangePasswordError)
async def must_change_password_handler(
    request: Request, exc: MustChangePasswordError
) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(UserNotPendingError)
async def user_not_pending_handler(request: Request, exc: UserNotPendingError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(WishlistNotPendingError)
async def wishlist_not_pending_handler(
    request: Request, exc: WishlistNotPendingError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidUserStatusTransitionError)
async def invalid_user_status_transition_handler(
    request: Request, exc: InvalidUserStatusTransitionError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(CannotTargetSelfError)
async def cannot_target_self_handler(request: Request, exc: CannotTargetSelfError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(UserNotFoundError)
async def user_not_found_handler(request: Request, exc: UserNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(LastAdminError)
async def last_admin_handler(request: Request, exc: LastAdminError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidBackupError)
async def invalid_backup_handler(request: Request, exc: InvalidBackupError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(DeployScriptNotFoundError)
async def deploy_script_not_found_handler(
    request: Request, exc: DeployScriptNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(NotSupportedOnThisPlatformError)
async def not_supported_on_platform_handler(
    request: Request, exc: NotSupportedOnThisPlatformError
) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": str(exc)})


@app.exception_handler(NoPendingCsrError)
async def no_pending_csr_handler(request: Request, exc: NoPendingCsrError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(CertKeyMismatchError)
async def cert_key_mismatch_handler(request: Request, exc: CertKeyMismatchError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(Pkcs12ImportError)
async def pkcs12_import_handler(request: Request, exc: Pkcs12ImportError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(MessageNotFoundError)
async def message_not_found_handler(request: Request, exc: MessageNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(NoRecipientsError)
async def no_recipients_handler(request: Request, exc: NoRecipientsError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(MessageTemplateNotFoundError)
async def message_template_not_found_handler(
    request: Request, exc: MessageTemplateNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InvalidMessageTemplateError)
async def invalid_message_template_handler(
    request: Request, exc: InvalidMessageTemplateError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(TestModeActiveError)
async def test_mode_active_handler(request: Request, exc: TestModeActiveError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(NoCertStagedError)
async def no_cert_staged_handler(request: Request, exc: NoCertStagedError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ReservationNotFoundError)
async def reservation_not_found_handler(
    request: Request, exc: ReservationNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InvalidSeatError)
async def invalid_seat_handler(request: Request, exc: InvalidSeatError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(PlexFilterUnavailableError)
async def plex_filter_unavailable_handler(
    request: Request, exc: PlexFilterUnavailableError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ReservationTargetError)
async def reservation_target_handler(request: Request, exc: ReservationTargetError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(SeatTakenError)
async def seat_taken_handler(request: Request, exc: SeatTakenError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(AnthemNotConfiguredError)
async def anthem_not_configured_handler(
    request: Request, exc: AnthemNotConfiguredError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(AnthemSessionBusyError)
async def anthem_session_busy_handler(
    request: Request, exc: AnthemSessionBusyError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


app.include_router(health.router)
app.include_router(analytics.router)
app.include_router(audit_log.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(movies.router)
app.include_router(tv_shows.router)
app.include_router(tags.router)
app.include_router(attributes.router)
app.include_router(scan.router)
app.include_router(plex.router)
app.include_router(settings_api.router)
app.include_router(system.router)
app.include_router(library_backup.router)
app.include_router(screening_requests.router)
app.include_router(screenings.router)
app.include_router(polls.router)
app.include_router(reservations.router)
app.include_router(messages.router)
app.include_router(posters.router)
app.include_router(monitor.router)
app.include_router(anthem.router)
