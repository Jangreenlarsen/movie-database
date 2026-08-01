class MovieNotFoundError(Exception):
    def __init__(self, movie_id: str):
        self.movie_id = movie_id
        super().__init__(f"Movie not found: {movie_id}")


class DuplicateBarcodeError(Exception):
    def __init__(self, barcode: str):
        self.barcode = barcode
        super().__init__(f"A movie with barcode '{barcode}' already exists")


class TmdbNotFoundError(Exception):
    def __init__(self, tmdb_id: int):
        self.tmdb_id = tmdb_id
        super().__init__(f"TMDb movie not found: {tmdb_id}")


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


class UserNotFoundError(Exception):
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"User not found: {user_id}")


class LastAdminError(Exception):
    def __init__(self):
        super().__init__("Cannot remove the last remaining admin")
