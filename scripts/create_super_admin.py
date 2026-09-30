"""Bootstrap the first super admin of a fresh installation.

Users sign in with Google, but only if their email was registered beforehand.
Run this once so the first administrator can sign in and create everyone else
from the web UI:

    python scripts/create_super_admin.py admin@example.com "Jane Doe"
    # or, with Docker Compose:
    docker compose exec web python scripts/create_super_admin.py admin@example.com "Jane Doe"

Uses CONTROL_DB_URL from the environment / .env. Idempotent.
"""

from __future__ import annotations

import argparse

from clasificador.config import load_settings
from clasificador.control_db import repository as control_repo
from clasificador.control_db.engine import create_control_engine, create_control_tables
from clasificador.db.engine import make_session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Create (or find) the super admin user.")
    parser.add_argument("email")
    parser.add_argument("name", nargs="?", default="Super Admin")
    args = parser.parse_args()

    settings = load_settings()
    engine = create_control_engine(settings.control_db_url)
    create_control_tables(engine)
    with make_session_factory(engine)() as session:
        control_repo.seed_roles(session)
        user = control_repo.get_or_create_super_admin(session, args.email.strip().lower(), args.name)
        session.commit()
        print(f"Super admin ready: {user.email} (id={user.id_usuario})")


if __name__ == "__main__":
    main()
