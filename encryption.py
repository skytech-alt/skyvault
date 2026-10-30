"""
Модуль шифрования SkyVault.
PBKDF2-HMAC-SHA256 для получения ключа из мастер-пароля + Fernet.
"""
import base64
import hashlib
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SALT_LENGTH = 16
KDF_ITERATIONS = 480_000

def generate_salt() -> bytes:
    return os.urandom(SALT_LENGTH)

def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    key = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(key)

def hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, KDF_ITERATIONS)
    return dk.hex()

def verify_password(password: str, salt: bytes, expected_hash: str) -> bool:
    return hash_password(password, salt) == expected_hash

def encrypt_text(fernet: Fernet, plaintext: str) -> str:
    if plaintext is None:
        plaintext = ""
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

def decrypt_text(fernet: Fernet, token: str) -> str:
    if not token:
        return ""
    return fernet.decrypt(token.encode("utf-8")).decode("utf-8")

def encrypt_file(fernet: Fernet, source_path: str, dest_path: str) -> None:
    with open(source_path, "rb") as f:
        data = f.read()
    with open(dest_path, "wb") as f:
        f.write(fernet.encrypt(data))

def decrypt_file(fernet: Fernet, source_path: str, dest_path: str) -> None:
    with open(source_path, "rb") as f:
        data = f.read()
    with open(dest_path, "wb") as f:
        f.write(fernet.decrypt(data))
