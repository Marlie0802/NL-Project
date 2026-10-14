from sqlalchemy import text

from database import engine


def run(statement: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(statement))


def main() -> None:
    print("ChallengeLab database migratie v2")
    print("---------------------------------")

    # =====================================================
    # 1. Organisaties
    # =====================================================

    print("1/8 organizations aanmaken...")

    run("""
        CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(150) NOT NULL UNIQUE,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # =====================================================
    # 2. Users uitbreiden
    # =====================================================

    print("2/8 users uitbreiden...")

    run("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS organization_id INTEGER;
    """)

    run("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_users_organization'
            ) THEN
                ALTER TABLE users
                ADD CONSTRAINT fk_users_organization
                FOREIGN KEY (organization_id)
                REFERENCES organizations(id);
            END IF;
        END
        $$;
    """)

    run("""
        CREATE INDEX IF NOT EXISTS
        ix_users_organization_id
        ON users (organization_id);
    """)

    # =====================================================
    # 3. Game sessions uitbreiden
    # =====================================================

    print("3/8 game_sessions uitbreiden...")

    run("""
        ALTER TABLE game_sessions
        ADD COLUMN IF NOT EXISTS organization_id INTEGER;
    """)

    run("""
        ALTER TABLE game_sessions
        ADD COLUMN IF NOT EXISTS started_by_user_id INTEGER;
    """)

    run("""
        ALTER TABLE game_sessions
        ADD COLUMN IF NOT EXISTS mode VARCHAR(20)
        NOT NULL DEFAULT 'package';
    """)

    run("""
        ALTER TABLE game_sessions
        ADD COLUMN IF NOT EXISTS total_challenges INTEGER
        NOT NULL DEFAULT 10;
    """)

    run("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_game_sessions_organization'
            ) THEN
                ALTER TABLE game_sessions
                ADD CONSTRAINT fk_game_sessions_organization
                FOREIGN KEY (organization_id)
                REFERENCES organizations(id);
            END IF;
        END
        $$;
    """)

    run("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_game_sessions_started_by'
            ) THEN
                ALTER TABLE game_sessions
                ADD CONSTRAINT fk_game_sessions_started_by
                FOREIGN KEY (started_by_user_id)
                REFERENCES users(id);
            END IF;
        END
        $$;
    """)

    run("""
        CREATE INDEX IF NOT EXISTS
        ix_game_sessions_organization_id
        ON game_sessions (organization_id);
    """)

    # =====================================================
    # 4. Challenges per sessie
    # =====================================================

    print("4/8 session_challenges aanmaken...")

    run("""
        CREATE TABLE IF NOT EXISTS session_challenges (
            id SERIAL PRIMARY KEY,

            session_id VARCHAR(36) NOT NULL,

            challenge_id VARCHAR(100) NOT NULL,

            position INTEGER NOT NULL,

            difficulty_level INTEGER NOT NULL,

            max_points INTEGER NOT NULL DEFAULT 10,

            status VARCHAR(20) NOT NULL DEFAULT 'pending',

            started_at TIMESTAMPTZ,

            completed_at TIMESTAMPTZ,

            CONSTRAINT fk_session_challenges_session
                FOREIGN KEY (session_id)
                REFERENCES game_sessions(id)
                ON DELETE CASCADE,

            CONSTRAINT uq_session_challenge_position
                UNIQUE (session_id, position),

            CONSTRAINT uq_session_challenge_id
                UNIQUE (session_id, challenge_id)
        );
    """)

    run("""
        CREATE INDEX IF NOT EXISTS
        ix_session_challenges_session_id
        ON session_challenges (session_id);
    """)

    # =====================================================
    # 5. Handmatige challengepakketten
    # =====================================================

    print("5/8 team_challenge_assignments aanmaken...")

    run("""
        CREATE TABLE IF NOT EXISTS team_challenge_assignments (
            id SERIAL PRIMARY KEY,

            user_id INTEGER NOT NULL,

            challenge_id VARCHAR(100) NOT NULL,

            position INTEGER NOT NULL,

            difficulty_level INTEGER NOT NULL,

            created_by_user_id INTEGER,

            created_at TIMESTAMPTZ
                NOT NULL DEFAULT NOW(),

            CONSTRAINT fk_team_assignment_user
                FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE,

            CONSTRAINT fk_team_assignment_creator
                FOREIGN KEY (created_by_user_id)
                REFERENCES users(id),

            CONSTRAINT uq_team_assignment_position
                UNIQUE (user_id, position),

            CONSTRAINT uq_team_assignment_challenge
                UNIQUE (user_id, challenge_id)
        );
    """)

    run("""
        CREATE INDEX IF NOT EXISTS
        ix_team_challenge_assignments_user_id
        ON team_challenge_assignments (user_id);
    """)

    # =====================================================
    # 6. Live berichten / spelleider hints
    # =====================================================

    print("6/8 session_messages aanmaken...")

    run("""
        CREATE TABLE IF NOT EXISTS session_messages (
            id SERIAL PRIMARY KEY,

            session_id VARCHAR(36) NOT NULL,

            sender_user_id INTEGER NOT NULL,

            challenge_id VARCHAR(100),

            message_type VARCHAR(20)
                NOT NULL DEFAULT 'message',

            message VARCHAR(2000) NOT NULL,

            penalty_points INTEGER
                NOT NULL DEFAULT 0,

            created_at TIMESTAMPTZ
                NOT NULL DEFAULT NOW(),

            read_at TIMESTAMPTZ,

            CONSTRAINT fk_session_messages_session
                FOREIGN KEY (session_id)
                REFERENCES game_sessions(id)
                ON DELETE CASCADE,

            CONSTRAINT fk_session_messages_sender
                FOREIGN KEY (sender_user_id)
                REFERENCES users(id)
        );
    """)

    run("""
        CREATE INDEX IF NOT EXISTS
        ix_session_messages_session_id
        ON session_messages (session_id);
    """)

    # =====================================================
    # 7. Bestaande challenge_results indexes
    # =====================================================

    print("7/8 challenge_results controleren...")

    run("""
        ALTER TABLE challenge_results
        ADD COLUMN IF NOT EXISTS hints_used INTEGER
        NOT NULL DEFAULT 0;
    """)

    run("""
        CREATE INDEX IF NOT EXISTS
        ix_challenge_results_session_id
        ON challenge_results (session_id);
    """)

    run("""
        CREATE INDEX IF NOT EXISTS
        ix_challenge_results_user_id
        ON challenge_results (user_id);
    """)

    # =====================================================
    # 8. Bestaande data voorbereiden
    # =====================================================

    print("8/8 bestaande sessies voorbereiden...")

    # Bestaande sessies blijven gewone pakketsessies.
    run("""
        UPDATE game_sessions
        SET mode = 'package'
        WHERE mode IS NULL;
    """)

    run("""
        UPDATE game_sessions
        SET total_challenges = 10
        WHERE total_challenges IS NULL;
    """)

    print()
    print("Migratie voltooid.")
    print("Bestaande users, resultaten en sessies zijn behouden.")


if __name__ == "__main__":
    main()
