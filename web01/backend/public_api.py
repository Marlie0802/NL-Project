from fastapi import APIRouter
from sqlalchemy import func, select

from database import SessionLocal
from models import (
    ChallengeResult,
    GameSession,
    User,
)


router = APIRouter(
    prefix="/public",
    tags=["public"],
)


# =========================================================
# Publiek scoreboard
#
# Regels:
#
# - Alleen actieve teamaccounts worden getoond.
# - Alleen pakketsessies tellen mee.
# - Losse challenges zijn oefening/test.
# - Van ieder team telt de beste pakketsessie.
# - Bij gelijke score telt het aantal voltooide
#   challenges als tweede sortering.
# =========================================================

@router.get("/scoreboard")
def public_scoreboard():

    db = SessionLocal()

    try:
        teams = db.scalars(
            select(User)
            .where(
                User.role == "team",
                User.active.is_(True)
            )
            .order_by(
                User.display_name.asc()
            )
        ).all()

        scoreboard = []

        for team in teams:

            sessions = db.scalars(
                select(GameSession)
                .where(
                    GameSession.user_id
                    == team.id,
                    GameSession.mode
                    == "package"
                )
                .order_by(
                    GameSession.started_at.asc()
                )
            ).all()

            best_score = 0
            best_completed = 0
            best_total = 10

            for game_session in sessions:

                score = db.scalar(
                    select(
                        func.coalesce(
                            func.sum(
                                ChallengeResult.points
                            ),
                            0
                        )
                    )
                    .where(
                        ChallengeResult.session_id
                        == game_session.id,
                        ChallengeResult.completed.is_(
                            True
                        )
                    )
                )

                completed = db.scalar(
                    select(
                        func.count(
                            ChallengeResult.id
                        )
                    )
                    .where(
                        ChallengeResult.session_id
                        == game_session.id,
                        ChallengeResult.completed.is_(
                            True
                        )
                    )
                )

                score = int(
                    score or 0
                )

                completed = int(
                    completed or 0
                )

                if (
                    score > best_score
                    or (
                        score == best_score
                        and completed
                        > best_completed
                    )
                ):
                    best_score = score
                    best_completed = completed
                    best_total = (
                        game_session.total_challenges
                    )

            scoreboard.append({
                "team": team.display_name,
                "completed": best_completed,
                "total": best_total,
                "score": best_score,
            })

        scoreboard.sort(
            key=lambda row: (
                -row["score"],
                -row["completed"],
                row["team"].lower()
            )
        )

        for position, row in enumerate(
            scoreboard,
            start=1
        ):
            row["position"] = position

        return {
            "scoreboard": scoreboard
        }

    finally:
        db.close()
