import unicodedata

from pydantic import EmailStr, TypeAdapter, ValidationError

MIN_NAME_LENGTH = 2
MAX_NAME_LENGTH = 200
MAX_EMAIL_LENGTH = 320
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_ACCESS_TOKEN_LENGTH = 2048
MAX_PROJECT_DESCRIPTION_LENGTH = 2000
MAX_TASK_DESCRIPTION_LENGTH = 2000

_email_adapter = TypeAdapter(EmailStr)


def normalize_name(value: str, *, field_name: str) -> str:
    """Normalize a person or business name and enforce safe size limits."""

    normalized = " ".join(unicodedata.normalize("NFKC", value).split())
    if not MIN_NAME_LENGTH <= len(normalized) <= MAX_NAME_LENGTH:
        raise ValueError(
            f"{field_name} must be between {MIN_NAME_LENGTH} and "
            f"{MAX_NAME_LENGTH} characters"
        )
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise ValueError(f"{field_name} contains unsupported control characters")
    return normalized


def normalize_email(value: str) -> str:
    """Validate and normalize an email address for consistent uniqueness checks."""

    candidate = unicodedata.normalize("NFKC", value).strip().lower()
    if len(candidate) > MAX_EMAIL_LENGTH:
        raise ValueError(f"Email must not exceed {MAX_EMAIL_LENGTH} characters")
    try:
        return str(_email_adapter.validate_python(candidate))
    except ValidationError as error:
        raise ValueError("Invalid email format") from error


def normalize_project_description(value: str | None) -> str | None:
    """Normalize optional project copy while preserving an explicit empty value as null."""

    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).split())
    if not normalized:
        return None
    if len(normalized) > MAX_PROJECT_DESCRIPTION_LENGTH:
        raise ValueError(
            "Project description must not exceed "
            f"{MAX_PROJECT_DESCRIPTION_LENGTH} characters"
        )
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise ValueError("Project description contains unsupported control characters")
    return normalized


def normalize_task_description(value: str | None) -> str | None:
    """Normalize optional task copy and reject control characters."""

    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).split())
    if not normalized:
        return None
    if len(normalized) > MAX_TASK_DESCRIPTION_LENGTH:
        raise ValueError(
            "Task description must not exceed "
            f"{MAX_TASK_DESCRIPTION_LENGTH} characters"
        )
    if any(unicodedata.category(character).startswith("C") for character in normalized):
        raise ValueError("Task description contains unsupported control characters")
    return normalized


def normalize_password(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def validate_password(value: str) -> str:
    """Validate plaintext at the boundary before it is hashed and discarded."""

    normalized = normalize_password(value)
    if not MIN_PASSWORD_LENGTH <= len(normalized) <= MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be between {MIN_PASSWORD_LENGTH} and "
            f"{MAX_PASSWORD_LENGTH} characters"
        )
    return normalized

