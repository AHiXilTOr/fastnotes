import logging
from logging.handlers import TimedRotatingFileHandler
from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import crud, schemas, auth, models, hmac, hashlib
from database import engine, Base, db_dependency
from typing import List
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from datetime import timedelta
from cachetools import TTLCache

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

file_handler = TimedRotatingFileHandler('app.log', when='midnight', interval=1, backupCount=7)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Создание сущностей в базе данных
Base.metadata.create_all(bind=engine)

SECRET_KEY = "zjem#x1il3q^3n#-95%3%h$i#arp-b8+ou3$di4von18010+or"

def check_telegram_auth(auth_data: schemas.TelegramAuth):
    data_check_string = f"telegram_id={auth_data.telegram_id}\ntelegram_username={auth_data.telegram_username}"
    
    secret_key_bytes = SECRET_KEY.encode()
    secret_hash = hmac.new(secret_key_bytes, data_check_string.encode(), hashlib.sha256).hexdigest()

    if secret_hash != auth_data.hash:
        logger.warning("Неверный запрос от Telegram: %s", auth_data.telegram_id)
        raise HTTPException(status_code=403, detail="Неверный запрос от Telegram")

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.post("/register", response_model=schemas.User)
def register(user: schemas.UserCreate, db: db_dependency):
    db_user = crud.get_user_by_username(db, user.username)
    if db_user:
        logger.info("Попытка регистрации с уже существующим именем пользователя: %s", user.username)
        raise HTTPException(status_code=400, detail="Имя пользователя уже зарегистрировано")
    logger.info("Регистрация нового пользователя: %s", user.username)
    return crud.create_user(db, user)

@app.post("/token", response_model=schemas.Token)
def login_for_access_token(db: db_dependency, form_data: OAuth2PasswordRequestForm = Depends()):
    user = crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        logger.warning("Неудачная попытка входа: %s", form_data.username)
        raise HTTPException(status_code=400, detail="Неверное имя пользователя или пароль")
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    logger.info("Создан токен для пользователя: %s", form_data.username)
    return {"access_token": access_token, "token_type": "bearer"}

def get_current_user(db: db_dependency, token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        username = auth.decode_access_token(token)
        if username is None:
            logger.warning("Не удалось декодировать токен: %s", token)
            raise credentials_exception
    except JWTError:
        logger.warning("Ошибка JWT: %s", token)
        raise credentials_exception
    user = crud.get_user_by_username(db, username)
    if user is None:
        logger.warning("Пользователь не найден: %s", username)
        raise credentials_exception
    return user

@app.get("/users/me", response_model=schemas.User)
def read_users_me(current_user: schemas.User = Depends(get_current_user)):
    logger.info("Запрос информации о пользователе: %s", current_user.username)
    return current_user

@app.post("/notes/", response_model=schemas.Note)
def create_note(note: schemas.NoteCreate, db: db_dependency, current_user: schemas.User = Depends(get_current_user)):
    logger.info("Создание заметки пользователем %s: %s", current_user.username, note.title)
    return crud.create_note(db, note, current_user)

@app.get("/notes/", response_model=List[schemas.Note])
def read_notes(db: db_dependency, current_user: schemas.User = Depends(get_current_user)):
    logger.info("Получение заметок для пользователя %s", current_user.username)
    return crud.get_notes_by_user(db, current_user.id)

@app.get("/notes/{note_id}", response_model=schemas.Note)
def read_note(note_id: int, db: db_dependency, current_user: schemas.User = Depends(get_current_user)):
    db_note = crud.get_note_by_user_and_id(db, current_user.id, note_id)
    if db_note is None:
        logger.warning("Заметка не найдена для пользователя %s: %d", current_user.username, note_id)
        raise HTTPException(status_code=404, detail="Заметка не найдена")
    logger.info("Получение заметки для пользователя %s: %d", current_user.username, note_id)
    return db_note

@app.put("/notes/{note_id}", response_model=schemas.Note)
def update_note(note_id: int, note: schemas.NoteUpdate, db: db_dependency, current_user: schemas.User = Depends(get_current_user)):
    db_note = crud.get_note_by_user_and_id(db, current_user.id, note_id)
    if db_note is None:
        logger.warning("Заметка не найдена для обновления пользователя %s: %d", current_user.username, note_id)
        raise HTTPException(status_code=404, detail="Заметка не найдена")
    logger.info("Обновление заметки для пользователя %s: %d", current_user.username, note_id)
    return crud.update_note(db, note_id, note)

@app.delete("/notes/{note_id}")
def delete_note(note_id: int, db: db_dependency, current_user: schemas.User = Depends(get_current_user)):
    db_note = crud.get_note_by_user_and_id(db, current_user.id, note_id)
    if db_note is None:
        logger.warning("Заметка не найдена для удаления пользователя %s: %d", current_user.username, note_id)
        raise HTTPException(status_code=404, detail="Заметка не найдена")
    crud.delete_note(db, note_id)
    logger.info("Удаление заметки пользователем %s: %d", current_user.username, note_id)
    return {"detail": "Заметка удалена"}

@app.post("/auth/telegram-login")
async def telegram_login(auth_data: schemas.TelegramAuth, db: db_dependency):
    check_telegram_auth(auth_data)
    
    user = db.query(models.User).filter(models.User.telegram_id == auth_data.telegram_id).first()
    
    if user is None:
        user = models.User(telegram_id=auth_data.telegram_id, username=auth_data.telegram_username)
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception as e:
            db.rollback()
            logger.error("Ошибка базы данных при создании пользователя: %s", e)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ошибка базы данных")
    try:
        access_token = auth.create_access_token(data={"sub": user.username})
    except Exception as e:
        logger.error("Ошибка создания токена: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ошибка создания токена")
    
    logger.info("Telegram авторизация прошла успешно для пользователя %s", auth_data.telegram_username)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/notes/search/{tag}", response_model=List[schemas.Note])
async def search_notes(
    tag: str,
    db: db_dependency,
    current_user: schemas.User = Depends(get_current_user)
):
    logger.info("Поиск заметок по тегу '%s' для пользователя %s", tag, current_user.username)
    return crud.search_notes_by_tag(db, current_user.id, tag)

MAX_REQUESTS_PER_IP = 60
TIME_WINDOW = 60
ip_request_count = TTLCache(maxsize=10000, ttl=TIME_WINDOW)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not request or not request.client or not request.client.host:
        return Response("Недостаточно данных", status_code=400)

    ip = request.client.host
    ip_request_count[ip] = ip_request_count.get(ip, 0) + 1

    if ip_request_count[ip] > MAX_REQUESTS_PER_IP:
        return Response("Слишком много запросов", status_code=429)

    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run('main:app', host='0.0.0.0', port=3000, reload=False)
