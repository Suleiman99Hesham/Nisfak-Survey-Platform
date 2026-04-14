from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings


class FieldEncryption:
    """
    Fernet symmetric encryption for sensitive survey field answers.
    Supports key rotation via MultiFernet.
    """

    def __init__(self):
        key = settings.ENCRYPTION_KEY
        if not key:
            raise ValueError("ENCRYPTION_KEY is not set in settings.")
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        if isinstance(ciphertext, memoryview):
            ciphertext = bytes(ciphertext)
        return self._fernet.decrypt(ciphertext).decode("utf-8")


# Module-level singleton for convenience
_encryption = None


def get_encryption() -> FieldEncryption:
    global _encryption
    if _encryption is None:
        _encryption = FieldEncryption()
    return _encryption
