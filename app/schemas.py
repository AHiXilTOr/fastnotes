''' pydantic scheme '''

from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class TagBase(BaseModel):
    name: str

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int
    class ConfigDict:
        from_attributes = True

class NoteBase(BaseModel):
    title: str
    content: str
    tags: Optional[List[str]] = []

class NoteCreate(NoteBase):
    pass

class NoteUpdate(NoteBase):
    pass

class Note(NoteBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    tags: List[Tag] = []

    class ConfigDict:
        from_attributes = True

# работа с пользователями

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    class ConfigDict:
        from_attributes = True

# для авторизации

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None


# телеграм

class TelegramAuth(BaseModel):
    telegram_id: int
    telegram_username: str
    hash: str