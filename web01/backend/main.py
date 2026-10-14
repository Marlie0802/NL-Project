from fastapi import FastAPI

from admin_api import router as admin_router
from challenges import (
    challenge_statistics,
    get_catalog,
)
from config import (
    APP_NAME,
    APP_ROOT_PATH,
)
from gameleader_api import (
    router as gameleader_router,
)
from public_api import router as public_router
from session_api import router as session_router
from team_api import router as team_router


# =========================================================
# FastAPI applicatie
# =========================================================

app = FastAPI(
    title=APP_NAME,
    root_path=APP_ROOT_PATH,
)


# =========================================================
# Routers
# =========================================================

app.include_router(
    admin_router
)

app.include_router(
    gameleader_router
)

app.include_router(
    team_router
)

app.include_router(
    session_router
)

app.include_router(
    public_router
)


# =========================================================
# API status
# =========================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "ChallengeLab API",
        "product": "BreachOut",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# =========================================================
# Publieke challengecatalogus
#
# Behouden voor compatibiliteit met de huidige frontend.
# Antwoorden en hints worden nooit meegestuurd.
# =========================================================

@app.get("/catalog")
def catalog():
    challenges = get_catalog(
        include_disabled=False
    )

    return {
        "total": len(challenges),
        "challenges": challenges,
    }


# =========================================================
# Algemene challenge-info
# =========================================================

@app.get("/challenge-statistics")
def challenge_stats():
    return challenge_statistics()
