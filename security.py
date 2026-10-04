from datetime import datetime, timedelta
from jose import jwt, JWTError

SECRET_KEY = "solo-dev-secret-change-this-later"
ALGORITHM = "HS256"
EXPIRE_MINUTES = 60


def create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None