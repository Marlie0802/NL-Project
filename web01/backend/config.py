import os


# =========================================================
# Algemene applicatie-instellingen
# =========================================================

APP_NAME = "ChallengeLab API"
APP_ROOT_PATH = "/api"


# =========================================================
# Docker / DOCKER01
#
# Waarden kunnen later eventueel via
# /etc/challengelab.env worden overschreven.
# =========================================================

DOCKER_HOST = os.environ.get(
    "CHALLENGELAB_DOCKER_HOST",
    "team@192.168.10.23"
)

SSH_KEY = os.environ.get(
    "CHALLENGELAB_SSH_KEY",
    "/home/team/.ssh/challengelab_docker"
)

DOCKER_NETWORK = os.environ.get(
    "CHALLENGELAB_DOCKER_NETWORK",
    "challenge-net"
)

DOCKER_MEMORY_LIMIT = os.environ.get(
    "CHALLENGELAB_DOCKER_MEMORY",
    "256m"
)

DOCKER_CPU_LIMIT = os.environ.get(
    "CHALLENGELAB_DOCKER_CPUS",
    "0.50"
)


# =========================================================
# Challenge scoring
# =========================================================

BASE_POINTS = 10

WRONG_ANSWER_PENALTY = 1

HINT_PENALTY = 2

MINIMUM_POINTS = 1


# =========================================================
# Challengepakket
# =========================================================

PACKAGE_SIZE = 10

DIFFICULTY_LEVELS = 5

CHALLENGES_PER_LEVEL = 2


# =========================================================
# Authenticatie
# =========================================================

LOGIN_MAX_AGE_SECONDS = 28800  # 8 uur

ADMIN_COOKIE_NAME = "challengelab_admin_auth"

TEAM_COOKIE_NAME = "challengelab_team_auth"

GAMELEADER_COOKIE_NAME = "challengelab_gameleader_auth"


# =========================================================
# Live sessies
# =========================================================

SESSION_MESSAGE_MAX_LENGTH = 2000
