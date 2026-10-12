"""Authentication service: user lookup, credential verification, creation."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, UnauthorizedError, ValidationError
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole


class AuthService:
    def get_by_email(self, db: Session, email: str) -> User | None:
        return db.scalar(
            select(User).where(User.email == email.strip().lower())
        )

    def get_by_id(self, db: Session, user_id: str) -> User | None:
        return db.get(User, user_id)

    def list_users(self, db: Session) -> list[User]:
        return list(db.scalars(select(User).order_by(User.created_at.desc())).all())

    def authenticate(self, db: Session, email: str, password: str) -> User:
        user = self.get_by_email(db, email)
        if user is None:
            raise UnauthorizedError("Invalid email or password")
        if not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedError("Account is inactive")
        return user

    def create_user(
        self,
        db: Session,
        *,
        email: str,
        password: str,
        full_name: str | None = None,
        role: str = UserRole.USER,
    ) -> User:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise ValidationError("Email is required")
        if not password or len(password) < 8:
            raise ValidationError("Password must be at least 8 characters")
        if role not in UserRole.ALL:
            raise ValidationError(f"Unsupported role: {role}")

        if self.get_by_email(db, normalized_email) is not None:
            raise ConflictError("An account with this email already exists")

        user = User(
            user_id=f"user-{uuid.uuid4().hex[:12]}",
            email=normalized_email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user