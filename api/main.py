from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, EmailStr, Field, SecretStr
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from api.database import get_session
from api.models import User
from api.security import (
    create_access_token,
    hash_password,
    verify_access_token,
    verify_login_password,
)


# Application

app = FastAPI(title="PathfinderSRC")
bearer_scheme = HTTPBearer(auto_error=False)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request"},
    )


# Schemas

class RegisterRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=64)


class UserResponse(BaseModel):
    id: UUID
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# Endpoints

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


@app.post("/login", response_model=TokenResponse)
def login(
    data: RegisterRequest,
    session: Session = Depends(get_session),
):
    user = session.exec(
        select(User).where(User.email == data.email.lower())
    ).first()

    valid = verify_login_password(
        data.password.get_secret_value(),
        user.password_hash if user else None,
    )
    if user is None or not valid:
        raise HTTPException(401, "Invalid credentials")

    return TokenResponse(
        access_token=create_access_token(user.id)
    )


@app.get("/me", response_model=UserResponse)
def me(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
):
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or missing token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        user_id = verify_access_token(credentials.credentials)
    except (InvalidTokenError, ValueError):
        raise unauthorized from None

    user = session.get(User, user_id)

    if user is None:
        raise unauthorized

    return UserResponse(id=user.id, email=user.email)