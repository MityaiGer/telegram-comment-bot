# bot.py
import os
import re
import logging
import asyncio
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from asyncio import Event
# Third-party libraries
from aiogram import Bot, Dispatcher, types, executor
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import InvalidQueryID
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from project_config.config import task_manager as global_task_manager, account_manager, CommentSender, TaskManager
# Local modules
from project_config.config import task_manager, account_manager, AccountManager, comment_sender, CommentSender

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('telethon').setLevel(logging.ERROR)
logging.getLogger('telethon.network.mtprotosender').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)
load_dotenv()

log_file = 'app_logs.log'
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)


# Bot Initialization
bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
dp = Dispatcher(bot, storage=MemoryStorage())

start_keyboard = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("/start"))
last_task_execution_time = datetime.now()
task_executed_event = Event()

monitoring_enabled = True
last_task_completed = False
bot_should_continue = True
comments_sent = False
auth_in_progress = False
# FSM States
class Form(StatesGroup):
    link = State()
    comments = State()
    delay = State()
    running = State()  

allowed_users = ["2089545494", "5187431761", "5654082445","5114237580", "5400757423","5044826920", "6921429885"]  # Список разрешенных пользователей


async def on_start_command(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id in allowed_users:
        global bot_should_continue
        bot_should_continue = True
        
        await account_manager.connect_account()
        asyncio.create_task(execute_task())
        asyncio.create_task(monitor_task_timeout())
        
        await message.reply("👋 Привет! Ты можешь использовать этого бота.")
    else:
        await message.reply("😢 Извини, но ты не имеешь доступа к этому боту.")

async def start_task_execution_and_connections():
    await account_manager.connect_account()
    asyncio.create_task(execute_task())
    print('start')
    

async def execute_task():
    global last_task_execution_time
    global comments_sent
    global last_task_completed
    while bot_should_continue:
        try:
            executed_comments = await task_manager.execute_tasks()
            if executed_comments:
                logger.info(f"Отправлено комментариев: {len(executed_comments)}")
                last_task_completed = True  # Задача выполнена
                for comment_info in executed_comments:
                    comment_text = comment_info['comment']
                    await bot.send_message(comment_info['chat_id'], f'✅ Комментарий успешно отправлен:\n\n✉️ - {comment_text}')
        except Exception as e:
            logger.error(f"Ошибка при выполнении задач: {e}")       
# Обработчик команды /start
@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    global auth_in_progress  # Используем глобальную переменную
    global last_task_completed
    global last_task_execution_time
    global monitoring_enabled 
    auth_in_progress = True
    monitoring_enabled = True
    global bot_should_continue
    bot_should_continue = True
    user_id = str(message.from_user.id)
    if user_id in allowed_users:
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton('НАЧАТЬ', callback_data='start'),
            types.InlineKeyboardButton('ОСТАНОВИТЬ', callback_data='stop')
            
        )
        msg = await message.answer('👋 Добро пожаловать!\nВыберите действие:', reply_markup=keyboard)
        await bot.pin_chat_message(message.chat.id, msg.message_id, disable_notification=True)
    else:
        await message.reply("😢 Извини, но ты не имеешь доступа к этому боту.")
    
@dp.message_handler(commands='stop', state='*')
async def process_callback_stop(callback_query: types.CallbackQuery,  state: FSMContext):
    global auth_in_progress  # Включаем блокировку
    auth_in_progress = True
    global bot_should_continue
    bot_should_continue = False
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, '⏳ Ожидайте завершения сеанса работы.')
    await account_manager.disconnect_account()
    await state.finish()
    #await bot.send_message(callback_query.from_user.id, '⏳ Ожидайте завершения сеанса работы.')
    await asyncio.sleep(20)
    await bot.send_message(callback_query.from_user.id, '⛔️ Работа бота остановлена. Для возобновления работы нажмите "ПРОДОЛЖИТЬ".')
    
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton('ПРОДОЛЖИТЬ', callback_data='start'),
        
    )
    await bot.send_message(callback_query.from_user.id, '🧠 Выберите дальнейшее действие:', reply_markup=keyboard)
   

@dp.callback_query_handler(lambda c: c.data == 'restart', state='*')
async def process_callback_start(callback_query: types.CallbackQuery, state: FSMContext):
    global auth_in_progress  # Используем глобальную переменную
    global last_task_completed
    global last_task_execution_time
    global monitoring_enabled 
    auth_in_progress = True
    monitoring_enabled = True
    global bot_should_continue
    bot_should_continue = True
    try:
        await bot.send_message(callback_query.from_user.id, '🤖 Бот авторизует сессии!\nПожалуйста подождите ⏳')
        active_clients = await account_manager.get_active_clients()
        await bot.answer_callback_query(callback_query.id)
        await Form.link.set()
        await start_task_execution_and_connections()
        await bot.send_message(callback_query.from_user.id, f"🔐 Авторизованно: {len(active_clients)} сессий")
        await bot.send_message(callback_query.from_user.id, f'✔️ Отправьте ссылку на пост 📃')
        last_task_execution_time = datetime.now()  
        asyncio.create_task(monitor_task_timeout(callback_query, state))
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton('ОСТАНОВИТЬ', callback_data='stop'),
            
        )
        await bot.send_message(callback_query.from_user.id, '🧠 Выберите дальнейшее действие:', reply_markup=keyboard)
    except InvalidQueryID as e:
        await bot.send_message(callback_query.from_user.id, f'❌ Error: {e}')
        
@dp.callback_query_handler(lambda c: c.data.startswith('connect'), state='*')
async def process_connect_category(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)

    if user_id not in allowed_users:
        await bot.answer_callback_query(callback_query.id, '😢 У вас нет доступа к этому боту.')
        return

    category = callback_query.data.split('_')[1]  # Извлекаем категорию из callback_data

    if category in ['mixed', 'male', 'female']:
        await account_manager.connect_account(category)
        await bot.answer_callback_query(callback_query.id, f'✅ Подключены аккаунты из категории: {category}')
    else:
        await bot.answer_callback_query(callback_query.id, '❌ Неизвестная категория аккаунтов.')

@dp.callback_query_handler(lambda c: c.data == 'start', state='*')
async def process_callback_start(callback_query: types.CallbackQuery, state: FSMContext):
    global auth_in_progress  # Включаем блокировку
    global last_task_execution_time
    global monitoring_enabled
    global bot_should_continue
    bot_should_continue = True
    auth_in_progress = True
    monitoring_enabled = True
    try:
        await bot.send_message(callback_query.from_user.id, '🤖 Бот авторизует сессии!\nПожалуйста подождите ⏳')
        active_clients = await account_manager.get_active_clients()
        last_task_execution_time = datetime.now()
        await bot.answer_callback_query(callback_query.id)
        await Form.link.set()
        await start_task_execution_and_connections()
        await bot.send_message(callback_query.from_user.id, f"🔐 Авторизованно: {len(active_clients)} сессий")
        await bot.send_message(callback_query.from_user.id, f'✅ Бот готов к работе!\n'
                                                        f'✔️ Отправьте ссылку на пост 📃')
        
        asyncio.create_task(monitor_task_timeout(callback_query, state))
        last_task_execution_time = datetime.now()
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton('ОСТАНОВИТЬ', callback_data='stop'),
            
        )
        await bot.send_message(callback_query.from_user.id, '🧠 Выберите дальнейшее действие:', reply_markup=keyboard)
    except InvalidQueryID as e:
        await bot.send_message(callback_query.from_user.id, f'❌ Error: {e}')
    
@dp.callback_query_handler(lambda c: c.data == 'stop', state='*')
async def process_callback_stop(callback_query: types.CallbackQuery,  state: FSMContext):
    global auth_in_progress  # Включаем блокировку
    auth_in_progress = True
    global bot_should_continue
    bot_should_continue = False
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, '⏳ Ожидайте завершения сеанса работы.')
    await account_manager.disconnect_account()
    await state.finish()
    #await bot.send_message(callback_query.from_user.id, '⏳ Ожидайте завершения сеанса работы.')
    await asyncio.sleep(20)
    await bot.send_message(callback_query.from_user.id, '⛔️ Работа бота остановлена. Для возобновления работы нажмите "ПРОДОЛЖИТЬ".')
    
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton('ПРОДОЛЖИТЬ', callback_data='start'),
        
    )
    await bot.send_message(callback_query.from_user.id, '🧠 Выберите дальнейшее действие:', reply_markup=keyboard)
   
# Обработчик получения ссылки на пост
@dp.message_handler(state=Form.link)
async def process_link(message: types.Message, state: FSMContext):
    link = message.text
    match = re.match(r'https?://t.me/[^/]+/(\d+)', link)
    if match:
        post_id = int(match.group(1))
        if post_id:
            async with state.proxy() as data:
                data['post_id'] = post_id  # Сохраняем ID оригинального поста
                
                # Извлекаем имя канала из ссылки
                channel_username = link.split('/')[-2]
                data['channel_username'] = channel_username
                
                await Form.comments.set()
                await bot.send_message(message.chat.id, '📌 Пришлите свои комментарии, каждый с новой строки.')
        else:
            await bot.send_message(message.chat.id, '❌ Неправильный формат ссылки. Пожалуйста, пришлите ссылку в формате "https://t.me/username/post_id".')
    else:
        await bot.send_message(message.chat.id, '❌ Неправильный формат ссылки. Пожалуйста, пришлите ссылку в формате "https://t.me/username/post_id".')

# Обработчик получения комментариев
@dp.message_handler(state=Form.comments)
async def process_comments(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['comments'] = message.text.split('\n')
        await Form.delay.set()
        await bot.send_message(message.chat.id, '⏰ Введите желаемую задержку между отправкой комментариев в секундах, две пары цифр, например, "60 180":\n\nПервый комментарий отправляется сразу!')

@dp.message_handler(lambda message: not all(part.isdigit() for part in message.text.split()), state=Form.delay)
async def process_invalid_delay_format(message: types.Message):
    await message.reply('❌ Пожалуйста, введите две пары цифр, разделенных пробелом, например, "60 180".')
    # Не переходите к следующему состоянию, чтобы пользователь мог повторить попытку.

# Обработчик получения задержки (корректный ввод)
@dp.message_handler(state=Form.delay)
async def process_delay(message: types.Message, state: FSMContext):
    global last_task_execution_time
    global last_task_completed
    global comments_sent

    async with state.proxy() as data:
        delays = message.text.split()

        if len(delays) == 2 and all(part.isdigit() for part in delays):
            delay_min, delay_max = int(delays[0]), int(delays[1])

            if delay_min > 0 and delay_max >= delay_min:
                data['delay_min'] = delay_min
                data['delay_max'] = delay_max
                channel_username = data['channel_username']
                post_id = data['post_id']
                comments = data['comments']
                

                try:
                    total_comments = len(comments)
                    await bot.send_message(message.chat.id, f'☝️ Всего задано {total_comments} задач(чи)')
                    for index, comment in enumerate(comments):
                        random_delay = random.randint(delay_min, delay_max)

                        task = await task_manager.create_task(channel_username, post_id, [comment], random_delay)
                        
                        if task:True
                        task_execution_time = datetime.now() + timedelta(seconds=random_delay)
                        await bot.send_message(message.chat.id, f'🔥 Задача на отправку комментария создана 🔥\n'
                                                                f'🔹 Канал: {channel_username}\n'
                                                                f'🔸 ID поста в чате: {post_id}\n'
                                                                f'⏳ Комментарий скоро будет отправлен:\n\n✍️ - {comment}\n'
                                                                f'🕒 Следущий Комментарий будет отправлен через {random_delay} секунд, '
                                                                    f'в {task_execution_time.strftime("%H:%M:%S")}')
                        
                        
                        # task_execution_time = datetime.now() + timedelta(seconds=random_delay)
                        # await bot.send_message(message.chat.id, f'🕒 Следущий Комментарий будет отправлен через {random_delay} секунд, '
                        #                                             f'в {task_execution_time.strftime("%H:%M:%S")}')
                        
                        await bot.send_message(message.chat.id, f'✅ Комментарий успешно отправлен:\n\n✉️ - {comment}')
                        await asyncio.sleep(random_delay)  
                    if index == total_comments - 1:  # Отправляем сообщение после последнего комментария
                        await bot.send_message(message.chat.id, f'🎉 Все {total_comments} задачи выполнены! 🎉\n\n⏳ Ожидайте... ')
                    last_task_completed = True
                    last_task_execution_time = datetime.now()
                    task_executed_event.set()
                    comments_sent = True
                    await state.finish()

                    keyboard = types.InlineKeyboardMarkup(row_width=2)
                    keyboard.add(
                        types.InlineKeyboardButton('ПРОДОЛЖИТЬ', callback_data='restart'),
                        types.InlineKeyboardButton('ОСТАНОВИТЬ', callback_data='stop')
                    )
                    await bot.send_message(message.chat.id, '🧠 Выберите дальнейшее действие:', reply_markup=keyboard)

                except Exception as e:
                    await bot.send_message(message.chat.id, f'❌ Ошибка при создании задачи: {str(e)}')
            else:
                await bot.send_message(message.chat.id, '❌ Некорректный ввод. Второе число должно быть больше или равно первому.')
        else:
            await bot.send_message(message.chat.id, '❌ Некорректный ввод. Введите две пары цифр, разделенных пробелом, например, "60 180".')

            
@dp.message_handler(lambda message: message.text.isdigit(), state=Form.delay)
async def monitor_task_timeout(callback_query: types.CallbackQuery, state: FSMContext):
    global last_task_execution_time
    global monitoring_enabled
    global last_task_completed
    while bot_should_continue:
        await asyncio.sleep(60)  # Проверяем каждые 60 секунд
        current_time = datetime.now()
        if current_time - last_task_execution_time >= timedelta(minutes=30):  # 10 минут (600 секунд)
            if not last_task_completed:  # Если в последние 10 минут задачи не выполнялись
                #await bot.answer_callback_query(callback_query.id)
                await bot.send_message(callback_query.from_user.id, '⛔️ Из-за отсутсвия задач бот будет отключён!')
                await bot.send_message(callback_query.from_user.id, '⏳ Ожидайте завершения сеанса работы.')
                await account_manager.disconnect_account()
                await state.finish()
                #await bot.send_message(callback_query.from_user.id, '⏳ Ожидайте завершения сеанса работы.')
                await asyncio.sleep(20)
                await bot.send_message(callback_query.from_user.id, '⛔️ Работа бота остановлена. Для возобновления работы нажмите "ПРОДОЛЖИТЬ".')
                
                keyboard = types.InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    types.InlineKeyboardButton('ПРОДОЛЖИТЬ', callback_data='start'),
                    
                )
                await bot.send_message(callback_query.from_user.id, '🧠 Выберите дальнейшее действие:', reply_markup=keyboard)
            
                return  # Выход из цикла
            else:
               last_task_completed = False

