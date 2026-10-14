from datetime import datetime, timezone
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from challenges import (
    get_challenge,
    get_enabled_challenges,
    generate_balanced_package,
    validate_manual_package,
    validate_single_challenge,
)
from config import PACKAGE_SIZE
from docker_service import (
    remove_instance,
    start_instance,
)
from models import (
    ChallengeResult,
    GameSession,
    SessionChallenge,
    TeamChallengeAssignment,
)
from scoring import (
    build_score_summary,
    calculate_result_points,
)


# =========================================================
# Oude challengevolgorde
#
# Alleen gebruikt om eventueel bestaande sessies van vóór
# de refactor netjes te kunnen herstellen.
# =========================================================

LEGACY_CHALLENGE_ORDER = [
    "vergeten-medewerker",
    "gebroken-toegangscode",
    "bericht-van-directeur",
    "wie-kun-je-vertrouwen",
    "de-verkeerde-deur",
    "de-verboden-route",
    "de-ontbrekende-minuten",
    "wie-was-het",
    "het-geheime-bericht",
    "de-echte-kluis",
]


# =========================================================
# Hulpfuncties
# =========================================================

def now_utc() -> datetime:
    return datetime.now(
        timezone.utc
    )


def get_active_session(
    db: Session,
    user_id: int
) -> GameSession | None:
    return db.scalar(
        select(GameSession)
        .where(
            GameSession.user_id == user_id,
            GameSession.status == "active"
        )
        .order_by(
            GameSession.started_at.desc()
        )
    )


def get_session_for_team(
    db: Session,
    session_id: str,
    user_id: int
) -> GameSession:
    game_session = db.scalar(
        select(GameSession).where(
            GameSession.id == session_id,
            GameSession.user_id == user_id
        )
    )

    if not game_session:
        raise HTTPException(
            status_code=404,
            detail="Sessie niet gevonden"
        )

    return game_session


def get_session_challenges(
    db: Session,
    session_id: str
) -> list[SessionChallenge]:
    return list(
        db.scalars(
            select(SessionChallenge)
            .where(
                SessionChallenge.session_id
                == session_id
            )
            .order_by(
                SessionChallenge.position.asc()
            )
        ).all()
    )


def get_session_challenge_at_position(
    db: Session,
    session_id: str,
    position: int
) -> SessionChallenge | None:
    return db.scalar(
        select(SessionChallenge).where(
            SessionChallenge.session_id
            == session_id,
            SessionChallenge.position
            == position
        )
    )


# =========================================================
# Compatibiliteit met bestaande sessies
# =========================================================

def ensure_session_plan(
    db: Session,
    game_session: GameSession
) -> list[SessionChallenge]:
    """
    Zorg dat een sessie SessionChallenge-records heeft.

    Nieuwe sessies krijgen deze direct bij het starten.

    Oude sessies uit de vorige ChallengeLab-versie hebben
    deze records nog niet. In dat geval reconstrueren we
    de oude challengevolgorde zodat een actieve testsessie
    niet ineens naar een andere challenge springt.
    """

    existing = get_session_challenges(
        db,
        game_session.id
    )

    if existing:
        return existing

    position = 1

    for challenge_id in LEGACY_CHALLENGE_ORDER:
        challenge = get_challenge(
            challenge_id
        )

        if not challenge:
            continue

        status = "pending"

        if position - 1 < game_session.current_index:
            status = "completed"

        elif position - 1 == game_session.current_index:
            if game_session.status == "active":
                status = "active"

        session_challenge = SessionChallenge(
            session_id=game_session.id,
            challenge_id=challenge_id,
            position=position,
            difficulty_level=(
                challenge["difficulty_level"]
            ),
            max_points=10,
            status=status
        )

        db.add(
            session_challenge
        )

        position += 1

    game_session.total_challenges = (
        position - 1
    )

    db.flush()

    return get_session_challenges(
        db,
        game_session.id
    )


# =========================================================
# ChallengeResult ophalen / maken
# =========================================================

def ensure_result(
    db: Session,
    *,
    game_session: GameSession,
    challenge_id: str
) -> ChallengeResult:
    result = db.scalar(
        select(ChallengeResult).where(
            ChallengeResult.session_id
            == game_session.id,
            ChallengeResult.challenge_id
            == challenge_id
        )
    )

    if result:
        return result

    result = ChallengeResult(
        session_id=game_session.id,
        user_id=game_session.user_id,
        challenge_id=challenge_id,
        attempts=0,
        wrong_attempts=0,
        hints_used=0,
        completed=False,
        points=0
    )

    db.add(
        result
    )

    db.flush()

    return result


# =========================================================
# Challengepakket bepalen
# =========================================================

def get_team_assignments(
    db: Session,
    user_id: int
) -> list[TeamChallengeAssignment]:
    return list(
        db.scalars(
            select(TeamChallengeAssignment)
            .where(
                TeamChallengeAssignment.user_id
                == user_id
            )
            .order_by(
                TeamChallengeAssignment.position.asc()
            )
        ).all()
    )


def build_package(
    db: Session,
    *,
    user_id: int,
    challenge_ids: list[str] | None = None,
    use_saved_assignments: bool = True
) -> list[dict]:
    """
    Bepaal welke 10 challenges een team krijgt.

    Volgorde:

    1. challenge_ids opgegeven:
       handmatig pakket gebruiken.

    2. Opgeslagen team assignments:
       deze gebruiken.

    3. Automatisch gebalanceerd:
       2 challenges per niveau.

    4. Tijdelijke overgang:
       zolang exact de huidige 10 challenges enabled zijn,
       gebruik alle 10 van makkelijk naar moeilijk.
    """

    if challenge_ids is not None:
        return validate_manual_package(
            challenge_ids,
            expected_count=PACKAGE_SIZE
        )

    if use_saved_assignments:
        assignments = get_team_assignments(
            db,
            user_id
        )

        if assignments:
            assigned_ids = [
                assignment.challenge_id
                for assignment in assignments
            ]

            return validate_manual_package(
                assigned_ids,
                expected_count=PACKAGE_SIZE
            )

    try:
        return generate_balanced_package(
            challenges_per_level=2
        )

    except ValueError:
        enabled = get_enabled_challenges()

        # Tijdelijke overgang tijdens bouw van challenge 11-20.
        # Er zijn nu precies 10 bestaande challenges actief.
        if len(enabled) == PACKAGE_SIZE:
            return sorted(
                enabled,
                key=lambda challenge: (
                    challenge["difficulty_level"]
                )
            )

        raise HTTPException(
            status_code=409,
            detail=(
                "Er zijn nog niet voldoende actieve challenges "
                "voor een gebalanceerd pakket van 10."
            )
        )


# =========================================================
# Sessieplan opslaan
# =========================================================

def create_session_plan(
    db: Session,
    *,
    session_id: str,
    challenges: list[dict]
) -> None:
    for index, challenge in enumerate(
        challenges,
        start=1
    ):
        status = (
            "active"
            if index == 1
            else "pending"
        )

        started_at = (
            now_utc()
            if index == 1
            else None
        )

        db.add(
            SessionChallenge(
                session_id=session_id,
                challenge_id=challenge["id"],
                position=index,
                difficulty_level=(
                    challenge["difficulty_level"]
                ),
                max_points=10,
                status=status,
                started_at=started_at
            )
        )


# =========================================================
# Nieuwe sessie starten
# =========================================================

def start_session(
    db: Session,
    *,
    user_id: int,
    started_by_user_id: int,
    organization_id: int | None,
    mode: str,
    challenge_id: str | None = None,
    challenge_ids: list[str] | None = None,
    use_saved_assignments: bool = True
) -> dict:
    """
    Start een losse challenge of pakket.

    mode:
        single
        package
    """

    existing = get_active_session(
        db,
        user_id
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                "Dit team heeft al een actieve sessie."
            )
        )

    if mode == "single":
        if not challenge_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Voor een losse sessie moet een "
                    "challenge_id worden opgegeven."
                )
            )

        try:
            challenges = [
                validate_single_challenge(
                    challenge_id
                )
            ]

        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error)
            ) from error

    elif mode == "package":
        challenges = build_package(
            db,
            user_id=user_id,
            challenge_ids=challenge_ids,
            use_saved_assignments=(
                use_saved_assignments
            )
        )

    else:
        raise HTTPException(
            status_code=400,
            detail="Ongeldige sessiemodus."
        )

    session_id = str(
        uuid.uuid4()
    )

    first_challenge = challenges[0]

    instance = None

    try:
        # Eerst Docker starten.
        instance = start_instance(
            first_challenge["id"]
        )

        game_session = GameSession(
            id=session_id,
            user_id=user_id,
            organization_id=organization_id,
            started_by_user_id=(
                started_by_user_id
            ),
            mode=mode,
            current_index=0,
            total_challenges=len(
                challenges
            ),
            current_instance=(
                instance["instance_id"]
            ),
            status="active"
        )

        db.add(
            game_session
        )

        # GameSession moet eerst bestaan vanwege FK's.
        db.flush()

        create_session_plan(
            db,
            session_id=session_id,
            challenges=challenges
        )

        ensure_result(
            db,
            game_session=game_session,
            challenge_id=(
                first_challenge["id"]
            )
        )

        # =================================================
        # ONE-SHOT TEAM ASSIGNMENTS
        #
        # Opgeslagen handmatige challengekeuzes gelden
        # uitsluitend voor de eerstvolgende pakketsessie.
        #
        # Pas wissen nadat Docker + sessieplan succesvol
        # zijn opgebouwd. Bij een fout vóór deze commit
        # blijft de selectie dus beschikbaar.
        # =================================================

        if mode == "package":
            assignments = get_team_assignments(
                db,
                user_id
            )

            for assignment in assignments:
                db.delete(
                    assignment
                )

        db.commit()

    except Exception:
        db.rollback()

        if instance:
            remove_instance(
                instance["instance_id"]
            )

        raise

    return {
        "session_id": session_id,
        "status": "active",
        "mode": mode,
        "current": 1,
        "total": len(challenges),
        "challenge": {
            "id": first_challenge["id"],
            "name": first_challenge["name"],
            "difficulty": (
                first_challenge["difficulty"]
            ),
            "difficulty_level": (
                first_challenge[
                    "difficulty_level"
                ]
            ),
            "category": (
                first_challenge["category"]
            )
        },
        "instance_id": (
            instance["instance_id"]
        ),
        "url": (
            f'{instance["route"]}'
            f'?session={session_id}'
        )
    }


# =========================================================
# Huidige challenge
# =========================================================

def get_current_challenge(
    db: Session,
    game_session: GameSession
) -> tuple[
    SessionChallenge,
    dict
]:
    ensure_session_plan(
        db,
        game_session
    )

    position = (
        game_session.current_index
        + 1
    )

    session_challenge = (
        get_session_challenge_at_position(
            db,
            game_session.id,
            position
        )
    )

    if not session_challenge:
        raise HTTPException(
            status_code=400,
            detail="Geen actieve challenge gevonden."
        )

    challenge = get_challenge(
        session_challenge.challenge_id
    )

    if not challenge:
        raise HTTPException(
            status_code=500,
            detail=(
                "Challengeconfiguratie ontbreekt."
            )
        )

    return (
        session_challenge,
        challenge
    )


# =========================================================
# Sessie-status
# =========================================================

def build_session_status(
    db: Session,
    game_session: GameSession
) -> dict:
    ensure_session_plan(
        db,
        game_session
    )

    if game_session.status != "active":
        return {
            "session_id": game_session.id,
            "status": game_session.status,
            "mode": game_session.mode,
            "current": min(
                game_session.current_index,
                game_session.total_challenges
            ),
            "total": (
                game_session.total_challenges
            )
        }

    session_challenge, challenge = (
        get_current_challenge(
            db,
            game_session
        )
    )

    result = ensure_result(
        db,
        game_session=game_session,
        challenge_id=challenge["id"]
    )

    return {
        "session_id": game_session.id,
        "status": game_session.status,
        "mode": game_session.mode,
        "current": (
            game_session.current_index
            + 1
        ),
        "total": (
            game_session.total_challenges
        ),
        "challenge": {
            "id": challenge["id"],
            "name": challenge["name"],
            "difficulty": (
                challenge["difficulty"]
            ),
            "difficulty_level": (
                challenge[
                    "difficulty_level"
                ]
            ),
            "category": (
                challenge["category"]
            )
        },
        "score": build_score_summary(
            result
        ),
        "instance_id": (
            game_session.current_instance
        ),
        "url": (
            f"/c/"
            f"{game_session.current_instance}/"
            f"?session={game_session.id}"
        )
    }


# =========================================================
# Hint aanvragen
# =========================================================

def request_hint(
    db: Session,
    *,
    game_session: GameSession
) -> dict:
    if game_session.status != "active":
        raise HTTPException(
            status_code=400,
            detail="Sessie is niet actief."
        )

    _, challenge = get_current_challenge(
        db,
        game_session
    )

    hints = challenge.get(
        "hints",
        []
    )

    if not hints:
        raise HTTPException(
            status_code=404,
            detail=(
                "Voor deze challenge zijn "
                "geen hints beschikbaar."
            )
        )

    result = ensure_result(
        db,
        game_session=game_session,
        challenge_id=challenge["id"]
    )

    if result.hints_used >= len(hints):
        return {
            "available": False,
            "message": (
                "Er zijn geen extra hints meer."
            ),
            "hints_used": (
                result.hints_used
            ),
            "total_hints": len(hints),
            "score": build_score_summary(
                result
            )
        }

    hint_index = (
        result.hints_used
    )

    hint_text = hints[
        hint_index
    ]

    result.hints_used += 1

    db.commit()

    return {
        "available": True,
        "hint": hint_text,
        "hint_number": (
            result.hints_used
        ),
        "total_hints": len(hints),
        "score": build_score_summary(
            result
        )
    }


# =========================================================
# Antwoord controleren
# =========================================================

def submit_answer(
    db: Session,
    *,
    game_session: GameSession,
    submitted_answer: str
) -> dict:
    if game_session.status != "active":
        raise HTTPException(
            status_code=400,
            detail="Sessie is niet actief."
        )

    session_challenge, challenge = (
        get_current_challenge(
            db,
            game_session
        )
    )

    result = ensure_result(
        db,
        game_session=game_session,
        challenge_id=challenge["id"]
    )

    result.attempts += 1

    normalized_answer = (
        submitted_answer
        .strip()
        .lower()
    )

    valid_answers = [
        answer.strip().lower()
        for answer in challenge.get(
            "answers",
            []
        )
    ]

    # -----------------------------------------------------
    # Fout antwoord
    # -----------------------------------------------------

    if normalized_answer not in valid_answers:
        result.wrong_attempts += 1

        db.commit()

        return {
            "correct": False,
            "message": (
                "Dat antwoord is niet correct."
            ),
            "score": build_score_summary(
                result
            )
        }

    # -----------------------------------------------------
    # Goed antwoord
    # -----------------------------------------------------

    result.completed = True

    result.points = (
        calculate_result_points(
            result
        )
    )

    result.completed_at = (
        now_utc()
    )

    session_challenge.status = (
        "completed"
    )

    session_challenge.completed_at = (
        now_utc()
    )

    old_instance = (
        game_session.current_instance
    )

    next_index = (
        game_session.current_index
        + 1
    )

    # -----------------------------------------------------
    # Laatste challenge
    # -----------------------------------------------------

    if (
        next_index
        >= game_session.total_challenges
    ):
        game_session.status = (
            "completed"
        )

        game_session.current_index = (
            game_session.total_challenges
        )

        game_session.current_instance = (
            None
        )

        game_session.completed_at = (
            now_utc()
        )

        db.commit()

        remove_instance(
            old_instance
        )

        return {
            "correct": True,
            "completed": True,
            "message": (
                "Sessie voltooid!"
            ),
            "points": result.points,
            "score": build_score_summary(
                result
            ),
            "current": (
                game_session.total_challenges
            ),
            "total": (
                game_session.total_challenges
            )
        }

    # -----------------------------------------------------
    # Volgende challenge bepalen
    # -----------------------------------------------------

    next_position = (
        next_index
        + 1
    )

    next_session_challenge = (
        get_session_challenge_at_position(
            db,
            game_session.id,
            next_position
        )
    )

    if not next_session_challenge:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Volgende challenge ontbreekt "
                "in het sessieplan."
            )
        )

    next_challenge = get_challenge(
        next_session_challenge.challenge_id
    )

    if not next_challenge:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Configuratie van de volgende "
                "challenge ontbreekt."
            )
        )

    # Start eerst de volgende container.
    # Als Docker faalt wordt de huidige voortgang
    # teruggedraaid en kan opnieuw geprobeerd worden.
    try:
        next_instance = start_instance(
            next_challenge["id"]
        )

    except Exception:
        db.rollback()
        raise

    try:
        game_session.current_index = (
            next_index
        )

        game_session.current_instance = (
            next_instance["instance_id"]
        )

        next_session_challenge.status = (
            "active"
        )

        next_session_challenge.started_at = (
            now_utc()
        )

        ensure_result(
            db,
            game_session=game_session,
            challenge_id=(
                next_challenge["id"]
            )
        )

        db.commit()

    except Exception:
        db.rollback()

        remove_instance(
            next_instance["instance_id"]
        )

        raise

    remove_instance(
        old_instance
    )

    return {
        "correct": True,
        "completed": False,
        "message": (
            "Correct! De volgende challenge "
            "wordt gestart."
        ),
        "points": result.points,
        "score": build_score_summary(
            result
        ),
        "current": (
            game_session.current_index
            + 1
        ),
        "total": (
            game_session.total_challenges
        ),
        "challenge": {
            "id": next_challenge["id"],
            "name": next_challenge["name"],
            "difficulty": (
                next_challenge[
                    "difficulty"
                ]
            ),
            "difficulty_level": (
                next_challenge[
                    "difficulty_level"
                ]
            ),
            "category": (
                next_challenge["category"]
            )
        },
        "instance_id": (
            next_instance["instance_id"]
        ),
        "url": (
            f'{next_instance["route"]}'
            f'?session={game_session.id}'
        )
    }


# =========================================================
# Sessie stoppen
# =========================================================

def stop_session(
    db: Session,
    *,
    game_session: GameSession
) -> dict:
    if game_session.status != "active":
        raise HTTPException(
            status_code=400,
            detail="Deze sessie is niet actief."
        )

    old_instance = (
        game_session.current_instance
    )

    current = (
        get_session_challenge_at_position(
            db,
            game_session.id,
            game_session.current_index + 1
        )
    )

    if current and current.status == "active":
        current.status = "skipped"

    game_session.status = (
        "cancelled"
    )

    game_session.current_instance = (
        None
    )

    game_session.completed_at = (
        now_utc()
    )

    db.commit()

    remove_instance(
        old_instance
    )

    return {
        "status": "cancelled",
        "session_id": game_session.id
    }
