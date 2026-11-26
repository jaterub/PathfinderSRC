from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(max_length=254, unique=True)
    password_hash: str = Field(max_length=255)
