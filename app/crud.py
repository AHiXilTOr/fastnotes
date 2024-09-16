''' CRUD операции '''

from sqlalchemy.orm import Session
import models, schemas, auth
from typing import List

def get_notes(db: Session):
    return db.query(models.Note).all()

def get_note_by_id(db: Session, note_id: int):
    return db.query(models.Note).filter(models.Note.id == note_id).first()

def update_note(db: Session, note_id: int, note: schemas.NoteUpdate):
    db_note = get_note_by_id(db, note_id)
    if db_note:
        db_note.title = note.title
        db_note.content = note.content
        if note.tags:
            tags = get_or_create_tags(db, note.tags)
            db_note.tags = tags
        db.commit()
        db.refresh(db_note)
        return db_note
    return None

def delete_note(db: Session, note_id: int):
    db_note = get_note_by_id(db, note_id)
    if db_note:
        db.delete(db_note)
        db.commit()

def get_or_create_tags(db: Session, tag_names: List[str]):
    tags = []
    for tag_name in tag_names:
        tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
        if not tag:
            tag = models.Tag(name=tag_name)
            db.add(tag)
            db.commit()
            db.refresh(tag)
        tags.append(tag)
    return tags

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not auth.verify_password(password, user.hashed_password):
        return False
    return user

def create_note(db: Session, note: schemas.NoteCreate, current_user: models.User):
    db_note = models.Note(title=note.title, content=note.content, owner_id=current_user.id)

    if note.tags:
        tags = get_or_create_tags(db, note.tags)
        db_note.tags.extend(tags)
        
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note

def get_notes_by_user(db: Session, user_id: int):
    return db.query(models.Note).filter(models.Note.owner_id == user_id).all()

def get_note_by_user_and_id(db: Session, user_id: int, note_id: int):
    return db.query(models.Note).filter(models.Note.id == note_id, models.Note.owner_id == user_id).first()

def search_notes_by_tag(db: Session, user_id: int, tag_name: str):
    return db.query(models.Note).join(models.Tag, models.Note.tags).filter(
        models.Note.owner_id == user_id,
        models.Tag.name == tag_name
    ).all()
