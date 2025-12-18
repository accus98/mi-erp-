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

# Smart Dev Detection
# Smart Dev Detection & .env Loader
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
git_dir = os.path.join(root_dir, '.git')
env_file = os.path.join(root_dir, '.env')

# 1. Try Git Detection REMOVED for Security
# We rely ONLY on explicit .env file or Environment Variables.
# if not os.getenv('ENV_TYPE') and os.path.exists(git_dir):
#     ENV_TYPE = 'dev'

# 2. Try .env File (Manual Load)
if os.path.exists(env_file):
    try:
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    if k == 'ENV_TYPE' and not os.getenv('ENV_TYPE'):
                        ENV_TYPE = v
                    if k == 'SECRET_KEY' and not SECRET_KEY:
                        SECRET_KEY = v
    except Exception:
        pass

if not SECRET_KEY:
    if ENV_TYPE == 'dev':
        SECRET_KEY = "SECRET_CHANGE_ME"
        print("WARNING: Using insecure default SECRET_KEY (Dev Mode).")
    else:
        raise ValueError("CRITICAL: SECRET_KEY environment variable is not set!")
elif SECRET_KEY == "SECRET_CHANGE_ME" and ENV_TYPE != 'dev':
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
