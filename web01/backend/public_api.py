from fastapi import APIRouter

from sqlalchemy import (
    select,
    func
)

from database import SessionLocal

from models import (
    User,
    ChallengeResult
)


router = APIRouter(
    prefix="/public",
    tags=["public"]
)


@router.get("/scoreboard")
def public_scoreboard():

    db = SessionLocal()

    try:

        # Pak per team per challenge alleen
        # de beste behaalde score.
        best_scores = (
            select(
                ChallengeResult.user_id.label(
                    "user_id"
                ),

                ChallengeResult.challenge_id.label(
                    "challenge_id"
                ),

                func.max(
                    ChallengeResult.points
                ).label(
                    "points"
                )
            )
            .where(
                ChallengeResult.completed.is_(True)
            )
            .group_by(
                ChallengeResult.user_id,
                ChallengeResult.challenge_id
            )
            .subquery()
        )


        completed_expression = func.count(
            best_scores.c.challenge_id
        )


        score_expression = func.coalesce(
            func.sum(
                best_scores.c.points
            ),
            0
        )


        statement = (
            select(
                User.id,
                User.display_name,

                completed_expression.label(
                    "completed"
                ),

                score_expression.label(
                    "score"
                )
            )

            .outerjoin(
                best_scores,
                best_scores.c.user_id == User.id
            )

            .where(
                User.role == "team",
                User.active.is_(True)
            )

            .group_by(
                User.id,
                User.display_name
            )

            .order_by(
                score_expression.desc(),
                completed_expression.desc(),
                User.display_name.asc()
            )
        )


        rows = db.execute(
            statement
        ).all()


        result = []


        for position, row in enumerate(
            rows,
            start=1
        ):

            result.append({
                "position": position,
                "team": row.display_name,
                "completed": int(
                    row.completed or 0
                ),
                "total": 10,
                "score": int(
                    row.score or 0
                )
            })


        return {
            "scoreboard": result
        }

    finally:
        db.close()
