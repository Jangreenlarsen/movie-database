class MovieNotFoundError(Exception):
    def __init__(self, movie_id: str):
        self.movie_id = movie_id
        super().__init__(f"Movie not found: {movie_id}")


class DuplicateBarcodeError(Exception):
    def __init__(self, barcode: str):
        self.barcode = barcode
        super().__init__(f"A movie with barcode '{barcode}' already exists")
