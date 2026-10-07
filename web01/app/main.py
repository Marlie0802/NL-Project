from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import uuid
import sqlite3
import shlex
from pathlib import Path


app = FastAPI(
    title="ChallengeLab API",
    root_path="/api"
)


DOCKER_HOST = "team@192.168.10.23"
SSH_KEY = "/home/team/.ssh/challengelab_docker"

DB_PATH = "/opt/challengelab/challengelab.db"


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
    }
	,
    {
    "id": "bericht-van-directeur",
    "name": "Bericht van Directeur",
    "image": "challengelab/bericht-van-directeur:1.0",
    "difficulty": "Beginner",
    "category": "Phishing",
    "description": (
        "Onderzoek een verdachte e-mail, controleer de headers "
        "en ontdek welk domein voor de phishingaanval wordt gebruikt."
    ),
    "answers": [
        "secure-paymentdesk.net"
    ]
    }
	,
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
        "welke directe verkeersroute in strijd is met het beveiligingsbeleid."
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
        "welke gebruiker actief was tijdens een ontbrekend stuk logging."
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
        "Combineer fysieke toegangsgegevens, gebruikerslogins, "
        "IP-adressen en USB-auditlogs om de verantwoordelijke medewerker te vinden."
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
    "answers": [
        "blauw"
    ]
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
    "answers": [
        "salarissen.xlsx"
    ]
}
]

# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            current_index INTEGER NOT NULL DEFAULT 0,
            current_instance TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.commit()
    db.close()


init_db()


# ---------------------------------------------------------
# Remote Docker
# ---------------------------------------------------------

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
        (c for c in CHALLENGES if c["id"] == challenge_id),
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


# ---------------------------------------------------------
# API models
# ---------------------------------------------------------

class AnswerRequest(BaseModel):
    answer: str


# ---------------------------------------------------------
# General API
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "ChallengeLab API draait"
    }


@app.get("/catalog")
def catalog():
    result = []

    for index, challenge in enumerate(CHALLENGES):
        result.append({
            "number": index + 1,
            "id": challenge["id"],
            "name": challenge["name"],
            "difficulty": challenge["difficulty"],
            "category": challenge["category"],
            "description": challenge["description"]
        })

    return {
        "total": len(result),
        "challenges": result
    }


# ---------------------------------------------------------
# Sessions
# ---------------------------------------------------------

@app.post("/session/start")
def start_session():
    session_id = str(uuid.uuid4())

    first_challenge = CHALLENGES[0]

    instance = start_instance(
        first_challenge["id"]
    )

    db = get_db()

    db.execute(
        """
        INSERT INTO sessions (
            id,
            current_index,
            current_instance,
            status
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            session_id,
            0,
            instance["instance_id"],
            "active"
        )
    )

    db.commit()
    db.close()

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


@app.get("/session/{session_id}")
def session_status(session_id: str):
    db = get_db()

    session = db.execute(
        "SELECT * FROM sessions WHERE id = ?",
        (session_id,)
    ).fetchone()

    db.close()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Sessie niet gevonden"
        )

    if session["status"] == "completed":
        return {
            "session_id": session_id,
            "status": "completed",
            "current": len(CHALLENGES),
            "total": len(CHALLENGES)
        }

    index = session["current_index"]
    challenge = CHALLENGES[index]

    return {
        "session_id": session_id,
        "status": session["status"],
        "current": index + 1,
        "total": len(CHALLENGES),
        "challenge": {
            "id": challenge["id"],
            "name": challenge["name"],
            "difficulty": challenge["difficulty"],
            "category": challenge["category"]
        },
        "instance_id": session["current_instance"],
        "url": (
            f'/c/{session["current_instance"]}/'
            f'?session={session_id}'
        )
    }


@app.post("/session/{session_id}/answer")
def submit_answer(
    session_id: str,
    request: AnswerRequest
):
    db = get_db()

    session = db.execute(
        "SELECT * FROM sessions WHERE id = ?",
        (session_id,)
    ).fetchone()

    if not session:
        db.close()

        raise HTTPException(
            status_code=404,
            detail="Sessie niet gevonden"
        )

    if session["status"] != "active":
        db.close()

        raise HTTPException(
            status_code=400,
            detail="Sessie is niet actief"
        )

    current_index = session["current_index"]

    if current_index >= len(CHALLENGES):
        db.close()

        raise HTTPException(
            status_code=400,
            detail="Geen actieve challenge"
        )

    challenge = CHALLENGES[current_index]

    submitted_answer = request.answer.strip().lower()

    valid_answers = [
        answer.lower()
        for answer in challenge["answers"]
    ]

    if submitted_answer not in valid_answers:
        db.close()

        return {
            "correct": False,
            "message": "Dat antwoord is niet correct."
        }

    # Oude challenge opruimen
    remove_instance(
        session["current_instance"]
    )

    next_index = current_index + 1

    # Alle challenges voltooid
    if next_index >= len(CHALLENGES):
        db.execute(
            """
            UPDATE sessions
            SET
                status = 'completed',
                current_instance = NULL,
                current_index = ?
            WHERE id = ?
            """,
            (
                next_index,
                session_id
            )
        )

        db.commit()
        db.close()

        return {
            "correct": True,
            "completed": True,
            "message": "Alle challenges voltooid!"
        }

    # Volgende challenge starten
    next_challenge = CHALLENGES[next_index]

    instance = start_instance(
        next_challenge["id"]
    )

    db.execute(
        """
        UPDATE sessions
        SET
            current_index = ?,
            current_instance = ?
        WHERE id = ?
        """,
        (
            next_index,
            instance["instance_id"],
            session_id
        )
    )

    db.commit()
    db.close()

    return {
        "correct": True,
        "completed": False,
        "message": "Correct! Volgende challenge wordt gestart.",
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


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    db = get_db()

    session = db.execute(
        "SELECT * FROM sessions WHERE id = ?",
        (session_id,)
    ).fetchone()

    if not session:
        db.close()

        raise HTTPException(
            status_code=404,
            detail="Sessie niet gevonden"
        )

    remove_instance(
        session["current_instance"]
    )

    db.execute(
        "DELETE FROM sessions WHERE id = ?",
        (session_id,)
    )

    db.commit()
    db.close()

    return {
        "status": "deleted"
    }
