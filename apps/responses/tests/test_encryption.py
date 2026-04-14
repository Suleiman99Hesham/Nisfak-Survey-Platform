import pytest
from cryptography.fernet import Fernet
from django.test import override_settings

from apps.responses.services.encryption import FieldEncryption, get_encryption


TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture
def encryption():
    with override_settings(ENCRYPTION_KEY=TEST_KEY):
        yield FieldEncryption()


class TestFieldEncryption:
    def test_encrypt_decrypt_roundtrip(self, encryption):
        plaintext = "sensitive data 123"
        ciphertext = encryption.encrypt(plaintext)
        assert isinstance(ciphertext, bytes)
        assert ciphertext != plaintext.encode()
        assert encryption.decrypt(ciphertext) == plaintext

    def test_decrypt_memoryview(self, encryption):
        """BinaryField returns memoryview — decrypt must handle it."""
        plaintext = "test memoryview"
        ciphertext = encryption.encrypt(plaintext)
        mv = memoryview(ciphertext)
        assert encryption.decrypt(mv) == plaintext

    def test_different_encryptions_differ(self, encryption):
        ct1 = encryption.encrypt("same text")
        ct2 = encryption.encrypt("same text")
        # Fernet includes a timestamp, so two encryptions of same text differ
        assert ct1 != ct2

    def test_unicode_roundtrip(self, encryption):
        text = "مرحبا بالعالم"
        assert encryption.decrypt(encryption.encrypt(text)) == text

    def test_empty_string(self, encryption):
        assert encryption.decrypt(encryption.encrypt("")) == ""


class TestEncryptionKeyMissing:
    def test_raises_without_key(self):
        with override_settings(ENCRYPTION_KEY=""):
            with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
                FieldEncryption()


class TestGetEncryption:
    def test_returns_instance(self):
        import apps.responses.services.encryption as mod
        mod._encryption = None
        with override_settings(ENCRYPTION_KEY=TEST_KEY):
            enc = get_encryption()
            assert isinstance(enc, FieldEncryption)
        mod._encryption = None

    def test_singleton_returns_same_instance(self):
        import apps.responses.services.encryption as mod
        mod._encryption = None
        with override_settings(ENCRYPTION_KEY=TEST_KEY):
            enc1 = get_encryption()
            enc2 = get_encryption()
            assert enc1 is enc2
        mod._encryption = None
