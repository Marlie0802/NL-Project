from config import (
    BASE_POINTS,
    HINT_PENALTY,
    MINIMUM_POINTS,
    WRONG_ANSWER_PENALTY,
)


# =========================================================
# Centrale scoreberekening
# =========================================================

def calculate_points(
    *,
    wrong_attempts: int = 0,
    hints_used: int = 0,
    extra_penalty: int = 0,
    base_points: int = BASE_POINTS,
    minimum_points: int = MINIMUM_POINTS,
) -> int:
    """
    Bereken de score voor één challenge.

    Standaard:
        10 punten basis
        -1 per fout antwoord
        -2 per ingebouwde hint
        minimum 1 punt bij voltooien

    extra_penalty is alvast beschikbaar voor eventuele
    toekomstige handmatige straftijd/punten.
    """

    wrong_attempts = max(
        0,
        int(wrong_attempts)
    )

    hints_used = max(
        0,
        int(hints_used)
    )

    extra_penalty = max(
        0,
        int(extra_penalty)
    )

    score = (
        int(base_points)
        - (
            wrong_attempts
            * WRONG_ANSWER_PENALTY
        )
        - (
            hints_used
            * HINT_PENALTY
        )
        - extra_penalty
    )

    return max(
        int(minimum_points),
        score
    )


# =========================================================
# Score vanuit ChallengeResult-model
# =========================================================

def calculate_result_points(
    result,
    *,
    extra_penalty: int = 0
) -> int:
    """
    Bereken punten rechtstreeks vanuit een
    ChallengeResult-object.
    """

    return calculate_points(
        wrong_attempts=result.wrong_attempts,
        hints_used=result.hints_used,
        extra_penalty=extra_penalty
    )


# =========================================================
# Potentiële score
# =========================================================

def calculate_potential_points(
    result,
    *,
    extra_penalty: int = 0
) -> int:
    """
    De score die een team krijgt als de challenge
    op dit moment correct wordt beantwoord.

    Wordt gebruikt voor bijvoorbeeld:

        "Deze challenge is nu maximaal 7 punten waard."
    """

    return calculate_result_points(
        result,
        extra_penalty=extra_penalty
    )


# =========================================================
# Scoregegevens voor API / rapport
# =========================================================

def build_score_summary(
    result,
    *,
    extra_penalty: int = 0
) -> dict:
    """
    Maak één consistente score-samenvatting.

    Handig voor:
    - session API
    - adminpanel
    - spelleider
    - rapportage
    """

    potential_points = (
        calculate_potential_points(
            result,
            extra_penalty=extra_penalty
        )
    )

    return {
        "base_points": BASE_POINTS,

        "attempts": int(
            result.attempts or 0
        ),

        "wrong_attempts": int(
            result.wrong_attempts or 0
        ),

        "hints_used": int(
            result.hints_used or 0
        ),

        "wrong_answer_penalty": (
            int(result.wrong_attempts or 0)
            * WRONG_ANSWER_PENALTY
        ),

        "hint_penalty": (
            int(result.hints_used or 0)
            * HINT_PENALTY
        ),

        "extra_penalty": int(
            extra_penalty
        ),

        "potential_points": (
            potential_points
        ),

        "points": int(
            result.points or 0
        ),

        "completed": bool(
            result.completed
        )
    }


# =========================================================
# Totale sessiescore
# =========================================================

def calculate_session_score(
    results
) -> int:
    """
    Tel alle behaalde punten van een sessie op.
    """

    return sum(
        int(result.points or 0)
        for result in results
        if result.completed
    )


# =========================================================
# Maximale sessiescore
# =========================================================

def calculate_max_session_score(
    challenge_count: int
) -> int:
    """
    Bijvoorbeeld:
        10 challenges = 100 punten
        1 challenge    = 10 punten
    """

    return (
        max(
            0,
            int(challenge_count)
        )
        * BASE_POINTS
    )
