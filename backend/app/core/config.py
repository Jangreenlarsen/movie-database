from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_JWT_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "moviedb"

    tmdb_api_token: str = ""
    upc_api_key: str = ""
    discogs_token: str = ""

    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"

    jwt_secret_key: str = INSECURE_DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 30  # 30 dage
    cookie_secure: bool = False

    # OTA-opdatering (feature #20) — kun meningsfuldt i produktion, se DEPLOYMENT.md.
    # Scriptet ligger bevidst uden for git-working-tree'en (/opt/moviedb), så
    # `git pull` aldrig overskriver den fil der er ved at blive eksekveret.
    deploy_script_path: str = "/opt/moviedb-deploy.sh"
    deploy_log_path: str = "/opt/moviedb-deploy.log"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def using_insecure_jwt_secret(self) -> bool:
        return self.jwt_secret_key == INSECURE_DEFAULT_JWT_SECRET


settings = Settings()

# Immutable snapshot of the .env-derived values, taken once at import time —
# used to restore the "no override" value when an admin clears a custom
# key via `PATCH /api/settings/system` (feature #36). `settings` itself gets
# mutated in place at runtime (see system_settings_service), so this is the
# only remaining record of what .env actually provided.
ENV_DEFAULT_API_KEYS: dict[str, str] = {
    "tmdb_api_token": settings.tmdb_api_token,
    "upc_api_key": settings.upc_api_key,
    "discogs_token": settings.discogs_token,
}
