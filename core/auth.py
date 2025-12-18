import os
from jose import jwt
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
import os

# Configuración de Hashing
# Fallback to pbkdf2_sha256 due to bcrypt/passlib compatibility issues
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

SECRET_KEY = os.getenv('SECRET_KEY')
ENV_TYPE = os.getenv('ENV_TYPE', 'prod')

# Auto-loading .env is handled by entry points (http_fastapi.py, scripts)
# or via python-dotenv if strictly needed here.
from dotenv import load_dotenv
load_dotenv()

# Reload vars after dotenv (in case they were None before)
if not SECRET_KEY: SECRET_KEY = os.getenv('SECRET_KEY')
if not os.getenv('ENV_TYPE'): ENV_TYPE = os.getenv('ENV_TYPE', 'prod')

# 1. Manual Parsing Logic REMOVED (Duplicate)
pass

if not SECRET_KEY:
    # STRICT MODE: No defaults. App must crash if no secret.
    # Security First. Use .env to set SECRET_KEY even for Dev.
    msg = (
        "CRITICAL SECURITY ERROR: 'SECRET_KEY' is not set.\n"
        "1. Check your .env file.\n"
        "2. Check Environment Variables.\n"
        "Application cannot start without a secure secret."
    )
    raise ValueError(msg)

if SECRET_KEY == "SECRET_CHANGE_ME" and ENV_TYPE != 'dev':
     raise ValueError("CRITICAL: You are using the default insecure SECRET_KEY in Production!")

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
