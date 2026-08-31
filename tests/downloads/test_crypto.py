import pytest
from cryptography.fernet import Fernet, InvalidToken

from downloads.crypto import (
    decrypt_context,
    encrypt_context,
    issue_public_token,
    verify_public_token,
)


def test_resolver_context_round_trip_does_not_leak_plaintext():
    keys = [Fernet.generate_key().decode()]
    context = {"cookies": "session=very-secret", "referer": "https://example.test/1"}

    encrypted = encrypt_context(context, keys)

    assert "very-secret" not in encrypted
    assert decrypt_context(encrypted, keys) == context


def test_old_key_can_decrypt_after_rotation():
    old_key = Fernet.generate_key().decode()
    encrypted = encrypt_context({"token": "old"}, [old_key])

    assert decrypt_context(encrypted, [Fernet.generate_key().decode(), old_key]) == {"token": "old"}


def test_unknown_key_rejects_ciphertext():
    encrypted = encrypt_context({"token": "secret"}, [Fernet.generate_key().decode()])

    with pytest.raises(InvalidToken):
        decrypt_context(encrypted, [Fernet.generate_key().decode()])


def test_public_token_signature_is_verified_before_lookup():
    token = issue_public_token("signing-secret")

    assert verify_public_token(token, "signing-secret") is True
    assert verify_public_token(f"{token[:-1]}x", "signing-secret") is False
    assert verify_public_token("malformed", "signing-secret") is False
