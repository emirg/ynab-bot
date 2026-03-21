from typing import Optional

from cryptography.fernet import Fernet


class TokenEncryptor:
    """Encrypts and decrypts OAuth tokens using Fernet symmetric encryption."""

    def __init__(self, key: str):
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        if plaintext is None:
            return None
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        if ciphertext is None:
            return None
        return self._fernet.decrypt(ciphertext.encode()).decode()
