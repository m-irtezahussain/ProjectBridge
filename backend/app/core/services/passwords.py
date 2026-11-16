from pwdlib import PasswordHash

from app.core.validation import normalize_password, validate_password


class PasswordService:
    """Hash and verify passwords with pwdlib's recommended Argon2id settings."""

    def __init__(self) -> None:
        self._password_hash = PasswordHash.recommended()

    def hash_password(self, password: str) -> str:
        normalized = validate_password(password)
        return self._password_hash.hash(normalized)

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            normalized = normalize_password(password)
            return self._password_hash.verify(normalized, password_hash)
        except (ValueError, TypeError):
            return False


password_service = PasswordService()

