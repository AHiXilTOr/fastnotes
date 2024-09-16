''' ПОДКЛЮЧЕНИЕ К БАЗЕ '''

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from fastapi import Depends
from typing import Annotated

SQLALCHEMY_URL = "postgresql://postgres:123@localhost:5432/note_db"

engine = create_engine(SQLALCHEMY_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
