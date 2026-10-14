from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel
from sqlalchemy import select

from auth import (
    create_login_token,
    read_login_token,
    verify_password,
)
from config import (
    LOGIN_MAX_AGE_SECONDS,
    TEAM_COOKIE_NAME,
)
from database import SessionLocal
from models import User


router = APIRouter(
    prefix="/team",
    tags=["team"],
)


# =========================================================
# Request-modellen
# =========================================================

class LoginRequest(BaseModel):
    username: str
    password: str


# =========================================================
# Team-authenticatie
# =========================================================

def require_team(
    request: Request
) -> dict:
    """
    Vereist een geldig ingelogd teamaccount.

    organization_id mag tijdens de overgang nog None zijn.
    Nieuwe teams worden later via het beheerpanel altijd
    aan een organisatie gekoppeld.
    """

    token = request.cookies.get(
        TEAM_COOKIE_NAME
    )

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Niet ingelogd"
        )

    token_data = read_login_token(
        token
    )

    if not token_data:
        raise HTTPException(
            status_code=401,
            detail="Sessie verlopen"
        )

    if token_data.get("role") != "team":
        raise HTTPException(
            status_code=403,
            detail="Geen teamaccount"
        )

    db = SessionLocal()

    try:
        user = db.get(
            User,
            token_data["user_id"]
        )

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Gebruiker niet gevonden"
            )

        if not user.active:
            raise HTTPException(
                status_code=403,
                detail="Account is uitgeschakeld"
            )

        if user.role != "team":
            raise HTTPException(
                status_code=403,
                detail="Geen teamaccount"
            )

        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "organization_id": (
                user.organization_id
            ),
        }

    finally:
        db.close()


# =========================================================
# Login
# =========================================================

@router.post("/login")
def login(
    data: LoginRequest,
    response: Response
):
    username = (
        data.username
        .strip()
        .lower()
    )

    db = SessionLocal()

    try:
        user = db.scalar(
            select(User).where(
                User.username == username
            )
        )

        # Zelfde foutmelding voor onbekende user
        # en verkeerd wachtwoord.
        if not user:
            raise HTTPException(
                status_code=401,
                detail=(
                    "Onjuiste gebruikersnaam "
                    "of wachtwoord"
                )
            )

        if not user.active:
            raise HTTPException(
                status_code=403,
                detail="Account is uitgeschakeld"
            )

        if user.role != "team":
            raise HTTPException(
                status_code=403,
                detail="Geen teamaccount"
            )

        if not verify_password(
            data.password,
            user.password_hash
        ):
            raise HTTPException(
                status_code=401,
                detail=(
                    "Onjuiste gebruikersnaam "
                    "of wachtwoord"
                )
            )

        token = create_login_token(
            user.id,
            user.role
        )

        response.set_cookie(
            key=TEAM_COOKIE_NAME,
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=LOGIN_MAX_AGE_SECONDS,
            path="/"
        )

        return {
            "status": "ok",
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": (
                    user.display_name
                ),
                "role": user.role,
                "organization_id": (
                    user.organization_id
                ),
            }
        }

    finally:
        db.close()


# =========================================================
# Logout
# =========================================================

@router.post("/logout")
def logout(
    response: Response
):
    response.delete_cookie(
        TEAM_COOKIE_NAME,
        path="/"
    )

    return {
        "status": "logged_out"
    }


# =========================================================
# Huidig team
# =========================================================

@router.get("/me")
def me(
    team=Depends(require_team)
):
    return team
