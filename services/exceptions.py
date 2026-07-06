"""Typed application errors, surfaced to the user via st.error()."""


class AppError(Exception):
    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(message)


class UnsupportedFileTypeError(AppError):
    pass


class FileTooLargeError(AppError):
    pass


class TextExtractionError(AppError):
    pass


class EmptyInputError(AppError):
    pass


class ConfigurationError(AppError):
    pass
