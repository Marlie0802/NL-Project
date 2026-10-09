from public_api import router as public_router
from datetime import datetime, timezone
import shlex
import subprocess
import uuid

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select

from database import SessionLocal
from models import GameSession, ChallengeResult

from admin_api import router as admin_router
from team_api import router as team_router
from team_api import require_team


app = FastAPI(
    title="ChallengeLab API",
    root_path="/api"
)

app.include_router(admin_router)
app.include_router(team_router)
app.include_router(admin_router)
app.include_router(team_router)
app.include_router(public_router)

DOCKER_HOST = "team@192.168.10.23"
SSH_KEY = "/home/team/.ssh/challengelab_docker"


CHALLENGES = [
    {
        "id": "vergeten-medewerker",
        "name": "De vergeten medewerker",
        "image": "challengelab/vergeten-medewerker:1.0",
        "difficulty": "Beginner",
        "category": "Authenticatie",
        "description": (
            "Onderzoek accountgegevens, HR-mutaties en beveiligingslogs "
            "en ontdek welk account een beveiligingsrisico vormt."
        ),
        "answers": ["tvos"]
    },
    {
        "id": "gebroken-toegangscode",
        "name": "De gebroken toegangscode",
        "image": "challengelab/gebroken-toegangscode:1.0",
        "difficulty": "Gemiddeld",
        "category": "Authenticatie",
        "description": (
            "Combineer informatie uit authenticatielogs en "
            "herstelsystemen om een MFA-herstelcode te reconstrueren."
        ),
        "answers": ["47218396"]
    },
    {
        "id": "bericht-van-directeur",
        "name": "Bericht van Directeur",
        "image": "challengelab/bericht-van-directeur:1.0",
        "difficulty": "Beginner",
        "category": "Phishing",
        "description": (
            "Onderzoek een verdachte e-mail en ontdek welk domein "
            "voor het nep-betaalportaal wordt gebruikt."
        ),
        "answers": ["secure-paymentdesk.net"]
    },
    {
        "id": "wie-kun-je-vertrouwen",
        "name": "Wie kun je vertrouwen?",
        "image": "challengelab/wie-kun-je-vertrouwen:1.0",
        "difficulty": "Gemiddeld",
        "category": "Social engineering",
        "description": (
            "Beoordeel verschillende contactpogingen en bepaal "
            "welke persoon een veilige en controleerbare procedure volgt."
        ),
        "answers": ["persoon-b"]
    },
    {
        "id": "de-verkeerde-deur",
        "name": "De verkeerde deur",
        "image": "challengelab/de-verkeerde-deur:1.0",
        "difficulty": "Beginner",
        "category": "Netwerk / firewall",
        "description": (
            "Onderzoek firewallregels en bepaal welke beheerservice "
            "ten onrechte vanaf het internet bereikbaar is."
        ),
        "answers": ["22"]
    },
    {
        "id": "de-verboden-route",
        "name": "De verboden route",
        "image": "challengelab/de-verboden-route:1.0",
        "difficulty": "Gemiddeld",
        "category": "Netwerk / firewall",
        "description": (
            "Analyseer netwerkzones en firewallregels en ontdek "
            "welke verkeersroute in strijd is met het beveiligingsbeleid."
        ),
        "answers": ["user-db"]
    },
    {
        "id": "de-ontbrekende-minuten",
        "name": "De ontbrekende minuten",
        "image": "challengelab/de-ontbrekende-minuten:1.0",
        "difficulty": "Gemiddeld",
        "category": "Forensics",
        "description": (
            "Combineer login-, bestands- en netwerklogs om te bepalen "
            "welke gebruiker actief was tijdens ontbrekende logging."
        ),
        "answers": ["mvandermeer"]
    },
    {
        "id": "wie-was-het",
        "name": "Wie was het?",
        "image": "challengelab/wie-was-het:1.0",
        "difficulty": "Gevorderd",
        "category": "Forensics",
        "description": (
            "Combineer toegangsgegevens, gebruikerslogins, "
            "IP-adressen en USB-auditlogs."
        ),
        "answers": [
            "rkuiper",
            "robin kuiper"
        ]
    },
    {
        "id": "het-geheime-bericht",
        "name": "Het geheime bericht",
        "image": "challengelab/het-geheime-bericht:1.0",
        "difficulty": "Beginner",
        "category": "Encryptie",
        "description": (
            "Ontcijfer een eenvoudig versleuteld bericht "
            "met behulp van een Caesar-verschuiving."
        ),
        "answers": ["blauw"]
    },
    {
        "id": "de-echte-kluis",
        "name": "De echte Kluis",
        "image": "challengelab/de-echte-kluis:1.0",
        "difficulty": "Gevorderd",
        "category": "Databeveiliging",
        "description": (
            "Analyseer classificaties en toegangsrechten en bepaal "
            "welk vertrouwelijk bestand onvoldoende beschermd is."
        ),
        "answers": ["salarissen.xlsx"]
    }
]


BASE_POINTS = 10
WRONG_ANSWER_PENALTY = 1
HINT_PENALTY = 2
MINIMUM_POINTS = 1

HINTS = {

    "vergeten-medewerker": [
        (
            "Vergelijk de actieve accounts met de lijst "
            "van medewerkers die nog in dienst zijn."
        ),
        (
            "Zoek naar een actief account van iemand "
            "die niet meer op de actuele medewerkerslijst staat."
        )
    ],

    "gebroken-toegangscode": [
        (
            "Begin bij het recovery request-ID dat bij "
            "Eva de Wit hoort."
        ),
        (
            "Gebruik beide codefragmenten met request-ID "
            "REC-8821 en zet ze achter elkaar."
        )
    ],

    "bericht-van-directeur": [
        (
            "Vergelijk het normale bedrijfsdomein met "
            "het domein van de link in de e-mail."
        ),
        (
            "Kijk specifiek naar het gedeelte direct na "
            "https:// in de betaallink."
        )
    ],

    "wie-kun-je-vertrouwen": [
        (
            "Een echte IT-medewerker hoeft jouw "
            "wachtwoord nooit te weten."
        ),
        (
            "Zoek de persoon van wie je de identiteit "
            "zelf via interne middelen kunt controleren."
        )
    ],

    "de-verkeerde-deur": [
        (
            "De website moet vanaf internet bereikbaar zijn, "
            "maar serverbeheer niet."
        ),
        (
            "SSH is een beheerprotocol. Controleer vanaf "
            "welk netwerk dat bereikbaar hoort te zijn."
        )
    ],

    "de-verboden-route": [
        (
            "Lees het beleid eerst zonder naar de "
            "poortnummers te kijken."
        ),
        (
            "USER-NET mag via de DMZ werken, maar niet "
            "rechtstreeks verbinding maken met DB-NET."
        )
    ],

    "de-ontbrekende-minuten": [
        (
            "Let op welk IP-adres tijdens de ontbrekende "
            "minuten actief blijft."
        ),
        (
            "Koppel 10.10.10.37 aan de gebruiker die "
            "vlak daarvoor is ingelogd."
        )
    ],

    "wie-was-het": [
        (
            "Begin bij het IP-adres waarmee het bestand "
            "op de fileserver werd geopend."
        ),
        (
            "Volg de keten: IP-adres → werkstation → "
            "ingelogde gebruiker."
        )
    ],

    "het-geheime-bericht": [
        (
            "Bij deze Caesar-versleuteling moet iedere "
            "letter drie plaatsen terug."
        ),
        (
            "KHW wordt HET. Gebruik dezelfde verschuiving "
            "voor de rest van het bericht."
        )
    ],

    "de-echte-kluis": [
        (
            "Let vooral op bestanden met de classificatie "
            "Vertrouwelijk."
        ),
        (
            "Salarisgegevens horen bij HR. Controleer wie "
            "het salarisbestand momenteel allemaal kan openen."
        )
    ]
}


def calculate_points(result: ChallengeResult) -> int:

    score = (
        BASE_POINTS
        - (
            result.wrong_attempts
            * WRONG_ANSWER_PENALTY
        )
        - (
            result.hints_used
            * HINT_PENALTY
        )
    )

    return max(
        MINIMUM_POINTS,
        score
    )


def run_remote(command: str):
    result = subprocess.run(
        [
            "/usr/bin/ssh",
            "-i", SSH_KEY,
            "-o", "StrictHostKeyChecking=no",
            DOCKER_HOST,
            command
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=result.stderr.strip() or "Remote command failed"
        )

    return result.stdout.strip()


def start_instance(challenge_id: str):
    challenge = next(
        (
            challenge
            for challenge in CHALLENGES
            if challenge["id"] == challenge_id
        ),
        None
    )

    if not challenge:
        raise HTTPException(
            status_code=404,
            detail="Challenge bestaat niet"
        )

    instance_id = str(uuid.uuid4())[:8]
    container_name = f"challenge-{instance_id}"
    route = f"/c/{instance_id}"

    image = shlex.quote(challenge["image"])

    command = (
        f"docker run -d "
        f"--name {container_name} "
        f"--network challenge-net "
        f"--memory=256m "
        f"--cpus=0.50 "
        f"--label 'challengelab.instance=true' "
        f"--label 'challengelab.challenge_id={challenge_id}' "
        f"--label 'traefik.enable=true' "
        f"--label 'traefik.http.routers.{container_name}.rule=PathPrefix(`{route}`)' "
        f"--label 'traefik.http.routers.{container_name}.entrypoints=web' "
        f"--label 'traefik.http.middlewares.{container_name}-strip.stripprefix.prefixes={route}' "
        f"--label 'traefik.http.routers.{container_name}.middlewares={container_name}-strip' "
        f"--label 'traefik.http.services.{container_name}.loadbalancer.server.port=80' "
        f"{image}"
    )

    container_id = run_remote(command)

    return {
        "instance_id": instance_id,
        "container_name": container_name,
        "container_id": container_id,
        "route": f"/c/{instance_id}/"
    }


def remove_instance(instance_id: str | None):
    if not instance_id:
        return

    container_name = f"challenge-{instance_id}"

    run_remote(
        f"docker rm -f {shlex.quote(container_name)} "
        f">/dev/null 2>&1 || true"
    )


class AnswerRequest(BaseModel):
    answer: str


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "ChallengeLab API draait"
    }


@app.get("/catalog")
def catalog():
    return {
        "total": len(CHALLENGES),
        "challenges": [
            {
                "number": index + 1,
                "id": challenge["id"],
                "name": challenge["name"],
                "difficulty": challenge["difficulty"],
                "category": challenge["category"],
                "description": challenge["description"]
            }
            for index, challenge in enumerate(CHALLENGES)
        ]
    }


@app.get("/session/active")
def active_session(
    team=Depends(require_team)
):
    db = SessionLocal()

    try:
        game_session = db.scalar(
            select(GameSession)
            .where(
                GameSession.user_id == team["id"],
                GameSession.status == "active"
            )
            .order_by(
                GameSession.started_at.desc()
            )
        )

        if not game_session:
            return {
                "active": False
            }

        index = game_session.current_index

        if index >= len(CHALLENGES):
            return {
                "active": False
            }

        challenge = CHALLENGES[index]

        return {
            "active": True,
            "session_id": game_session.id,
            "status": game_session.status,
            "current": index + 1,
            "total": len(CHALLENGES),
            "challenge": {
                "id": challenge["id"],
                "name": challenge["name"],
                "difficulty": challenge["difficulty"],
                "category": challenge["category"]
            },
            "instance_id": game_session.current_instance,
            "url": (
                f"/c/{game_session.current_instance}/"
                f"?session={game_session.id}"
            )
        }

    finally:
        db.close()

@app.post("/session/start")
def start_session(
    team=Depends(require_team)
):
    db = SessionLocal()
    instance = None

    try:
        # Voorkom meerdere actieve sessies voor hetzelfde team
        existing = db.scalar(
            select(GameSession).where(
                GameSession.user_id == team["id"],
                GameSession.status == "active"
            )
        )

        if existing:
            raise HTTPException(
                status_code=409,
                detail="Dit team heeft al een actieve sessie"
            )

        session_id = str(uuid.uuid4())

        first_challenge = CHALLENGES[0]

        # Challenge-container starten
        instance = start_instance(
            first_challenge["id"]
        )

        # Eerst de hoofdsessie maken
        game_session = GameSession(
            id=session_id,
            user_id=team["id"],
            current_index=0,
            current_instance=instance["instance_id"],
            status="active"
        )

        db.add(game_session)

        # BELANGRIJK:
        # schrijf game_sessions eerst naar PostgreSQL
        # voordat challenge_results wordt aangemaakt
        db.flush()

        # Nu bestaat session_id voor de foreign key
        first_result = ChallengeResult(
            session_id=session_id,
            user_id=team["id"],
            challenge_id=first_challenge["id"],
            attempts=0,
            wrong_attempts=0,
            completed=False,
            points=0
        )

        db.add(first_result)

        db.commit()

        return {
            "session_id": session_id,
            "status": "active",
            "current": 1,
            "total": len(CHALLENGES),
            "challenge": {
                "id": first_challenge["id"],
                "name": first_challenge["name"]
            },
            "instance_id": instance["instance_id"],
            "url": (
                f'{instance["route"]}'
                f'?session={session_id}'
            )
        }

    except:
        db.rollback()

        # Als Docker al gestart was maar de DB faalde,
        # voorkomen we een verweesde container.
        if instance:
            try:
                remove_instance(
                    instance["instance_id"]
                )
            except Exception:
                pass

        raise

    finally:
        db.close()

@app.get("/session/{session_id}")
def session_status(
    session_id: str,
    team=Depends(require_team)
):
    db = SessionLocal()

    try:
        game_session = db.scalar(
            select(GameSession).where(
                GameSession.id == session_id,
                GameSession.user_id == team["id"]
            )
        )

        if not game_session:
            raise HTTPException(
                status_code=404,
                detail="Sessie niet gevonden"
            )

        if game_session.status == "completed":
            return {
                "session_id": session_id,
                "status": "completed",
                "current": len(CHALLENGES),
                "total": len(CHALLENGES)
            }

        if game_session.status != "active":
            return {
                "session_id": session_id,
                "status": game_session.status,
                "current": game_session.current_index,
                "total": len(CHALLENGES)
            }

        index = game_session.current_index
        challenge = CHALLENGES[index]

        return {
            "session_id": session_id,
            "status": game_session.status,
            "current": index + 1,
            "total": len(CHALLENGES),
            "challenge": {
                "id": challenge["id"],
                "name": challenge["name"],
                "difficulty": challenge["difficulty"],
                "category": challenge["category"]
            },
            "instance_id": game_session.current_instance,
            "url": (
                f'/c/{game_session.current_instance}/'
                f'?session={session_id}'
            )
        }

    finally:
        db.close()

@app.post("/session/{session_id}/hint")
def request_hint(
    session_id: str,
    team=Depends(require_team)
):
    db = SessionLocal()

    try:

        game_session = db.scalar(
            select(GameSession).where(
                GameSession.id == session_id,
                GameSession.user_id == team["id"]
            )
        )

        if not game_session:
            raise HTTPException(
                status_code=404,
                detail="Sessie niet gevonden"
            )

        if game_session.status != "active":
            raise HTTPException(
                status_code=400,
                detail="Sessie is niet actief"
            )

        index = game_session.current_index

        if index >= len(CHALLENGES):
            raise HTTPException(
                status_code=400,
                detail="Geen actieve challenge"
            )

        challenge = CHALLENGES[index]

        hints = HINTS.get(
            challenge["id"],
            []
        )

        if not hints:
            raise HTTPException(
                status_code=404,
                detail="Voor deze challenge zijn geen hints beschikbaar"
            )

        result = db.scalar(
            select(ChallengeResult).where(
                ChallengeResult.session_id == session_id,
                ChallengeResult.challenge_id == challenge["id"]
            )
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Challenge-resultaat niet gevonden"
            )

        # Alle hints al gebruikt?
        if result.hints_used >= len(hints):

            return {
                "available": False,
                "message": "Er zijn geen extra hints meer.",
                "hints_used": result.hints_used,
                "total_hints": len(hints),
                "potential_points": calculate_points(
                    result
                )
            }

        hint_index = result.hints_used

        hint_text = hints[
            hint_index
        ]

        result.hints_used += 1

        db.commit()

        return {
            "available": True,
            "hint": hint_text,
            "hint_number": result.hints_used,
            "total_hints": len(hints),
            "penalty": HINT_PENALTY,
            "potential_points": calculate_points(
                result
            )
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()

@app.post("/session/{session_id}/answer")
def submit_answer(
    session_id: str,
    request: AnswerRequest,
    team=Depends(require_team)
):
    db = SessionLocal()

    try:
        game_session = db.scalar(
            select(GameSession).where(
                GameSession.id == session_id,
                GameSession.user_id == team["id"]
            )
        )

        if not game_session:
            raise HTTPException(
                status_code=404,
                detail="Sessie niet gevonden"
            )

        if game_session.status != "active":
            raise HTTPException(
                status_code=400,
                detail="Sessie is niet actief"
            )

        current_index = game_session.current_index

        if current_index >= len(CHALLENGES):
            raise HTTPException(
                status_code=400,
                detail="Geen actieve challenge"
            )

        challenge = CHALLENGES[current_index]

        result = db.scalar(
            select(ChallengeResult).where(
                ChallengeResult.session_id == session_id,
                ChallengeResult.challenge_id == challenge["id"]
            )
        )

        if not result:
            result = ChallengeResult(
                session_id=session_id,
                user_id=team["id"],
                challenge_id=challenge["id"],
                attempts=0,
                wrong_attempts=0,
                hints_used=0,
                completed=False,
                points=0
            )

            db.add(result)
            db.flush()

        # Iedere inzending telt als poging.
        result.attempts += 1

        submitted_answer = (
            request.answer
            .strip()
            .lower()
        )

        valid_answers = [
            answer.strip().lower()
            for answer in challenge["answers"]
        ]

        # Fout antwoord
        if submitted_answer not in valid_answers:
            result.wrong_attempts += 1

            db.commit()

            return {
                "correct": False,
                "message": "Dat antwoord is niet correct.",
                "attempts": result.attempts,
                "wrong_attempts": result.wrong_attempts,
                "hints_used": result.hints_used,
                "potential_points": calculate_points(
                    result
                )
            }

        # Goed antwoord
        result.completed = True

        result.points = calculate_points(
            result
        )

        result.completed_at = datetime.now(
            timezone.utc
        )

        next_index = current_index + 1

        # Laatste challenge voltooid
        if next_index >= len(CHALLENGES):
            remove_instance(
                game_session.current_instance
            )

            game_session.status = "completed"
            game_session.current_index = next_index
            game_session.current_instance = None
            game_session.completed_at = datetime.now(
                timezone.utc
            )

            db.commit()

            return {
                "correct": True,
                "completed": True,
                "points": result.points,
                "wrong_attempts": result.wrong_attempts,
                "hints_used": result.hints_used,
                "message": "Alle challenges voltooid!"
            }

        # Volgende challenge starten
        next_challenge = CHALLENGES[
            next_index
        ]

        instance = start_instance(
            next_challenge["id"]
        )

        old_instance = (
            game_session.current_instance
        )

        game_session.current_index = (
            next_index
        )

        game_session.current_instance = (
            instance["instance_id"]
        )

        next_result = ChallengeResult(
            session_id=session_id,
            user_id=team["id"],
            challenge_id=next_challenge["id"],
            attempts=0,
            wrong_attempts=0,
            hints_used=0,
            completed=False,
            points=0
        )

        db.add(next_result)
        db.commit()

        remove_instance(
            old_instance
        )

        return {
            "correct": True,
            "completed": False,
            "points": result.points,
            "wrong_attempts": result.wrong_attempts,
            "hints_used": result.hints_used,
            "message": (
                "Correct! Volgende challenge wordt gestart."
            ),
            "current": next_index + 1,
            "total": len(CHALLENGES),
            "challenge": {
                "id": next_challenge["id"],
                "name": next_challenge["name"]
            },
            "url": (
                f'{instance["route"]}'
                f'?session={session_id}'
            )
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()

@app.delete("/session/{session_id}")
def stop_session(
    session_id: str,
    team=Depends(require_team)
):
    db = SessionLocal()

    try:
        game_session = db.scalar(
            select(GameSession).where(
                GameSession.id == session_id,
                GameSession.user_id == team["id"]
            )
        )

        if not game_session:
            raise HTTPException(
                status_code=404,
                detail="Sessie niet gevonden"
            )

        remove_instance(
            game_session.current_instance
        )

        # Niet verwijderen: we willen resultaten bewaren.
        game_session.status = "cancelled"
        game_session.current_instance = None

        db.commit()

        return {
            "status": "cancelled"
        }

    except:
        db.rollback()
        raise

    finally:
        db.close()
