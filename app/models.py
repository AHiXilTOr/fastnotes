''' Сущности базы данных '''

from sqlalchemy import Column, Integer, String, Text, DateTime, Table, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

note_tag = Table(
    'note_tag',
    Base.metadata,
    Column('note_id', Integer, ForeignKey('notes.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    telegram_id = Column(BigInteger, unique=True, index=True)

    notes = relationship("Note", back_populates="owner")

class Note(Base):
    __tablename__ = 'notes'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    owner_id = Column(Integer, ForeignKey('users.id'))
    owner = relationship("User", back_populates="notes")

    tags = relationship("Tag", secondary=note_tag, back_populates="notes")

class Tag(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    notes = relationship("Note", secondary=note_tag, back_populates="tags")