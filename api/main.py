from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, SecretStr
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from api.database import get_session
from api.models import User
from api.security import hash_password

app = FastAPI(title="PathfinderSRC")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: SecretStr


class UserResponse(BaseModel):
    id: UUID
    email: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register", response_model=UserResponse, status_code=201)
def register(
    data: RegisterRequest,
    session: Session = Depends(get_session),
):
    try:
        hashed = hash_password(data.password.get_secret_value())
    except ValueError as error:
        raise HTTPException(422, str(error)) from None

    user = User(
        email=data.email.lower(),
        password_hash=hashed,
    )

    session.add(user)

    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if getattr(error.orig, "sqlstate", None) == "23505":
            raise HTTPException(409, "Email already registered") from None
        raise

    session.refresh(user)

    return UserResponse(id=user.id, email=user.email)