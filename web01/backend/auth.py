import os

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pwdlib import PasswordHash


password_hash = PasswordHash.recommended()

serializer = URLSafeTimedSerializer(
    os.environ["SESSION_SECRET"]
)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    password: str,
    hashed_password: str
) -> bool:
    return password_hash.verify(
        password,
        hashed_password
    )


def create_login_token(
    user_id: int,
    role: str
) -> str:

    return serializer.dumps({
        "user_id": user_id,
        "role": role
    })


def read_login_token(
    token: str,
    max_age: int = 28800
):

    try:
        return serializer.loads(
            token,
            max_age=max_age
        )

    except SignatureExpired:
        return None

    except BadSignature:
        return None
