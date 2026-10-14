import shlex
import subprocess
import uuid

from fastapi import HTTPException

from challenges import get_challenge
from config import (
    DOCKER_CPU_LIMIT,
    DOCKER_HOST,
    DOCKER_MEMORY_LIMIT,
    DOCKER_NETWORK,
    SSH_KEY,
)


def run_remote(
    command: str,
    *,
    raise_on_error: bool = True
) -> str:
    result = subprocess.run(
        [
            "/usr/bin/ssh",
            "-i",
            SSH_KEY,
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            DOCKER_HOST,
            command,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if raise_on_error and result.returncode != 0:
        error_message = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Remote Docker-command mislukt"
        )

        raise HTTPException(
            status_code=500,
            detail=error_message
        )

    return result.stdout.strip()


def start_instance(
    challenge_id: str
) -> dict:
    challenge = get_challenge(
        challenge_id
    )

    if not challenge:
        raise HTTPException(
            status_code=404,
            detail="Challenge bestaat niet"
        )

    if not challenge["enabled"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Challenge '{challenge['name']}' "
                "is nog niet beschikbaar"
            )
        )

    instance_id = str(
        uuid.uuid4()
    )[:8]

    container_name = (
        f"challenge-{instance_id}"
    )

    route = (
        f"/c/{instance_id}"
    )

    image = shlex.quote(
        challenge["image"]
    )

    safe_container_name = shlex.quote(
        container_name
    )

    safe_network = shlex.quote(
        DOCKER_NETWORK
    )

    safe_memory = shlex.quote(
        DOCKER_MEMORY_LIMIT
    )

    safe_cpu = shlex.quote(
        DOCKER_CPU_LIMIT
    )

    command = " ".join([
        "docker run -d",

        f"--name {safe_container_name}",

        f"--network {safe_network}",

        f"--memory={safe_memory}",

        f"--cpus={safe_cpu}",

        "--restart=no",

        "--label 'challengelab.instance=true'",

        (
            "--label "
            f"'challengelab.instance_id={instance_id}'"
        ),

        (
            "--label "
            f"'challengelab.challenge_id={challenge_id}'"
        ),

        "--label 'traefik.enable=true'",

        (
            "--label "
            f"'traefik.http.routers."
            f"{container_name}.rule="
            f"PathPrefix(`{route}`)'"
        ),

        (
            "--label "
            f"'traefik.http.routers."
            f"{container_name}.entrypoints=web'"
        ),

        (
            "--label "
            f"'traefik.http.middlewares."
            f"{container_name}-strip."
            f"stripprefix.prefixes={route}'"
        ),

        (
            "--label "
            f"'traefik.http.routers."
            f"{container_name}.middlewares="
            f"{container_name}-strip'"
        ),

        (
            "--label "
            f"'traefik.http.services."
            f"{container_name}."
            f"loadbalancer.server.port=80'"
        ),

        image,
    ])

    container_id = run_remote(
        command
    )

    if not container_id:
        raise HTTPException(
            status_code=500,
            detail=(
                "Docker heeft geen container-ID "
                "teruggegeven"
            )
        )

    return {
        "instance_id": instance_id,
        "container_name": container_name,
        "container_id": container_id,
        "challenge_id": challenge_id,
        "route": f"{route}/",
    }


def remove_instance(
    instance_id: str | None
) -> None:
    if not instance_id:
        return

    container_name = (
        f"challenge-{instance_id}"
    )

    safe_container_name = shlex.quote(
        container_name
    )

    command = (
        f"docker rm -f "
        f"{safe_container_name} "
        f">/dev/null 2>&1 || true"
    )

    run_remote(
        command,
        raise_on_error=False
    )


def instance_exists(
    instance_id: str | None
) -> bool:
    if not instance_id:
        return False

    container_name = (
        f"challenge-{instance_id}"
    )

    safe_container_name = shlex.quote(
        container_name
    )

    command = (
        "docker inspect "
        f"{safe_container_name} "
        ">/dev/null 2>&1"
    )

    result = subprocess.run(
        [
            "/usr/bin/ssh",
            "-i",
            SSH_KEY,
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            DOCKER_HOST,
            command,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    return result.returncode == 0


def list_instances() -> list[dict]:
    command = (
        "docker ps "
        "--filter label=challengelab.instance=true "
        "--format "
        "'{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}'"
    )

    output = run_remote(
        command
    )

    if not output:
        return []

    instances = []

    for line in output.splitlines():
        parts = line.split(
            "|",
            3
        )

        if len(parts) != 4:
            continue

        container_id, name, image, status = parts

        instance_id = (
            name.removeprefix(
                "challenge-"
            )
        )

        instances.append({
            "instance_id": instance_id,
            "container_id": container_id,
            "container_name": name,
            "image": image,
            "status": status,
        })

    return instances
