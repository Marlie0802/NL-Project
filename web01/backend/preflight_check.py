from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


BASE = Path("/opt/challengelab")

FRONTEND_FILES = [
    BASE / "frontend/index.html",
    BASE / "frontend/hint-widget.js",
    BASE / "frontend/admin/index.html",
    BASE / "frontend/spelleider/index.html",
    BASE / "frontend/scoreboard/index.html",
]

PYTHON_FILES = [
    "main.py",
    "config.py",
    "database.py",
    "models.py",
    "auth.py",
    "challenges.py",
    "scoring.py",
    "docker_service.py",
    "session_service.py",
    "team_api.py",
    "session_api.py",
    "gameleader_api.py",
    "admin_api.py",
    "public_api.py",
]

FORBIDDEN_FRONTEND_STRINGS = [
    "/api/session/start",
    "DELETE /api/session/",
]

REQUIRED_API_PATHS = {
    "/team/login",
    "/team/me",

    "/session/active",
    "/session/{session_id}",
    "/session/{session_id}/answer",
    "/session/{session_id}/hint",
    "/session/{session_id}/messages",

    "/gameleader/login",
    "/gameleader/me",
    "/gameleader/teams",
    "/gameleader/sessions",
    "/gameleader/sessions/{session_id}",
    "/gameleader/sessions/{session_id}/messages",
    "/gameleader/sessions/{session_id}/stop",
    "/gameleader/teams/{team_id}/sessions/single",
    "/gameleader/teams/{team_id}/sessions/package",

    "/admin/login",
    "/admin/me",
    "/admin/organizations",
    "/admin/gameleaders",
    "/admin/teams",
    "/admin/challenges",
    "/admin/sessions",
    "/admin/scoreboard",
    "/admin/teams/{team_id}/assignments",
    "/admin/teams/{team_id}/sessions/single",
    "/admin/teams/{team_id}/sessions/package",

    "/public/scoreboard",

    "/catalog",
    "/health",
}


errors: list[str] = []
warnings: list[str] = []


def ok(message: str) -> None:
    print(f"[ OK ] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    errors.append(message)


def warn(message: str) -> None:
    print(f"[WARN] {message}")
    warnings.append(message)


print()
print("BreachOut / ChallengeLab preflight")
print("=" * 42)
print()


# =========================================================
# 1. Bestanden
# =========================================================

print("1. Frontendbestanden")

for file_path in FRONTEND_FILES:
    if file_path.is_file():
        ok(str(file_path))
    else:
        fail(f"Ontbreekt: {file_path}")

print()


# =========================================================
# 2. Oude frontend-endpoints
# =========================================================

print("2. Oude functionaliteit controleren")

for file_path in FRONTEND_FILES:
    if not file_path.is_file():
        continue

    content = file_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    for forbidden in FORBIDDEN_FRONTEND_STRINGS:
        if forbidden in content:
            fail(
                f"{file_path.name}: oude verwijzing gevonden: "
                f"{forbidden}"
            )

if not errors:
    ok("Geen oude session/start-functionaliteit gevonden")

print()


# =========================================================
# 3. Python syntax
# =========================================================

print("3. Backend Python syntax")

compile_result = subprocess.run(
    [
        sys.executable,
        "-m",
        "py_compile",
        *[
            str(BASE / filename)
            for filename in PYTHON_FILES
        ],
    ],
    capture_output=True,
    text=True,
)

if compile_result.returncode == 0:
    ok("Alle backendbestanden compileren")
else:
    fail("Python compile-check mislukt")

    if compile_result.stderr:
        print(compile_result.stderr)

print()


# =========================================================
# 4. FastAPI / OpenAPI
# =========================================================

print("4. FastAPI routes")

try:
    sys.path.insert(
        0,
        str(BASE),
    )

    from main import app

    schema = app.openapi()

    api_paths = set(
        schema.get(
            "paths",
            {}
        ).keys()
    )

    missing_paths = sorted(
        REQUIRED_API_PATHS
        - api_paths
    )

    if missing_paths:
        for path in missing_paths:
            fail(
                f"API-route ontbreekt: {path}"
            )
    else:
        ok(
            f"Alle verplichte API-routes aanwezig "
            f"({len(api_paths)} paden totaal)"
        )

except Exception as exc:
    fail(
        f"FastAPI import/OpenAPI mislukt: {exc}"
    )

print()


# =========================================================
# 5. JavaScript syntax
# =========================================================

print("5. JavaScript syntax")

node = shutil.which("node")

if not node:
    warn(
        "Node.js niet gevonden; JavaScript syntaxcheck overgeslagen"
    )

else:
    javascript_files: list[tuple[str, str]] = []

    # Los JS-bestand
    widget_path = (
        BASE
        / "frontend"
        / "hint-widget.js"
    )

    if widget_path.is_file():
        javascript_files.append(
            (
                str(widget_path),
                widget_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                ),
            )
        )

    # Inline scripts uit HTML
    html_files = [
        BASE / "frontend/index.html",
        BASE / "frontend/admin/index.html",
        BASE / "frontend/spelleider/index.html",
        BASE / "frontend/scoreboard/index.html",
    ]

    script_pattern = re.compile(
        r"<script(?:\s[^>]*)?>(.*?)</script>",
        re.IGNORECASE | re.DOTALL,
    )

    for html_path in html_files:
        if not html_path.is_file():
            continue

        html = html_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        scripts = script_pattern.findall(
            html
        )

        for index, script in enumerate(
            scripts,
            start=1,
        ):
            javascript_files.append(
                (
                    f"{html_path} inline-script-{index}",
                    script,
                )
            )

    for label, javascript in javascript_files:
        temp_name = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".js",
                delete=False,
            ) as temp_file:
                temp_file.write(
                    javascript
                )

                temp_name = (
                    temp_file.name
                )

            result = subprocess.run(
                [
                    node,
                    "--check",
                    temp_name,
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                ok(
                    f"JavaScript: {label}"
                )
            else:
                fail(
                    f"JavaScript fout: {label}"
                )

                if result.stderr:
                    print(
                        result.stderr
                    )

        finally:
            if (
                temp_name
                and
                os.path.exists(
                    temp_name
                )
            ):
                os.unlink(
                    temp_name
                )

print()


# =========================================================
# 6. Branding / pagina-inhoud
# =========================================================

print("6. BreachOut branding")

branding_checks = {
    BASE / "frontend/index.html":
        [
            "BreachOut",
            "Wachten op de Spelleider",
        ],

    BASE / "frontend/admin/index.html":
        [
            "BreachOut",
            "Bedrijven",
            "Spelleiders",
        ],

    BASE / "frontend/spelleider/index.html":
        [
            "BreachOut",
            "Spelleider",
            "Begeleiden",
        ],

    BASE / "frontend/scoreboard/index.html":
        [
            "BreachOut",
            "Publiek scoreboard",
        ],
}

for path, required_strings in branding_checks.items():
    if not path.is_file():
        continue

    content = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    missing = [
        item
        for item in required_strings
        if item not in content
    ]

    if missing:
        fail(
            f"{path}: ontbreekt: "
            + ", ".join(missing)
        )
    else:
        ok(
            f"Branding/content: {path.name}"
        )

print()


# =========================================================
# Resultaat
# =========================================================

print("=" * 42)

if errors:
    print(
        f"PREFLIGHT MISLUKT: "
        f"{len(errors)} fout(en)"
    )

    sys.exit(1)

print("PREFLIGHT GESLAAGD")

if warnings:
    print(
        f"Waarschuwingen: "
        f"{len(warnings)}"
    )

else:
    print(
        "Geen waarschuwingen."
    )

print()
