import os
from jose import jwt
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
import os

# Configuración de Hashing
# Fallback to pbkdf2_sha256 due to bcrypt/passlib compatibility issues
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# SECURITY: Externalize Keys
# Warning: Default key is for dev only.
SECRET_KEY = os.getenv('SECRET_KEY', "SECRET_CHANGE_ME")
if SECRET_KEY == "SECRET_CHANGE_ME":
    print("WARNING: Using insecure default SECRET_KEY. Set 'SECRET_KEY' in environment.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_password, hashed_password):
    """Verifica si la contraseña coincide con el hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Genera un hash seguro para la contraseña."""
    return pwd_context.hash(password)

def needs_update(hashed_password):
    """Verifica si el hash usa un algoritmo obsoleto (opcional pero recomendado)."""
    return pwd_context.needs_update(hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None
