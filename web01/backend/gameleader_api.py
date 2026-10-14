from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from auth import (
    create_login_token,
    hash_password,
    read_login_token,
    verify_password,
)
from challenges import get_catalog
from config import (
    GAMELEADER_COOKIE_NAME,
    LOGIN_MAX_AGE_SECONDS,
    SESSION_MESSAGE_MAX_LENGTH,
)
from database import SessionLocal
from models import (
    ChallengeResult,
    GameSession,
    SessionMessage,
    User,
)
from session_service import (
    get_session_challenges,
    start_session,
    stop_session,
)
from report_service import build_session_report


router = APIRouter(
    prefix="/gameleader",
    tags=["gameleader"],
)


# =========================================================
# Request-modellen
# =========================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class TeamCreateRequest(BaseModel):
    username: str
    display_name: str
    password: str


class SingleSessionRequest(BaseModel):
    challenge_id: str


class PackageSessionRequest(BaseModel):
    challenge_ids: list[str] | None = None

    use_saved_assignments: bool = True


class SessionMessageRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=SESSION_MESSAGE_MAX_LENGTH
    )

    message_type: str = "message"


# =========================================================
# Authenticatie
# =========================================================

def require_gameleader(
    request: Request
) -> dict:

    token = request.cookies.get(
        GAMELEADER_COOKIE_NAME
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

    if token_data.get("role") != "gameleader":
        raise HTTPException(
            status_code=403,
            detail="Geen spelleideraccount"
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

        if user.role != "gameleader":
            raise HTTPException(
                status_code=403,
                detail="Geen spelleideraccount"
            )

        if user.organization_id is None:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Spelleider is niet aan een "
                    "bedrijf gekoppeld"
                )
            )

        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "organization_id": user.organization_id,
        }

    finally:
        db.close()


# =========================================================
# Hulpfuncties
# =========================================================

def get_team_in_organization(
    db,
    *,
    team_id: int,
    organization_id: int
) -> User:

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
            detail="Gebruiker is geen team"
        )

    if team.organization_id != organization_id:
        raise HTTPException(
            status_code=403,
            detail=(
                "Dit team hoort niet bij jouw bedrijf"
            )
        )

    if not team.active:
        raise HTTPException(
            status_code=403,
            detail="Teamaccount is uitgeschakeld"
        )

    return team


def get_session_in_organization(
    db,
    *,
    session_id: str,
    organization_id: int
) -> GameSession:

    game_session = db.scalar(
        select(GameSession).where(
            GameSession.id == session_id,
            GameSession.organization_id
            == organization_id
        )
    )

    if not game_session:
        raise HTTPException(
            status_code=404,
            detail="Sessie niet gevonden"
        )

    return game_session


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

        if user.role != "gameleader":
            raise HTTPException(
                status_code=403,
                detail="Geen spelleideraccount"
            )

        if user.organization_id is None:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Spelleider is niet aan een "
                    "bedrijf gekoppeld"
                )
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
            key=GAMELEADER_COOKIE_NAME,
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
                "display_name": user.display_name,
                "role": user.role,
                "organization_id": (
                    user.organization_id
                )
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
        GAMELEADER_COOKIE_NAME,
        path="/"
    )

    return {
        "status": "logged_out"
    }


# =========================================================
# Huidige spelleider
# =========================================================

@router.get("/me")
def me(
    gameleader=Depends(
        require_gameleader
    )
):
    return gameleader


# =========================================================
# Teams van eigen bedrijf
# =========================================================

@router.get("/teams")
def list_teams(
    gameleader=Depends(
        require_gameleader
    )
):

    db = SessionLocal()

    try:
        teams = db.scalars(
            select(User)
            .where(
                User.role == "team",
                User.organization_id
                == gameleader["organization_id"]
            )
            .order_by(
                User.display_name.asc()
            )
        ).all()

        result = []

        for team in teams:

            active_session = db.scalar(
                select(GameSession)
                .where(
                    GameSession.user_id == team.id,
                    GameSession.status == "active"
                )
                .order_by(
                    GameSession.started_at.desc()
                )
            )

            result.append({
                "id": team.id,
                "username": team.username,
                "display_name": team.display_name,
                "active": team.active,
                "session": (
                    {
                        "id": active_session.id,
                        "status": (
                            active_session.status
                        ),
                        "mode": (
                            active_session.mode
                        ),
                        "current": (
                            active_session.current_index
                            + 1
                        ),
                        "total": (
                            active_session.total_challenges
                        )
                    }
                    if active_session
                    else None
                )
            })

        return {
            "teams": result
        }

    finally:
        db.close()


# =========================================================
# Team aanmaken binnen eigen bedrijf
# =========================================================

@router.post("/teams")
def create_team(
    data: TeamCreateRequest,
    gameleader=Depends(
        require_gameleader
    )
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

    password = (
        data.password
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
                "Teamnaam mag niet leeg zijn"
            )
        )

    if len(password) < 8:
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
                    "Deze gebruikersnaam bestaat al"
                )
            )

        team = User(
            username=username,
            display_name=display_name,
            password_hash=hash_password(
                password
            ),
            role="team",
            active=True,

            # De Spelleider kan bewust geen ander
            # bedrijf kiezen.
            organization_id=(
                gameleader["organization_id"]
            )
        )

        db.add(
            team
        )

        db.commit()
        db.refresh(
            team
        )

        return {
            "status": "created",

            "team": {
                "id": team.id,
                "username": team.username,
                "display_name": (
                    team.display_name
                ),
                "active": team.active,
                "organization_id": (
                    team.organization_id
                )
            }
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


# =========================================================
# Beschikbare challenges
# =========================================================

@router.get("/challenges")
def list_challenges(
    gameleader=Depends(
        require_gameleader
    )
):

    return {
        "challenges": get_catalog(
            include_disabled=False
        )
    }


# =========================================================
# Losse challenge starten
# =========================================================

@router.post(
    "/teams/{team_id}/sessions/single"
)
def start_single_session(
    team_id: int,
    data: SingleSessionRequest,
    gameleader=Depends(
        require_gameleader
    )
):

    db = SessionLocal()

    try:
        team = get_team_in_organization(
            db,
            team_id=team_id,
            organization_id=(
                gameleader["organization_id"]
            )
        )

        result = start_session(
            db,
            user_id=team.id,
            started_by_user_id=(
                gameleader["id"]
            ),
            organization_id=(
                gameleader["organization_id"]
            ),
            mode="single",
            challenge_id=(
                data.challenge_id
            )
        )

        return result

    finally:
        db.close()


# =========================================================
# Pakket van 10 starten
# =========================================================

@router.post(
    "/teams/{team_id}/sessions/package"
)
def start_package_session(
    team_id: int,
    data: PackageSessionRequest,
    gameleader=Depends(
        require_gameleader
    )
):

    db = SessionLocal()

    try:
        team = get_team_in_organization(
            db,
            team_id=team_id,
            organization_id=(
                gameleader["organization_id"]
            )
        )

        result = start_session(
            db,
            user_id=team.id,
            started_by_user_id=(
                gameleader["id"]
            ),
            organization_id=(
                gameleader["organization_id"]
            ),
            mode="package",
            challenge_ids=(
                data.challenge_ids
            ),
            use_saved_assignments=(
                data.use_saved_assignments
            )
        )

        # =============================================
        # ONE-SHOT PACKAGE ASSIGNMENTS
        #
        # Een opgeslagen handmatige selectie geldt alleen
        # voor de eerstvolgende pakketsessie.
        #
        # start_session() is hierboven succesvol afgerond,
        # dus we kunnen de oude selectie nu veilig wissen.
        # =============================================

        from models import TeamChallengeAssignment

        old_assignments = list(
            db.scalars(
                select(
                    TeamChallengeAssignment
                )
                .where(
                    TeamChallengeAssignment.user_id
                    == team.id
                )
            ).all()
        )

        for assignment in old_assignments:
            db.delete(
                assignment
            )

        db.commit()

        return result

    finally:
        db.close()


# =========================================================
# Scoreboard van eigen bedrijf
#
# Alleen teams uit de organisatie van deze Spelleider.
# Alleen pakketsessies tellen mee.
# Van elk team telt de beste pakketsessie.
# =========================================================

@router.get("/scoreboard")
def scoreboard(
    gameleader=Depends(
        require_gameleader
    )
):

    db = SessionLocal()

    try:
        teams = db.scalars(
            select(User)
            .where(
                User.role == "team",
                User.active.is_(True),
                User.organization_id
                == gameleader["organization_id"]
            )
            .order_by(
                User.display_name.asc()
            )
        ).all()

        rows = []

        for team in teams:

            package_sessions = db.scalars(
                select(GameSession)
                .where(
                    GameSession.user_id
                    == team.id,
                    GameSession.organization_id
                    == gameleader["organization_id"],
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

            for game_session in package_sessions:

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

            rows.append({
                "id": team.id,
                "team": team.display_name,
                "completed": best_completed,
                "total": best_total,
                "score": best_score,
            })

        rows.sort(
            key=lambda row: (
                -row["score"],
                -row["completed"],
                row["team"].lower()
            )
        )

        for position, row in enumerate(
            rows,
            start=1
        ):
            row["position"] = position

        return {
            "scoreboard": rows
        }

    finally:
        db.close()


# =========================================================
# Sessies bekijken
# =========================================================

@router.get("/sessions")
def list_sessions(
    gameleader=Depends(
        require_gameleader
    )
):

    db = SessionLocal()

    try:
        rows = db.execute(
            select(
                GameSession,
                User
            )
            .join(
                User,
                User.id == GameSession.user_id
            )
            .where(
                GameSession.organization_id
                == gameleader["organization_id"]
            )
            .order_by(
                GameSession.started_at.desc()
            )
        ).all()

        sessions = []

        for game_session, team in rows:

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
                    == game_session.id
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
                    ChallengeResult.session_id
                    == game_session.id
                )
            )

            hints_used = db.scalar(
                select(
                    func.coalesce(
                        func.sum(
                            ChallengeResult.hints_used
                        ),
                        0
                    )
                )
                .where(
                    ChallengeResult.session_id
                    == game_session.id
                )
            )

            sessions.append({
                "id": game_session.id,

                "team": {
                    "id": team.id,
                    "username": team.username,
                    "display_name": (
                        team.display_name
                    )
                },

                "status": (
                    game_session.status
                ),

                "mode": (
                    game_session.mode
                ),

                "current": (
                    game_session.current_index
                    + 1
                    if (
                        game_session.status
                        == "active"
                    )
                    else min(
                        game_session.current_index,
                        game_session.total_challenges
                    )
                ),

                "total": (
                    game_session.total_challenges
                ),

                "completed": int(
                    completed or 0
                ),

                "score": int(
                    score or 0
                ),

                "wrong_attempts": int(
                    wrong_attempts or 0
                ),

                "hints_used": int(
                    hints_used or 0
                ),

                "started_at": (
                    game_session.started_at
                ),

                "completed_at": (
                    game_session.completed_at
                )
            })

        return {
            "sessions": sessions
        }

    finally:
        db.close()


# =========================================================
# Sessie-details
# =========================================================

@router.get(
    "/sessions/{session_id}"
)
def session_details(
    session_id: str,
    gameleader=Depends(
        require_gameleader
    )
):

    db = SessionLocal()

    try:
        game_session = (
            get_session_in_organization(
                db,
                session_id=session_id,
                organization_id=(
                    gameleader[
                        "organization_id"
                    ]
                )
            )
        )

        team = db.get(
            User,
            game_session.user_id
        )

        session_challenges = (
            get_session_challenges(
                db,
                game_session.id
            )
        )

        results = db.scalars(
            select(ChallengeResult)
            .where(
                ChallengeResult.session_id
                == game_session.id
            )
        ).all()

        results_by_challenge = {
            result.challenge_id: result
            for result in results
        }

        challenge_data = []

        for item in session_challenges:

            result = results_by_challenge.get(
                item.challenge_id
            )

            challenge_data.append({
                "challenge_id": (
                    item.challenge_id
                ),
                "position": (
                    item.position
                ),
                "difficulty_level": (
                    item.difficulty_level
                ),
                "status": (
                    item.status
                ),
                "attempts": (
                    result.attempts
                    if result
                    else 0
                ),
                "wrong_attempts": (
                    result.wrong_attempts
                    if result
                    else 0
                ),
                "hints_used": (
                    result.hints_used
                    if result
                    else 0
                ),
                "points": (
                    result.points
                    if result
                    else 0
                )
            })

        return {
            "id": game_session.id,

            "team": {
                "id": team.id,
                "display_name": (
                    team.display_name
                ),
                "username": (
                    team.username
                )
            },

            "status": (
                game_session.status
            ),

            "mode": (
                game_session.mode
            ),

            "current": (
                game_session.current_index
                + 1
                if game_session.status
                == "active"
                else game_session.current_index
            ),

            "total": (
                game_session.total_challenges
            ),

            "started_at": (
                game_session.started_at
            ),

            "completed_at": (
                game_session.completed_at
            ),

            "challenges": (
                challenge_data
            )
        }

    finally:
        db.close()


# =========================================================
# Live bericht / hint sturen
# =========================================================

@router.post(
    "/sessions/{session_id}/messages"
)
def send_message(
    session_id: str,
    data: SessionMessageRequest,
    gameleader=Depends(
        require_gameleader
    )
):

    message = data.message.strip()

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Bericht mag niet leeg zijn"
        )

    message_type = (
        data.message_type
        .strip()
        .lower()
    )

    if message_type not in {
        "message",
        "hint",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "message_type moet "
                "'message' of 'hint' zijn"
            )
        )

    db = SessionLocal()

    try:
        game_session = (
            get_session_in_organization(
                db,
                session_id=session_id,
                organization_id=(
                    gameleader[
                        "organization_id"
                    ]
                )
            )
        )

        if game_session.status != "active":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Berichten kunnen alleen naar "
                    "een actieve sessie worden gestuurd"
                )
            )

        current_challenge_id = None

        session_challenges = (
            get_session_challenges(
                db,
                game_session.id
            )
        )

        for item in session_challenges:
            if item.status == "active":
                current_challenge_id = (
                    item.challenge_id
                )
                break

        session_message = SessionMessage(
            session_id=game_session.id,
            sender_user_id=(
                gameleader["id"]
            ),
            challenge_id=(
                current_challenge_id
            ),
            message_type=message_type,
            message=message,

            # Spelleiderhints kosten standaard
            # bewust geen punten.
            penalty_points=0
        )

        db.add(
            session_message
        )

        db.commit()

        db.refresh(
            session_message
        )

        return {
            "status": "sent",
            "message": {
                "id": session_message.id,
                "type": (
                    session_message.message_type
                ),
                "text": (
                    session_message.message
                ),
                "challenge_id": (
                    session_message.challenge_id
                ),
                "penalty_points": (
                    session_message.penalty_points
                ),
                "created_at": (
                    session_message.created_at
                )
            }
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


# =========================================================
# Berichten van sessie bekijken
# =========================================================

@router.get(
    "/sessions/{session_id}/messages"
)
def list_messages(
    session_id: str,
    gameleader=Depends(
        require_gameleader
    )
):

    db = SessionLocal()

    try:
        get_session_in_organization(
            db,
            session_id=session_id,
            organization_id=(
                gameleader[
                    "organization_id"
                ]
            )
        )

        messages = db.scalars(
            select(SessionMessage)
            .where(
                SessionMessage.session_id
                == session_id
            )
            .order_by(
                SessionMessage.created_at.asc()
            )
        ).all()

        return {
            "messages": [
                {
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
                    ),
                    "read_at": (
                        message.read_at
                    )
                }
                for message in messages
            ]
        }

    finally:
        db.close()


# =========================================================
# PDF-rapport downloaden
# =========================================================

@router.get(
    "/sessions/{session_id}/report"
)
def download_report(
    session_id: str,
    gameleader=Depends(
        require_gameleader
    )
):

    db = SessionLocal()

    try:
        game_session = (
            get_session_in_organization(
                db,
                session_id=session_id,
                organization_id=(
                    gameleader[
                        "organization_id"
                    ]
                )
            )
        )

        if game_session.status == "active":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Een actieve sessie heeft "
                    "nog geen eindrapport."
                )
            )

        pdf_bytes, filename = (
            build_session_report(
                db,
                game_session
            )
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    f'attachment; filename="{filename}"',

                "Cache-Control":
                    "no-store",
            },
        )

    finally:
        db.close()


# =========================================================
# Sessie stoppen
# =========================================================

@router.post(
    "/sessions/{session_id}/stop"
)
def stop_game_session(
    session_id: str,
    gameleader=Depends(
        require_gameleader
    )
):

    db = SessionLocal()

    try:
        game_session = (
            get_session_in_organization(
                db,
                session_id=session_id,
                organization_id=(
                    gameleader[
                        "organization_id"
                    ]
                )
            )
        )

        return stop_session(
            db,
            game_session=game_session
        )

    finally:
        db.close()
