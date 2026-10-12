"""Create or promote an admin user.

Usage:
    python -m app.scripts.create_admin --email admin@stockwiz.local --password 'StrongPass123'
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.user import User, UserRole
from app.services.auth_service import AuthService


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create or promote an admin user")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--full-name", default=None)
    p.add_argument("--promote", action="store_true",
                   help="If the user exists, promote them to ADMIN")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    email = args.email.strip().lower()

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))

        if existing is not None:
            if not args.promote:
                print(
                    f"User '{email}' already exists "
                    f"(user_id={existing.user_id}, role={existing.role}). "
                    f"Re-run with --promote.",
                    file=sys.stderr,
                )
                return 1
            existing.role = UserRole.ADMIN
            existing.hashed_password = hash_password(args.password)
            existing.is_active = True
            db.commit()
            print(f"Promoted '{email}' to ADMIN (user_id={existing.user_id}).")
            return 0

        service = AuthService()
        user = service.create_user(
            db, email=email, password=args.password,
            full_name=args.full_name, role=UserRole.ADMIN,
        )
        print(f"Created ADMIN '{user.email}' (user_id={user.user_id}).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())