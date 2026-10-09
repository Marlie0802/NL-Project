import subprocess
import shlex

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Response,
    Depends
)

from pydantic import BaseModel

from sqlalchemy import (
    select,
    func,
    delete
)

from database import SessionLocal

from models import (
    User,
    GameSession,
    ChallengeResult
)

from auth import (
    verify_password,
    hash_password,
    create_login_token,
    read_login_token
)


router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)


COOKIE_NAME = "challengelab_admin_auth"
DOCKER_HOST = "team@192.168.10.23"
SSH_KEY = "/home/team/.ssh/challengelab_docker"

# =========================================================
# Pydantic modellen
# =========================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class TeamCreateRequest(BaseModel):
    username: str
    display_name: str
    password: str


class TeamActiveRequest(BaseModel):
    active: bool


class TeamPasswordRequest(BaseModel):
    password: str


# =========================================================
# Authenticatie
# =========================================================

def require_admin(request: Request):

    token = request.cookies.get(
        COOKIE_NAME
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
            detail="Sessie verlopen of ongeldig"
        )

    user_id = token_data.get(
        "user_id"
    )

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Ongeldige sessie"
        )

    db = SessionLocal()

    try:

        user = db.get(
            User,
            user_id
        )

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Gebruiker bestaat niet"
            )

        if not user.active:
            raise HTTPException(
                status_code=403,
                detail="Account is uitgeschakeld"
            )

        if user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Geen beheerdersrechten"
            )

        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role
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

        if user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Geen beheerdersaccount"
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
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",

            # Later op True zetten
            # zodra HTTPS actief is.
            secure=True,

            max_age=28800,
            path="/"
        )

        return {
            "status": "ok",
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role
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
        key=COOKIE_NAME,
        path="/"
    )

    return {
        "status": "logged_out"
    }


# =========================================================
# Huidige beheerder
# =========================================================

@router.get("/me")
def me(
    admin=Depends(require_admin)
):

    return admin


# =========================================================
# Scoreboard
# =========================================================

@router.get("/scoreboard")
def scoreboard(
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:

        # Per team en per challenge pakken we
        # alleen de hoogst behaalde score.
        #
        # Hierdoor kan een team niet meerdere
        # sessies spelen om punten op te stapelen.

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
                ChallengeResult.completed.is_(
                    True
                )
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
                User.username,
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
                best_scores.c.user_id
                == User.id
            )

            .where(
                User.role == "team"
            )

            .group_by(
                User.id,
                User.username,
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


        scoreboard_data = []


        for position, row in enumerate(
            rows,
            start=1
        ):

            scoreboard_data.append({
                "position": position,
                "id": row.id,
                "username": row.username,
                "display_name": row.display_name,
                "completed": int(
                    row.completed or 0
                ),
                "total": 10,
                "score": int(
                    row.score or 0
                )
            })


        return {
            "scoreboard": scoreboard_data
        }

    finally:
        db.close()


# =========================================================
# Teams ophalen
# =========================================================

@router.get("/teams")
def list_teams(
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:

        teams = db.scalars(
            select(User)
            .where(
                User.role == "team"
            )
            .order_by(
                User.display_name.asc()
            )
        ).all()


        return {
            "teams": [
                {
                    "id": team.id,
                    "username": team.username,
                    "display_name": (
                        team.display_name
                    ),
                    "active": team.active,
                    "created_at": (
                        team.created_at
                    )
                }
                for team in teams
            ]
        }

    finally:
        db.close()


# =========================================================
# Team aanmaken
# =========================================================

@router.post("/teams")
def create_team(
    data: TeamCreateRequest,
    admin=Depends(require_admin)
):

    username = (
        data.username
        .strip()
        .lower()
    )

    display_name = (
        data.display_name
        .strip()
    )


    if len(username) < 3:
        raise HTTPException(
            status_code=400,
            detail=(
                "Gebruikersnaam moet minimaal "
                "3 tekens bevatten"
            )
        )


    if not display_name:
        raise HTTPException(
            status_code=400,
            detail=(
                "Weergavenaam mag niet leeg zijn"
            )
        )


    if len(data.password) < 8:
        raise HTTPException(
            status_code=400,
            detail=(
                "Wachtwoord moet minimaal "
                "8 tekens bevatten"
            )
        )


    db = SessionLocal()

    try:

        existing = db.scalar(
            select(User).where(
                User.username == username
            )
        )


        if existing:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Deze gebruikersnaam "
                    "bestaat al"
                )
            )


        team = User(
            username=username,
            display_name=display_name,

            password_hash=hash_password(
                data.password
            ),

            role="team",
            active=True
        )


        db.add(team)

        db.commit()

        db.refresh(team)


        return {
            "status": "created",
            "team": {
                "id": team.id,
                "username": team.username,
                "display_name": (
                    team.display_name
                ),
                "active": team.active
            }
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


# =========================================================
# Team in- of uitschakelen
# =========================================================

@router.patch(
    "/teams/{team_id}/active"
)
def set_team_active(
    team_id: int,
    data: TeamActiveRequest,
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:

        team = db.get(
            User,
            team_id
        )


        if not team:
            raise HTTPException(
                status_code=404,
                detail="Team niet gevonden"
            )


        if team.role != "team":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Deze gebruiker is "
                    "geen teamaccount"
                )
            )


        team.active = data.active


        db.commit()


        return {
            "status": "updated",
            "team": {
                "id": team.id,
                "username": team.username,
                "active": team.active
            }
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


# =========================================================
# Teamwachtwoord opnieuw instellen
# =========================================================

@router.post(
    "/teams/{team_id}/password"
)
def reset_team_password(
    team_id: int,
    data: TeamPasswordRequest,
    admin=Depends(require_admin)
):

    if len(data.password) < 8:
        raise HTTPException(
            status_code=400,
            detail=(
                "Wachtwoord moet minimaal "
                "8 tekens bevatten"
            )
        )


    db = SessionLocal()

    try:

        team = db.get(
            User,
            team_id
        )


        if not team:
            raise HTTPException(
                status_code=404,
                detail="Team niet gevonden"
            )


        if team.role != "team":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Deze gebruiker is "
                    "geen teamaccount"
                )
            )


        team.password_hash = hash_password(
            data.password
        )


        db.commit()


        return {
            "status": "updated"
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()

# =========================================================
# Team verwijderen
# =========================================================

@router.delete("/teams/{team_id}")
def delete_team(
    team_id: int,
    admin=Depends(require_admin)
):
    db = SessionLocal()

    try:
        team = db.get(
            User,
            team_id
        )

        if not team:
            raise HTTPException(
                status_code=404,
                detail="Team niet gevonden"
            )

        if team.role != "team":
            raise HTTPException(
                status_code=400,
                detail="Deze gebruiker is geen teamaccount"
            )

        active_session = db.scalar(
            select(GameSession).where(
                GameSession.user_id == team_id,
                GameSession.status == "active"
            )
        )

        if active_session:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Dit team heeft nog een actieve sessie. "
                    "Stop die sessie eerst."
                )
            )

        # Eerst resultaten verwijderen vanwege foreign keys
        db.execute(
            delete(ChallengeResult).where(
                ChallengeResult.user_id == team_id
            )
        )

        # Daarna oude sessies
        db.execute(
            delete(GameSession).where(
                GameSession.user_id == team_id
            )
        )

        # Als laatste het teamaccount
        db.delete(team)

        db.commit()

        return {
            "status": "deleted"
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()

# =========================================================
# Sessies bekijken
# =========================================================

@router.get("/sessions")
def list_sessions(
    admin=Depends(require_admin)
):
    db = SessionLocal()

    try:
        sessions = db.execute(
            select(
                GameSession,
                User
            )
            .join(
                User,
                User.id == GameSession.user_id
            )
            .order_by(
                GameSession.started_at.desc()
            )
        ).all()

        result = []

        for game_session, user in sessions:

            current_challenge = db.scalar(
                select(
                    ChallengeResult.challenge_id
                )
                .where(
                    ChallengeResult.session_id == game_session.id,
                    ChallengeResult.completed.is_(False)
                )
                .order_by(
                    ChallengeResult.id.desc()
                )
                .limit(1)
            )

            points = db.scalar(
                select(
                    func.coalesce(
                        func.sum(
                            ChallengeResult.points
                        ),
                        0
                    )
                )
                .where(
                    ChallengeResult.session_id == game_session.id
                )
            )

            wrong_attempts = db.scalar(
                select(
                    func.coalesce(
                        func.sum(
                            ChallengeResult.wrong_attempts
                        ),
                        0
                    )
                )
                .where(
                    ChallengeResult.session_id == game_session.id
                )
            )

            completed = db.scalar(
                select(
                    func.count(
                        ChallengeResult.id
                    )
                )
                .where(
                    ChallengeResult.session_id == game_session.id,
                    ChallengeResult.completed.is_(True)
                )
            )

            result.append({
                "id": game_session.id,
                "team_id": user.id,
                "team": user.display_name,
                "username": user.username,
                "status": game_session.status,
                "current_challenge": current_challenge,
                "completed": completed or 0,
                "total": 10,
                "score": int(points or 0),
                "wrong_attempts": int(wrong_attempts or 0),
                "started_at": game_session.started_at,
                "completed_at": game_session.completed_at
            })

        return {
            "sessions": result
        }

    finally:
        db.close()

# =========================================================
# Sessie geforceerd stoppen
# =========================================================

def remove_challenge_container(instance_id: str | None):

    if not instance_id:
        return

    container_name = f"challenge-{instance_id}"

    subprocess.run(
        [
            "/usr/bin/ssh",
            "-i", SSH_KEY,
            "-o", "StrictHostKeyChecking=no",
            DOCKER_HOST,
            (
                f"docker rm -f "
                f"{shlex.quote(container_name)} "
                f">/dev/null 2>&1 || true"
            )
        ],
        capture_output=True,
        text=True
    )


@router.post("/sessions/{session_id}/stop")
def admin_stop_session(
    session_id: str,
    admin=Depends(require_admin)
):
    db = SessionLocal()

    try:
        game_session = db.get(
            GameSession,
            session_id
        )

        if not game_session:
            raise HTTPException(
                status_code=404,
                detail="Sessie niet gevonden"
            )

        if game_session.status != "active":
            raise HTTPException(
                status_code=400,
                detail="Deze sessie is niet actief"
            )

        remove_challenge_container(
            game_session.current_instance
        )

        game_session.status = "cancelled"
        game_session.current_instance = None

        db.commit()

        return {
            "status": "cancelled",
            "session_id": session_id
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()

# =========================================================
# Sessie resetten
# =========================================================

@router.delete("/sessions/{session_id}/reset")
def reset_session(
    session_id: str,
    admin=Depends(require_admin)
):
    db = SessionLocal()

    try:
        game_session = db.get(
            GameSession,
            session_id
        )

        if not game_session:
            raise HTTPException(
                status_code=404,
                detail="Sessie niet gevonden"
            )

        if game_session.status == "active":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Een actieve sessie kan niet worden gereset. "
                    "Stop de sessie eerst."
                )
            )

        db.execute(
            delete(ChallengeResult).where(
                ChallengeResult.session_id == session_id
            )
        )

        db.delete(game_session)

        db.commit()

        return {
            "status": "reset",
            "session_id": session_id
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()
