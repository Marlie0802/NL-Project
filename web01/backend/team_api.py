from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel
from sqlalchemy import select

from database import SessionLocal
from models import User
from auth import (
    verify_password,
    create_login_token,
    read_login_token
)


router = APIRouter(prefix="/team", tags=["team"])

COOKIE_NAME = "challengelab_team_auth"


class LoginRequest(BaseModel):
    username: str
    password: str


def require_team(request: Request):

    token = request.cookies.get(COOKIE_NAME)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Niet ingelogd"
        )

    token_data = read_login_token(token)

    if not token_data:
        raise HTTPException(
            status_code=401,
            detail="Sessie verlopen"
        )

    db = SessionLocal()

    try:
        user = db.get(
            User,
            token_data.get("user_id")
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
            "display_name": user.display_name
        }

    finally:
        db.close()


@router.post("/login")
def login(
    data: LoginRequest,
    response: Response
):

    db = SessionLocal()

    try:

        user = db.scalar(
            select(User).where(
                User.username ==
                data.username.strip().lower()
            )
        )

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Onjuiste gebruikersnaam of wachtwoord"
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
                detail="Onjuiste gebruikersnaam of wachtwoord"
            )

        token = create_login_token(
            user.id,
            user.role
        )

        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            secure=True,
            max_age=28800,
            path="/"
        )

        return {
            "status": "ok",
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name
            }
        }

    finally:
        db.close()


@router.post("/logout")
def logout(response: Response):

    response.delete_cookie(
        COOKIE_NAME,
        path="/"
    )

    return {
        "status": "logged_out"
    }


@router.get("/me")
def me(
    team=Depends(require_team)
):
    return team
