from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel
from sqlalchemy import (
    delete,
    func,
    select,
)

from auth import (
    create_login_token,
    hash_password,
    read_login_token,
    verify_password,
)
from challenges import (
    challenge_statistics,
    get_catalog,
    validate_manual_package,
)
from config import (
    ADMIN_COOKIE_NAME,
    LOGIN_MAX_AGE_SECONDS,
)
from database import SessionLocal
from models import (
    ChallengeResult,
    GameSession,
    Organization,
    SessionChallenge,
    SessionMessage,
    TeamChallengeAssignment,
    User,
)
from session_service import (
    ensure_session_plan,
    get_session_challenges,
    start_session,
    stop_session,
)
from report_service import build_session_report


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


# =========================================================
# Request-modellen
# =========================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class ActiveRequest(BaseModel):
    active: bool


class PasswordRequest(BaseModel):
    password: str


class OrganizationCreateRequest(BaseModel):
    name: str


class OrganizationUpdateRequest(BaseModel):
    name: str | None = None
    active: bool | None = None


class UserCreateRequest(BaseModel):
    username: str
    display_name: str
    password: str
    organization_id: int | None = None


class UserOrganizationRequest(BaseModel):
    organization_id: int | None


class SingleSessionRequest(BaseModel):
    challenge_id: str


class PackageSessionRequest(BaseModel):
    challenge_ids: list[str] | None = None
    use_saved_assignments: bool = True


class AssignmentRequest(BaseModel):
    challenge_ids: list[str]


# =========================================================
# Authenticatie
# =========================================================

def require_admin(
    request: Request
) -> dict:

    token = request.cookies.get(
        ADMIN_COOKIE_NAME
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

    if token_data.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Geen beheerdersrechten"
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

        if user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Geen beheerdersrechten"
            )

        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
        }

    finally:
        db.close()


# =========================================================
# Algemene helpers
# =========================================================

def normalize_username(
    username: str
) -> str:

    username = (
        username
        .strip()
        .lower()
    )

    if len(username) < 3:
        raise HTTPException(
            status_code=400,
            detail=(
                "Gebruikersnaam moet minimaal "
                "3 tekens bevatten"
            )
        )

    return username


def validate_display_name(
    display_name: str
) -> str:

    display_name = (
        display_name.strip()
    )

    if not display_name:
        raise HTTPException(
            status_code=400,
            detail=(
                "Weergavenaam mag niet leeg zijn"
            )
        )

    return display_name


def validate_password(
    password: str
) -> None:

    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail=(
                "Wachtwoord moet minimaal "
                "8 tekens bevatten"
            )
        )


def get_organization(
    db,
    organization_id: int
) -> Organization:

    organization = db.get(
        Organization,
        organization_id
    )

    if not organization:
        raise HTTPException(
            status_code=404,
            detail="Bedrijf niet gevonden"
        )

    return organization


def get_user_by_role(
    db,
    user_id: int,
    role: str
) -> User:

    user = db.get(
        User,
        user_id
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Gebruiker niet gevonden"
        )

    if user.role != role:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Gebruiker heeft niet de rol "
                f"'{role}'"
            )
        )

    return user


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
            key=ADMIN_COOKIE_NAME,
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
        ADMIN_COOKIE_NAME,
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
# Challengecatalogus
# =========================================================

@router.get("/challenges")
def list_challenges(
    admin=Depends(require_admin)
):

    return {
        "statistics": (
            challenge_statistics()
        ),
        "challenges": get_catalog(
            include_disabled=True
        )
    }


# =========================================================
# Bedrijven
# =========================================================

@router.get("/organizations")
def list_organizations(
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        organizations = db.scalars(
            select(Organization)
            .order_by(
                Organization.name.asc()
            )
        ).all()

        result = []

        for organization in organizations:

            team_count = db.scalar(
                select(
                    func.count(User.id)
                )
                .where(
                    User.organization_id
                    == organization.id,
                    User.role == "team"
                )
            )

            gameleader_count = db.scalar(
                select(
                    func.count(User.id)
                )
                .where(
                    User.organization_id
                    == organization.id,
                    User.role == "gameleader"
                )
            )

            result.append({
                "id": organization.id,
                "name": organization.name,
                "active": organization.active,
                "teams": int(
                    team_count or 0
                ),
                "gameleaders": int(
                    gameleader_count or 0
                ),
                "created_at": (
                    organization.created_at
                )
            })

        return {
            "organizations": result
        }

    finally:
        db.close()


@router.post("/organizations")
def create_organization(
    data: OrganizationCreateRequest,
    admin=Depends(require_admin)
):

    name = data.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Bedrijfsnaam mag niet leeg zijn"
        )

    db = SessionLocal()

    try:
        existing = db.scalar(
            select(Organization).where(
                func.lower(
                    Organization.name
                )
                == name.lower()
            )
        )

        if existing:
            raise HTTPException(
                status_code=409,
                detail="Dit bedrijf bestaat al"
            )

        organization = Organization(
            name=name,
            active=True
        )

        db.add(
            organization
        )

        db.commit()
        db.refresh(
            organization
        )

        return {
            "status": "created",
            "organization": {
                "id": organization.id,
                "name": organization.name,
                "active": organization.active,
            }
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


@router.patch(
    "/organizations/{organization_id}"
)
def update_organization(
    organization_id: int,
    data: OrganizationUpdateRequest,
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        organization = get_organization(
            db,
            organization_id
        )

        if data.name is not None:
            name = data.name.strip()

            if not name:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Bedrijfsnaam mag "
                        "niet leeg zijn"
                    )
                )

            duplicate = db.scalar(
                select(Organization).where(
                    func.lower(
                        Organization.name
                    )
                    == name.lower(),
                    Organization.id
                    != organization.id
                )
            )

            if duplicate:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Een ander bedrijf gebruikt "
                        "deze naam al"
                    )
                )

            organization.name = name

        if data.active is not None:
            organization.active = (
                data.active
            )

        db.commit()

        return {
            "status": "updated",
            "organization": {
                "id": organization.id,
                "name": organization.name,
                "active": organization.active,
            }
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


# =========================================================
# Spelleiders
# =========================================================

@router.get("/gameleaders")
def list_gameleaders(
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        rows = db.execute(
            select(
                User,
                Organization
            )
            .outerjoin(
                Organization,
                Organization.id
                == User.organization_id
            )
            .where(
                User.role == "gameleader"
            )
            .order_by(
                User.display_name.asc()
            )
        ).all()

        return {
            "gameleaders": [
                {
                    "id": user.id,
                    "username": user.username,
                    "display_name": (
                        user.display_name
                    ),
                    "active": user.active,
                    "organization_id": (
                        user.organization_id
                    ),
                    "organization": (
                        organization.name
                        if organization
                        else None
                    ),
                    "created_at": (
                        user.created_at
                    )
                }
                for user, organization in rows
            ]
        }

    finally:
        db.close()


@router.post("/gameleaders")
def create_gameleader(
    data: UserCreateRequest,
    admin=Depends(require_admin)
):

    username = normalize_username(
        data.username
    )

    display_name = (
        validate_display_name(
            data.display_name
        )
    )

    validate_password(
        data.password
    )

    if data.organization_id is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Een spelleider moet aan "
                "een bedrijf gekoppeld zijn"
            )
        )

    db = SessionLocal()

    try:
        organization = get_organization(
            db,
            data.organization_id
        )

        if not organization.active:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Dit bedrijf is uitgeschakeld"
                )
            )

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

        user = User(
            username=username,
            display_name=display_name,
            password_hash=hash_password(
                data.password
            ),
            role="gameleader",
            organization_id=(
                organization.id
            ),
            active=True
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return {
            "status": "created",
            "gameleader": {
                "id": user.id,
                "username": user.username,
                "display_name": (
                    user.display_name
                ),
                "organization_id": (
                    user.organization_id
                ),
                "active": user.active,
            }
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


@router.patch(
    "/gameleaders/{gameleader_id}/active"
)
def set_gameleader_active(
    gameleader_id: int,
    data: ActiveRequest,
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        user = get_user_by_role(
            db,
            gameleader_id,
            "gameleader"
        )

        user.active = data.active

        db.commit()

        return {
            "status": "updated",
            "active": user.active
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


@router.patch(
    "/gameleaders/{gameleader_id}/organization"
)
def set_gameleader_organization(
    gameleader_id: int,
    data: UserOrganizationRequest,
    admin=Depends(require_admin)
):

    if data.organization_id is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Een spelleider moet aan "
                "een bedrijf gekoppeld zijn"
            )
        )

    db = SessionLocal()

    try:
        user = get_user_by_role(
            db,
            gameleader_id,
            "gameleader"
        )

        organization = get_organization(
            db,
            data.organization_id
        )

        user.organization_id = (
            organization.id
        )

        db.commit()

        return {
            "status": "updated",
            "organization_id": (
                user.organization_id
            )
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


@router.post(
    "/gameleaders/{gameleader_id}/password"
)
def reset_gameleader_password(
    gameleader_id: int,
    data: PasswordRequest,
    admin=Depends(require_admin)
):

    validate_password(
        data.password
    )

    db = SessionLocal()

    try:
        user = get_user_by_role(
            db,
            gameleader_id,
            "gameleader"
        )

        user.password_hash = hash_password(
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
# Teams
# =========================================================

@router.get("/teams")
def list_teams(
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        rows = db.execute(
            select(
                User,
                Organization
            )
            .outerjoin(
                Organization,
                Organization.id
                == User.organization_id
            )
            .where(
                User.role == "team"
            )
            .order_by(
                User.display_name.asc()
            )
        ).all()

        teams = []

        for team, organization in rows:

            active_session = db.scalar(
                select(GameSession)
                .where(
                    GameSession.user_id
                    == team.id,
                    GameSession.status
                    == "active"
                )
                .order_by(
                    GameSession.started_at.desc()
                )
            )

            teams.append({
                "id": team.id,
                "username": team.username,
                "display_name": (
                    team.display_name
                ),
                "active": team.active,
                "organization_id": (
                    team.organization_id
                ),
                "organization": (
                    organization.name
                    if organization
                    else None
                ),
                "created_at": (
                    team.created_at
                ),
                "active_session": (
                    {
                        "id": active_session.id,
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
            "teams": teams
        }

    finally:
        db.close()


@router.post("/teams")
def create_team(
    data: UserCreateRequest,
    admin=Depends(require_admin)
):

    username = normalize_username(
        data.username
    )

    display_name = (
        validate_display_name(
            data.display_name
        )
    )

    validate_password(
        data.password
    )

    db = SessionLocal()

    try:
        organization_id = None

        if data.organization_id is not None:
            organization = get_organization(
                db,
                data.organization_id
            )

            organization_id = (
                organization.id
            )

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
                data.password
            ),
            role="team",
            organization_id=(
                organization_id
            ),
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
                "organization_id": (
                    team.organization_id
                ),
                "active": team.active,
            }
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


@router.patch(
    "/teams/{team_id}/active"
)
def set_team_active(
    team_id: int,
    data: ActiveRequest,
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        team = get_user_by_role(
            db,
            team_id,
            "team"
        )

        team.active = data.active

        db.commit()

        return {
            "status": "updated",
            "active": team.active
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


@router.patch(
    "/teams/{team_id}/organization"
)
def set_team_organization(
    team_id: int,
    data: UserOrganizationRequest,
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        team = get_user_by_role(
            db,
            team_id,
            "team"
        )

        if data.organization_id is None:
            team.organization_id = None

        else:
            organization = get_organization(
                db,
                data.organization_id
            )

            team.organization_id = (
                organization.id
            )

        db.commit()

        return {
            "status": "updated",
            "organization_id": (
                team.organization_id
            )
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


@router.post(
    "/teams/{team_id}/password"
)
def reset_team_password(
    team_id: int,
    data: PasswordRequest,
    admin=Depends(require_admin)
):

    validate_password(
        data.password
    )

    db = SessionLocal()

    try:
        team = get_user_by_role(
            db,
            team_id,
            "team"
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
# Challengepakket per team
# =========================================================

@router.get(
    "/teams/{team_id}/assignments"
)
def get_team_assignments(
    team_id: int,
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        get_user_by_role(
            db,
            team_id,
            "team"
        )

        assignments = db.scalars(
            select(TeamChallengeAssignment)
            .where(
                TeamChallengeAssignment.user_id
                == team_id
            )
            .order_by(
                TeamChallengeAssignment.position.asc()
            )
        ).all()

        return {
            "mode": (
                "manual"
                if assignments
                else "automatic"
            ),
            "challenge_ids": [
                assignment.challenge_id
                for assignment in assignments
            ]
        }

    finally:
        db.close()


@router.put(
    "/teams/{team_id}/assignments"
)
def set_team_assignments(
    team_id: int,
    data: AssignmentRequest,
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        get_user_by_role(
            db,
            team_id,
            "team"
        )

        try:
            challenges = (
                validate_manual_package(
                    data.challenge_ids,
                    expected_count=10
                )
            )

        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error)
            ) from error

        db.execute(
            delete(
                TeamChallengeAssignment
            ).where(
                TeamChallengeAssignment.user_id
                == team_id
            )
        )

        for position, challenge in enumerate(
            challenges,
            start=1
        ):
            db.add(
                TeamChallengeAssignment(
                    user_id=team_id,
                    challenge_id=(
                        challenge["id"]
                    ),
                    position=position,
                    difficulty_level=(
                        challenge[
                            "difficulty_level"
                        ]
                    ),
                    created_by_user_id=(
                        admin["id"]
                    )
                )
            )

        db.commit()

        return {
            "status": "updated",
            "mode": "manual",
            "challenge_ids": [
                challenge["id"]
                for challenge in challenges
            ]
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


@router.delete(
    "/teams/{team_id}/assignments"
)
def clear_team_assignments(
    team_id: int,
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        get_user_by_role(
            db,
            team_id,
            "team"
        )

        db.execute(
            delete(
                TeamChallengeAssignment
            ).where(
                TeamChallengeAssignment.user_id
                == team_id
            )
        )

        db.commit()

        return {
            "status": "cleared",
            "mode": "automatic"
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()


# =========================================================
# Sessie starten vanuit beheer
# =========================================================

@router.post(
    "/teams/{team_id}/sessions/single"
)
def admin_start_single_session(
    team_id: int,
    data: SingleSessionRequest,
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        team = get_user_by_role(
            db,
            team_id,
            "team"
        )

        if not team.active:
            raise HTTPException(
                status_code=403,
                detail="Team is uitgeschakeld"
            )

        return start_session(
            db,
            user_id=team.id,
            started_by_user_id=(
                admin["id"]
            ),
            organization_id=(
                team.organization_id
            ),
            mode="single",
            challenge_id=(
                data.challenge_id
            )
        )

    finally:
        db.close()


@router.post(
    "/teams/{team_id}/sessions/package"
)
def admin_start_package_session(
    team_id: int,
    data: PackageSessionRequest,
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        team = get_user_by_role(
            db,
            team_id,
            "team"
        )

        if not team.active:
            raise HTTPException(
                status_code=403,
                detail="Team is uitgeschakeld"
            )

        return start_session(
            db,
            user_id=team.id,
            started_by_user_id=(
                admin["id"]
            ),
            organization_id=(
                team.organization_id
            ),
            mode="package",
            challenge_ids=(
                data.challenge_ids
            ),
            use_saved_assignments=(
                data.use_saved_assignments
            )
        )

    finally:
        db.close()


# =========================================================
# Sessies
# =========================================================

@router.get("/sessions")
def list_sessions(
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        rows = db.execute(
            select(
                GameSession,
                User,
                Organization
            )
            .join(
                User,
                User.id
                == GameSession.user_id
            )
            .outerjoin(
                Organization,
                Organization.id
                == GameSession.organization_id
            )
            .order_by(
                GameSession.started_at.desc()
            )
        ).all()

        sessions = []

        for (
            game_session,
            team,
            organization,
        ) in rows:

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

                "team_id": team.id,
                "team": team.display_name,
                "username": team.username,

                "organization_id": (
                    game_session.organization_id
                ),

                "organization": (
                    organization.name
                    if organization
                    else None
                ),

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
                    else min(
                        game_session.current_index,
                        game_session.total_challenges
                    )
                ),

                "completed": int(
                    completed or 0
                ),

                "total": (
                    game_session.total_challenges
                ),

                "score": int(
                    points or 0
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


@router.get(
    "/sessions/{session_id}"
)
def session_details(
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

        ensure_session_plan(
            db,
            game_session
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

        result_map = {
            result.challenge_id: result
            for result in results
        }

        challenges = []

        for item in session_challenges:

            result = result_map.get(
                item.challenge_id
            )

            challenges.append({
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
                "completed": (
                    result.completed
                    if result
                    else False
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
                "username": team.username,
                "display_name": (
                    team.display_name
                )
            },

            "status": game_session.status,
            "mode": game_session.mode,

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

            "challenges": challenges
        }

    finally:
        db.close()


@router.get(
    "/sessions/{session_id}/report"
)
def admin_download_report(
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


@router.post(
    "/sessions/{session_id}/stop"
)
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

        return stop_session(
            db,
            game_session=game_session
        )

    finally:
        db.close()


@router.delete(
    "/sessions/{session_id}/reset"
)
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
                    "Stop een actieve sessie eerst "
                    "voordat je hem reset"
                )
            )

        # ChallengeResult heeft geen ON DELETE CASCADE,
        # dus deze verwijderen we expliciet.
        db.execute(
            delete(ChallengeResult).where(
                ChallengeResult.session_id
                == session_id
            )
        )

        # SessionChallenge en SessionMessage worden door
        # PostgreSQL automatisch verwijderd via CASCADE.
        db.delete(
            game_session
        )

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


# =========================================================
# Team verwijderen
# =========================================================

@router.delete(
    "/teams/{team_id}"
)
def delete_team(
    team_id: int,
    admin=Depends(require_admin)
):

    db = SessionLocal()

    try:
        team = get_user_by_role(
            db,
            team_id,
            "team"
        )

        active_session = db.scalar(
            select(GameSession).where(
                GameSession.user_id
                == team.id,
                GameSession.status
                == "active"
            )
        )

        if active_session:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Dit team heeft nog een actieve "
                    "sessie. Stop die eerst."
                )
            )

        session_ids = list(
            db.scalars(
                select(GameSession.id)
                .where(
                    GameSession.user_id
                    == team.id
                )
            ).all()
        )

        if session_ids:
            db.execute(
                delete(ChallengeResult).where(
                    ChallengeResult.session_id.in_(
                        session_ids
                    )
                )
            )

            db.execute(
                delete(GameSession).where(
                    GameSession.id.in_(
                        session_ids
                    )
                )
            )

        # Assignments verdwijnen automatisch door CASCADE.
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
# Scoreboard
#
# Voor BreachOut telt de beste pakketsessie per team.
# Losse oefenchallenges beïnvloeden het hoofdscoreboard niet.
# =========================================================

@router.get("/scoreboard")
def scoreboard(
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

        scoreboard_rows = []

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

            scoreboard_rows.append({
                "id": team.id,
                "username": team.username,
                "display_name": (
                    team.display_name
                ),
                "organization_id": (
                    team.organization_id
                ),
                "completed": (
                    best_completed
                ),
                "total": 10,
                "score": best_score,
            })

        scoreboard_rows.sort(
            key=lambda row: (
                -row["score"],
                -row["completed"],
                row["display_name"].lower()
            )
        )

        for position, row in enumerate(
            scoreboard_rows,
            start=1
        ):
            row["position"] = position

        return {
            "scoreboard": scoreboard_rows
        }

    finally:
        db.close()
