from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Mock users — in a real system this would be a database
FAKE_USERS = {
    "bob": {
        "username": "bob",
        "hashed_password": pwd_context.hash("password123"),
        "role": "employee",
    },
    "carol": {
        "username": "carol",
        "hashed_password": pwd_context.hash("password123"),
        "role": "intern",
    },
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("password123"),
        "role": "admin",
    },
}

# Which roles can see which classification levels
ROLE_CLEARANCE = {
    "intern": ["Public", "Internal"],
    "employee": ["Public", "Internal"],
    "admin": ["Public", "Internal", "Confidential", "Restricted"],
}


def verify_user(username: str, password: str):
    user = FAKE_USERS.get(username)
    if not user:
        return None
    if not pwd_context.verify(password, user["hashed_password"]):
        return None
    return user