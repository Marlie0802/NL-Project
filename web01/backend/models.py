from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


# =========================================================
# Organisaties / bedrijven
# =========================================================

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


# =========================================================
# Gebruikers
#
# Rollen:
# - admin
# - gameleader
# - team
#
# Een globale admin mag organization_id = NULL hebben.
# Spelleiders en teams worden aan een organisatie gekoppeld.
# =========================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=True
    )

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    display_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="team"
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


# =========================================================
# Spelsessie
#
# mode:
# - single   = één losse challenge
# - package  = pakket van meerdere challenges
#
# status:
# - waiting
# - active
# - completed
# - cancelled
# =========================================================

class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=True
    )

    started_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="package"
    )

    current_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    total_challenges: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10
    )

    current_instance: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active"
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )


# =========================================================
# Challenges die daadwerkelijk in een sessie zitten
#
# Hiermee ligt bij de start definitief vast:
# - welke challenges het team krijgt
# - in welke volgorde
# - welk moeilijkheidsniveau
#
# status:
# - pending
# - active
# - completed
# - skipped
# =========================================================

class SessionChallenge(Base):
    __tablename__ = "session_challenges"

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "position",
            name="uq_session_challenge_position"
        ),
        UniqueConstraint(
            "session_id",
            "challenge_id",
            name="uq_session_challenge_id"
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey(
            "game_sessions.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    challenge_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    difficulty_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    max_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending"
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )


# =========================================================
# Handmatig gekozen challengepakket per team
#
# Als een team geen assignments heeft, kan ChallengeLab
# automatisch een gebalanceerd pakket genereren:
#
# 2x niveau 1
# 2x niveau 2
# 2x niveau 3
# 2x niveau 4
# 2x niveau 5
# =========================================================

class TeamChallengeAssignment(Base):
    __tablename__ = "team_challenge_assignments"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "position",
            name="uq_team_assignment_position"
        ),
        UniqueConstraint(
            "user_id",
            "challenge_id",
            name="uq_team_assignment_challenge"
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    challenge_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    difficulty_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


# =========================================================
# Resultaat per challenge
#
# hints_used:
# ingebouwde hints die het team zelf aanvraagt.
#
# Spelleider-hints worden apart opgeslagen in
# session_messages zodat die standaard geen punten kosten.
# =========================================================

class ChallengeResult(Base):
    __tablename__ = "challenge_results"

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "challenge_id",
            name="uq_session_challenge"
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("game_sessions.id"),
        nullable=False,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    challenge_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    wrong_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    hints_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )


# =========================================================
# Live berichten en hints van de spelleider
#
# message_type:
# - message
# - hint
#
# penalty_points blijft standaard 0.
# Daardoor beïnvloedt een handmatige hint van de
# spelleider het scoreboard niet, tenzij we dat later
# bewust willen inschakelen.
# =========================================================

class SessionMessage(Base):
    __tablename__ = "session_messages"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey(
            "game_sessions.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    sender_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    challenge_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="message"
    )

    message: Mapped[str] = mapped_column(
        String(2000),
        nullable=False
    )

    penalty_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
