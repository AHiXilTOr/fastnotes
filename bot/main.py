import logging
from logging.handlers import RotatingFileHandler
import aiohttp
import hmac
import hashlib
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.middlewares import BaseMiddleware
import time

API_TOKEN = '6663497827:AAFpn5d-QDHNQ5VmErxElj3toQAaUGCBQQQ'
SECRET_KEY = "zjem#x1il3q^3n#-95%3%h$i#arp-b8+ou3$di4von18010+or"
HOST = "http://web:3000"

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=5)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class Form(StatesGroup):
    waiting_for_note_title = State()  # Состояние ожидания заголовка заметки
    waiting_for_note_content = State()  # Состояние ожидания содержимого заметки
    waiting_for_tags = State()  # Состояние ожидания ввода тегов
    waiting_for_search_tag = State()  # Состояние ожидания тега для поиска

# Middleware
class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, rate_limit):
        self.rate_limit = rate_limit
        self.user_last_message_time = {}
        super().__init__()

    async def on_process_message(self, message: types.Message, data: dict):
        user_id = message.from_user.id
        current_time = time.time()
        last_time = self.user_last_message_time.get(user_id, 0)

        if current_time - last_time < self.rate_limit:
            await message.reply("Слишком много запросов. Пожалуйста, подождите немного.")
            raise types.CancelHandler()
        
        self.user_last_message_time[user_id] = current_time

# Подключение middleware
rate_limit_middleware = RateLimitMiddleware(rate_limit=1)  # 1 секунда между запросами
dp.middleware.setup(rate_limit_middleware)

def generate_telegram_hash(telegram_id: int, telegram_username: str):
    data = f"telegram_id={telegram_id}\ntelegram_username={telegram_username}"
    secret_key_bytes = SECRET_KEY.encode()
    hmac_hash = hmac.new(secret_key_bytes, data.encode(), hashlib.sha256).hexdigest()
    return hmac_hash

async def authorize_user(telegram_id: int, telegram_username: str):
    telegram_hash = generate_telegram_hash(telegram_id, telegram_username)
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{HOST}/auth/telegram-login",
            json={
                "telegram_id": telegram_id, 
                "telegram_username": telegram_username, 
                "hash": telegram_hash
            }
        ) as response:
            return await response.json()

def main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("Список заметок", callback_data='get_notes'),
        InlineKeyboardButton("Создать заметку", callback_data='create_note'),
        InlineKeyboardButton("Поиск заметок", callback_data='search_notes')
    ]
    keyboard.add(*buttons)
    return keyboard

def cancel_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Отменить", callback_data='cancel'))
    return keyboard

async def handle_error(message: types.Message, error_message: str):
    logger.error(f"Ошибка: {error_message}")
    await message.reply(f"Произошла ошибка: {error_message}. Пожалуйста, попробуйте снова.")

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        user_info = await authorize_user(telegram_id=user_id, telegram_username=username)
        
        if "access_token" in user_info:
            await message.reply(f"Авторизация прошла успешно. Добро пожаловать, {message.from_user.first_name}!",
                                reply_markup=main_menu_keyboard())
        else:
            await message.reply("Ошибка авторизации. Пожалуйста, попробуйте снова.")
    except Exception as e:
        await handle_error(message, str(e))

@dp.callback_query_handler(lambda c: c.data == 'cancel', state="*")
async def process_cancel(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await state.finish()
        await bot.send_message(callback_query.from_user.id, "Операция отменена.")
        await bot.answer_callback_query(callback_query.id)
        logger.info(f"Операция отменена для пользователя {callback_query.from_user.id}.")
    except Exception as e:
        await handle_error(callback_query.message, str(e))

@dp.callback_query_handler(lambda c: c.data in ['get_notes', 'create_note', 'search_notes'])
async def process_callback(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        code = callback_query.data
        user_id = callback_query.from_user.id

        if code == 'get_notes':
            user_info = await authorize_user(telegram_id=user_id, telegram_username=callback_query.from_user.username)
            access_token = user_info.get('access_token')
            headers = {"Authorization": f"Bearer {access_token}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{HOST}/notes/", headers=headers) as response:
                    if response.status == 200:
                        notes = await response.json()
                        if notes:
                            reply = "\n\n".join([f"{note['title']}: {note['content']}" for note in notes])
                            await bot.send_message(callback_query.from_user.id, reply)
                        else:
                            await bot.send_message(callback_query.from_user.id, "У вас пока нет заметок.")
                    else:
                        await bot.send_message(callback_query.from_user.id, "Ошибка при получении заметок.")
        elif code == 'create_note':
            await bot.send_message(callback_query.from_user.id, "Введите заголовок для новой заметки:",
                                   reply_markup=cancel_keyboard())
            await Form.waiting_for_note_title.set()
            await state.update_data(action='create_note')
        elif code == 'search_notes':
            await bot.send_message(callback_query.from_user.id, "Введите тег для поиска:",
                                   reply_markup=cancel_keyboard())
            await Form.waiting_for_search_tag.set()
            await state.update_data(action='search_notes')
    except Exception as e:
        await handle_error(callback_query.message, str(e))

@dp.message_handler(state=Form.waiting_for_note_title)
async def process_note_title(message: types.Message, state: FSMContext):
    try:
        title = message.text.strip()
        if not title:
            await message.reply("Заголовок не может быть пустым. Пожалуйста, введите заголовок заново:")
            return
        
        async with state.proxy() as data:
            data['note_title'] = title
        await message.reply("Введите содержимое заметки:", reply_markup=cancel_keyboard())
        await Form.waiting_for_note_content.set()
    except Exception as e:
        await handle_error(message, str(e))

@dp.message_handler(state=Form.waiting_for_note_content)
async def process_note_content(message: types.Message, state: FSMContext):
    try:
        content = message.text.strip()
        if not content:
            await message.reply("Содержимое заметки не может быть пустым. Пожалуйста, введите содержимое заново:")
            return

        async with state.proxy() as data:
            data['note_content'] = content

        await message.reply("Введите теги для заметки (через запятую):", reply_markup=cancel_keyboard())
        await Form.waiting_for_tags.set()
    except Exception as e:
        await handle_error(message, str(e))

@dp.message_handler(state=Form.waiting_for_tags)
async def process_note_tags(message: types.Message, state: FSMContext):
    try:
        tags = [tag.strip() for tag in message.text.split(',')]
        if not tags:
            await message.reply("Теги не могут быть пустыми. Пожалуйста, введите теги заново:")
            return

        async with state.proxy() as data:
            note_title = data['note_title']
            note_content = data['note_content']

        user_id = message.from_user.id
        user_info = await authorize_user(telegram_id=user_id, telegram_username=message.from_user.username)
        access_token = user_info.get('access_token')
        headers = {"Authorization": f"Bearer {access_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{HOST}/notes/",
                json={"title": note_title, "content": note_content, "tags": tags},
                headers=headers
            ) as response:
                if response.status == 201 or response.status == 200:
                    await message.reply("Заметка успешно создана!")
                    logger.info("Заметка успешно создана.")
                else:
                    error_message = await response.text()
                    await message.reply(f"Ошибка при создании заметки. Статус код: {response.status}, Тело ответа: {error_message}")
                    logger.error(f"Ошибка при создании заметки: {response.status} {error_message}")
        
        await state.finish()
        logger.info("Состояние завершено после создания заметки.")
    except Exception as e:
        await handle_error(message, str(e))

@dp.message_handler(state=Form.waiting_for_search_tag)
async def process_search_tag(message: types.Message, state: FSMContext):
    try:
        tag = message.text.strip()
        if not tag:
            await message.reply("Тег для поиска не может быть пустым. Пожалуйста, введите тег заново:")
            return

        user_id = message.from_user.id
        user_info = await authorize_user(telegram_id=user_id, telegram_username=message.from_user.username)
        access_token = user_info.get('access_token')
        headers = {"Authorization": f"Bearer {access_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{HOST}/notes/search/{tag}", headers=headers) as response:
                if response.status == 200:
                    notes = await response.json()
                    if notes:
                        reply = "\n\n".join([f"{note['title']}: {note['content']}" for note in notes])
                        await message.reply(reply)
                    else:
                        await message.reply("По вашему запросу ничего не найдено.")
                else:
                    await message.reply(f"Ошибка при поиске заметок по тегу: {response.status}")
    except Exception as e:
        await handle_error(message, str(e))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
