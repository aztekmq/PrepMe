from cryptography.fernet import Fernet

fernet = None  # Global reference

def init_fernet(key: bytes):
    global fernet
    fernet = Fernet(key)

def encrypt_password(password: str) -> str:
    return fernet.encrypt(password.encode()).decode()

def verify_password(stored_password: str, provided_password: str) -> bool:
    try:
        return fernet.decrypt(stored_password.encode()).decode() == provided_password
    except Exception:
        return False