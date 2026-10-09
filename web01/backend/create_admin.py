from getpass import getpass

from sqlalchemy import select

from database import SessionLocal
from models import User
from auth import hash_password


def main():

    username = input(
        "Admin gebruikersnaam: "
    ).strip().lower()

    display_name = input(
        "Weergavenaam: "
    ).strip()

    password = getpass(
        "Wachtwoord: "
    )

    password_again = getpass(
        "Wachtwoord herhalen: "
    )


    if not username:
        print("Gebruikersnaam mag niet leeg zijn.")
        return

    if not display_name:
        print("Weergavenaam mag niet leeg zijn.")
        return

    if len(password) < 10:
        print("Gebruik minimaal 10 tekens.")
        return

    if password != password_again:
        print("Wachtwoorden komen niet overeen.")
        return


    db = SessionLocal()

    try:

        existing = db.scalar(
            select(User).where(
                User.username == username
            )
        )

        if existing:
            print(
                "Deze gebruikersnaam bestaat al."
            )
            return


        user = User(
            username=username,
            display_name=display_name,
            password_hash=hash_password(
                password
            ),
            role="admin",
            active=True
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print()
        print("Adminaccount aangemaakt.")
        print(f"ID: {user.id}")
        print(f"Gebruiker: {user.username}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
