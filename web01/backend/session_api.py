from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from pydantic import BaseModel, Field
from sqlalchemy import select

from database import SessionLocal
from models import (
    GameSession,
    SessionMessage,
)
from session_service import (
    build_session_status,
    get_active_session,
    get_session_for_team,
    request_hint,
    submit_answer,
)
from team_api import require_team


router = APIRouter(
    prefix="/session",
    tags=["session"],
)


# =========================================================
# Request-modellen
# =========================================================

class AnswerRequest(BaseModel):
    answer: str = Field(
        min_length=1,
        max_length=500
    )


# =========================================================
# Huidige actieve sessie
# =========================================================

@router.get("/active")
def active_session(
    team=Depends(require_team)
):
    db = SessionLocal()

    try:
        game_session = get_active_session(
            db,
            team["id"]
        )

        if not game_session:
            return {
                "active": False
            }

        status = build_session_status(
            db,
            game_session
        )

        return {
            "active": True,
            **status
        }

    finally:
        db.close()


# =========================================================
# Sessie-status
# =========================================================

@router.get("/{session_id}")
def session_status(
    session_id: str,
    team=Depends(require_team)
):
    db = SessionLocal()

    try:
        game_session = get_session_for_team(
            db,
            session_id,
            team["id"]
        )

        return build_session_status(
            db,
            game_session
        )

    finally:
        db.close()


# =========================================================
# Ingebouwde hint aanvragen
#
# Deze hint kost punten volgens scoring.py.
# =========================================================

@router.post("/{session_id}/hint")
def get_hint(
    session_id: str,
    team=Depends(require_team)
):
    db = SessionLocal()

    try:
        game_session = get_session_for_team(
            db,
            session_id,
            team["id"]
        )

        return request_hint(
            db,
            game_session=game_session
        )

    finally:
        db.close()


# =========================================================
# Antwoord insturen
# =========================================================

@router.post("/{session_id}/answer")
def answer(
    session_id: str,
    data: AnswerRequest,
    team=Depends(require_team)
):
    db = SessionLocal()

    try:
        game_session = get_session_for_team(
            db,
            session_id,
            team["id"]
        )

        return submit_answer(
            db,
            game_session=game_session,
            submitted_answer=data.answer
        )

    finally:
        db.close()


# =========================================================
# Nieuwe berichten van spelleider ophalen
#
# after_id:
# frontend onthoudt het ID van het laatste getoonde
# bericht en vraagt alleen nieuwere berichten op.
#
# Opgehaalde berichten worden tevens als gelezen gemarkeerd.
# =========================================================

@router.get("/{session_id}/messages")
def session_messages(
    session_id: str,
    after_id: int = Query(
        default=0,
        ge=0
    ),
    team=Depends(require_team)
):
    db = SessionLocal()

    try:
        game_session = get_session_for_team(
            db,
            session_id,
            team["id"]
        )

        messages = db.scalars(
            select(SessionMessage)
            .where(
                SessionMessage.session_id
                == game_session.id,
                SessionMessage.id > after_id
            )
            .order_by(
                SessionMessage.id.asc()
            )
        ).all()

        now = datetime.now(
            timezone.utc
        )

        response_messages = []

        for message in messages:

            response_messages.append({
                "id": message.id,
                "type": (
                    message.message_type
                ),
                "text": (
                    message.message
                ),
                "challenge_id": (
                    message.challenge_id
                ),
                "penalty_points": (
                    message.penalty_points
                ),
                "created_at": (
                    message.created_at
                )
            })

            if message.read_at is None:
                message.read_at = now

        if messages:
            db.commit()

        return {
            "messages": response_messages,
            "last_id": (
                messages[-1].id
                if messages
                else after_id
            )
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


# =========================================================
# Belangrijk:
#
# Er bestaan hier bewust GEEN endpoints voor:
#
# POST   /session/start
# DELETE /session/{id}
#
# Teams mogen BreachOut-sessies niet zelf starten
# of stoppen. Dat gebeurt via admin/gameleader.
# =========================================================
