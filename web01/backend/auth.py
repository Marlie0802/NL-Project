import os

from itsdangerous import (
    BadSignature,
    SignatureExpired,
    URLSafeTimedSerializer,
)
from pwdlib import PasswordHash

from config import LOGIN_MAX_AGE_SECONDS


# =========================================================
# Authenticatie-instellingen
# =========================================================

SESSION_SECRET = os.environ["SESSION_SECRET"]

ALLOWED_ROLES = {
    "admin",
    "gameleader",
    "team",
}


# =========================================================
# Password hashing
# =========================================================

password_hasher = PasswordHash.recommended()


def hash_password(
    password: str
) -> str:
    """
    Hash een wachtwoord met de aanbevolen pwdlib-configuratie.
    """

    if not password:
        raise ValueError(
            "Wachtwoord mag niet leeg zijn."
        )

    return password_hasher.hash(
        password
    )


def verify_password(
    password: str,
    hashed_password: str
) -> bool:
    """
    Controleer een wachtwoord tegen een opgeslagen hash.

    Bij een ongeldige/beschadigde hash wordt False
    teruggegeven in plaats van een applicatiefout.
    """

    if (
        not password
        or
        not hashed_password
    ):
        return False

    try:
        return password_hasher.verify(
            password,
            hashed_password
        )

    except Exception:
        return False


# =========================================================
# Login tokens
# =========================================================

serializer = URLSafeTimedSerializer(
    SESSION_SECRET
)


def create_login_token(
    user_id: int,
    role: str
) -> str:
    """
    Maak een ondertekend login-token.

    Het token bevat alleen:
    - user_id
    - role

    Gebruikersgegevens zelf worden altijd opnieuw
    uit PostgreSQL gelezen.
    """

    if role not in ALLOWED_ROLES:
        raise ValueError(
            f"Ongeldige gebruikersrol: {role}"
        )

    return serializer.dumps({
        "user_id": int(user_id),
        "role": role,
    })


def read_login_token(
    token: str,
    max_age: int = LOGIN_MAX_AGE_SECONDS
) -> dict | None:
    """
    Lees en valideer een login-token.

    Geeft None terug bij:
    - verlopen token
    - ongeldige handtekening
    - verkeerd tokenformaat
    - onbekende rol
    """

    if not token:
        return None

    try:
        data = serializer.loads(
            token,
            max_age=max_age
        )

    except (
        SignatureExpired,
        BadSignature,
    ):
        return None

    except Exception:
        return None

    if not isinstance(
        data,
        dict
    ):
        return None

    user_id = data.get(
        "user_id"
    )

    role = data.get(
        "role"
    )

    if not isinstance(
        user_id,
        int
    ):
        return None

    if role not in ALLOWED_ROLES:
        return None

    return {
        "user_id": user_id,
        "role": role,
    }
