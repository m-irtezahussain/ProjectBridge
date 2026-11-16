import pytest

from app.core.services.passwords import PasswordService


def test_passwords_are_stored_as_argon2id_hashes() -> None:
    service = PasswordService()
    password = "a long memorable passphrase"

    password_hash = service.hash_password(password)

    assert password_hash.startswith("$argon2id$")
    assert password not in password_hash
    assert service.verify_password(password, password_hash) is True
    assert service.verify_password("a different passphrase", password_hash) is False


def test_short_password_is_rejected() -> None:
    service = PasswordService()

    with pytest.raises(ValueError, match="between 15 and 128"):
        service.hash_password("too short")

