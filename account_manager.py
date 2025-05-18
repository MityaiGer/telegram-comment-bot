# account_manager.py
import json
import logging
import os
import random
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telethon import TelegramClient, connection
#from project_config.Proxy import proxy_settings_list
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Не передавайте 'encoding' здесь
        logging.FileHandler('app_logs.log', encoding='utf-8'),  # Укажите кодировку только для FileHandler
    ]
)

logging.getLogger('telethon').setLevel(logging.ERROR)
logging.getLogger('telethon.network.mtprotosender').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# Добавлен код для сохранения логов в файл
log_file = 'app_logs.log'
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

load_dotenv()


class AccountData:
    def __init__(self, phone_number, app_id, app_hash, session_file_name):
        self.phone_number = phone_number
        self.app_id = app_id
        self.app_hash = app_hash
        self.session_file_name = session_file_name
        self.is_working = True
        self.last_usage_time = None 

    def update_last_usage_time(self):
        self.last_usage_time = datetime.now()

    def should_disconnect(self):
        if self.last_usage_time is None:
            return True
        return (datetime.now() - self.last_usage_time) > timedelta(minutes=10)

    async def disconnect_client(self, client):
        try:
            await client.disconnect()
            logger.info(f"Отключен от аккаунта: {client.session.connection.phone}")
        except Exception as e:
            logger.error(f"Не удалось отключиться от аккаунта: {str(e)}")

class AccountManager:
    def __init__(self):
        # Изменения в конструкторе
        self.accounts = []
        self.session_dir = "accounts"
        self.failed_accounts_dir = os.path.join(os.getcwd(), 'account_fail')
        self.is_connected = False
        self.should_connect_accounts = True
        self.connecting_accounts_lock = asyncio.Lock()
        self.proxy_settings = {
            'proxy_type': os.getenv('PROXY_TYPE'),
            'addr': os.getenv('PROXY_ADDR'),
            'port': int(os.getenv('PROXY_PORT')),
            'username': os.getenv('PROXY_USERNAME'),
            'password': os.getenv('PROXY_PASSWORD'),
            'rdns': True
        }
        self.load_accounts()
        self.is_first_connection = True
        self.active_clients = []
        self.last_online = None
        logger.info("Менеджер аккаунтов инициализирован")

    def load_accounts(self):
        accounts_dir = os.path.join(os.getcwd(), 'accounts')
        logging.info(f"Папка с аккаунтами: {accounts_dir}")

        if not os.path.exists(accounts_dir):
            logging.warning("Папка с аккаунтами не существует!")
            return

        for filename in os.listdir(accounts_dir):
            if filename.endswith(".session"):
                session_file_path = os.path.join(accounts_dir, filename)
                json_file_path = os.path.join(accounts_dir, filename.replace(".session", ".json"))

                if os.path.isfile(json_file_path):
                    try:
                        with open(json_file_path, 'r') as f:
                            account_data = json.load(f)
                            app_id = account_data.get("app_id")
                            app_hash = account_data.get("app_hash")
                            session_file_name = account_data.get("session_file")

                        if not session_file_name:
                            raise ValueError("Session file name not found in JSON data")

                        account_data = AccountData(
                            account_data.get("phone"),
                            app_id,
                            app_hash,
                            session_file_name
                        )

                        self.accounts.append(account_data)
                        logging.info(f"Аккаунт загружен: {session_file_name}")

                    except Exception as e:
                        logging.error(f"Ошибка при загрузке аккаунта из файла {json_file_path}: {str(e)}")
                        continue

        logging.info(f"Загружено {len(self.accounts)} аккаунтов")
 
    # async def check_inactive_sessions(self):
    #     while True:
    #         await asyncio.sleep(60)  # Проверка каждую минуту

    #         # Перебираем активные сессии
    #         for client in self.active_clients:
    #             if client.is_connected() and not client.is_user_authorized():
    #                 # Проверяем, не использовалась ли сессия в течение 10 минут
    #                 if client.should_disconnect():
    #                     await self.disconnect_account()
    #                     return
    async def connect_account(self):
        if not self.should_connect_accounts:
            return

        async with self.connecting_accounts_lock:
            if self.is_connected or not self.should_connect_accounts:
                return

            self.is_first_connection = False
            tasks = []
            proxy_addresses = os.getenv('PROXY_ADDR').split(',')

            for index, account_data in enumerate(self.accounts):
                session_file_path = os.path.join(self.session_dir, f"{account_data.session_file_name}.session")
                proxy_address = proxy_addresses[index % len(proxy_addresses)]  # Cycle through proxy addresses

                client = TelegramClient(
                    session=session_file_path,
                    api_id=account_data.app_id,
                    api_hash=account_data.app_hash,
                    proxy={
                        'proxy_type': os.getenv('PROXY_TYPE'),
                        'addr': proxy_address,
                        'port': int(os.getenv('PROXY_PORT')),
                        'username': os.getenv('PROXY_USERNAME'),
                        'password': os.getenv('PROXY_PASSWORD'),
                        'rdns': True
                    },
                    connection=connection.ConnectionTcpFull,
                    timeout=10, connection_retries=3, retry_delay=10, auto_reconnect=True
                )

                tasks.append(self.connect_and_add_to_active_clients(client, account_data.phone_number, proxy_address))

            await asyncio.gather(*tasks)
            self.is_connected = True


    async def connect_and_add_to_active_clients(self, client, phone_number, proxy_address):
        try:
            await client.connect()
            if await client.is_user_authorized():
                self.active_clients.append(client)
                self.is_connected = True  # Устанавливаем флаг в True
                logger.info(f"Успешно подключен к аккаунту: {phone_number} по IP: {proxy_address}")
            else:
                logger.error(f"Не удалось подключиться к аккаунту: {phone_number}")
                await client.disconnect()
                await self.mark_account_as_failed(phone_number)  # Помечаем аккаунт как нерабочий
                await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Ошибка при поддержании аккаунта в онлайне: {str(e)}")


    async def mark_account_as_failed(self, phone_number):
        for account_data in self.accounts:
            if account_data.phone_number == phone_number:
                account_data.is_working = False
                logger.warning(f"Аккаунт {phone_number} помечен как нерабочий.")

                session_file_path = os.path.join(self.session_dir, f"{account_data.session_file_name}.session")
                json_file_path = os.path.join(self.session_dir, f"{account_data.session_file_name}.json")
                failed_session_path = os.path.join(self.failed_accounts_dir, f"{account_data.session_file_name}.session")
                failed_json_path = os.path.join(self.failed_accounts_dir, f"{account_data.session_file_name}.json")

                try:
                    # Перемещаем файлы 
                    os.rename(session_file_path, failed_session_path)
                    os.rename(json_file_path, failed_json_path)
                    logger.warning(f"Файлы аккаунта {phone_number} перемещены в папку account_fail")
                except Exception as e:
                    logger.error(f"Не удалось переместить сессию и/или файл JSON аккаунта {phone_number} в папку account_fail: {str(e)}")
                    # Здесь вы можете реализовать более детальную обработку ошибки

                self.accounts.remove(account_data)
                logger.warning(f"Аккаунт {phone_number} удален из списка аккаунтов.")
                break

    # async def mark_account_as_failed(self, phone_number):
    #     for account_data in self.accounts:
    #         if account_data.phone_number == phone_number:
    #             if not account_data.is_working:  # Проверяем, что аккаунт неактивен
    #                 account_data.is_working = False
    #                 logger.warning(f"Аккаунт {phone_number} помечен как нерабочий.")

    #                 session_file_path = os.path.join(self.session_dir, f"{phone_number}.session")
    #                 json_file_path = os.path.join(self.session_dir, f"{phone_number}.json")

    #                 try:
    #                     # Закрываем клиент только для неактивных аккаунтов перед удалением файлов сессии
    #                     for client in self.active_clients:
    #                         if client.session.phone != phone_number:
    #                             await client.disconnect()
    #                             continue

    #                     # Проверяем, существуют ли файлы сессии, и удаляем их
    #                     if os.path.exists(session_file_path):
    #                         os.remove(session_file_path)
    #                     if os.path.exists(json_file_path):
    #                         os.remove(json_file_path)
    #                     logger.warning(f"Файлы сессии аккаунта {phone_number} удалены.")

    #                 except Exception as e:
    #                     logger.error(f"Не удалось удалить файлы сессии аккаунта {phone_number}: {str(e)}")
    #                     # Вы можете более детально обработать ошибку, если это необходимо

    #                 self.accounts.remove(account_data)
    #                 logger.warning(f"Аккаунт {phone_number} удален из списка аккаунтов.")
    #             break  # Выходим из цикла после обработки аккаунт


    
    async def disconnect_account(self):
        for client in self.active_clients:  # Создаем копию списка, чтобы избежать изменения размера во время итерации
            try:
                if client.is_connected():
                    await client.disconnect()
                    #logger.info(f"Отключено от аккаунта: {client.session.connection_info}")
            except Exception as e:
                logger.error(f"Не удалось отключиться от аккаунта: {str(e)}")

        logger.info(f"Отключено {len(self.active_clients)} сессий")
        await asyncio.gather(*[client.disconnected for client in self.active_clients])
        self.active_clients.clear()  # Очищаем список активных клиентов
        self.is_connected = False
    # async def disconnect_account(self):
    #     while self.active_clients:
    #         client = self.active_clients.pop(0)
    #         try:
    #             if client.is_connected():
    #                 await client.disconnect()
    #                 #logger.info(f"Отключено от аккаунта: {client.session.connection_info}")
    #         except Exception as e:
    #             logger.error(f"Не удалось отключиться от аккаунта: {str(e)}")

    #     logger.info(f"Отключено {len(self.active_clients)} сессий")
    #     self.is_connected = False
    # async def disconnect_account(self):
    #     for client in self.active_clients:
    #         try:
    #             await client.disconnect()
    #             #logger.info(f"Отключено {len(self.active_clients)} сессий")
    #         except Exception as e:
    #             logger.error(f"Не удалось отключиться от аккаунта: {str(e)}")
    #     logger.info(f"Отключено {len(self.active_clients)} сессий")
    #     await asyncio.gather(*[client.disconnected for client in self.active_clients])
    #     self.active_clients.clear()  # Очищаем список активных клиентов
    #     self.is_connected = False
    #     await asyncio.gather(*[client.disconnected for client in self.active_clients])

    async def reconnect_account(self, account_data):
        for account_data in self.accounts:
            session_file_path = os.path.join(self.session_dir, f"{account_data.session_file_name}.session")
            client = TelegramClient(
                session=session_file_path,
                api_id=account_data.app_id,
                api_hash=account_data.app_hash,
                proxy=self.proxy_settings,
                auto_reconnect=False  
            )
            try:
                await self.connect_and_add_to_active_clients(client, account_data.phone_number)
                logger.info(f"Переподключен аккаунт: {account_data.phone_number}")
            except Exception as e:
                logger.error(f"Не удалось переподключить аккаунт {account_data.phone_number}. Ошибка: {str(e)}")

    async def get_active_clients(self):
        return self.active_clients

    async def get_account(self):
        if not self.active_clients:
            await self.connect_account()
            await asyncio.sleep(1800)  # Увеличенная задержка в секундах (30 минут)
        return self.active_clients.pop(random.randint(0, len(self.active_clients) - 1))