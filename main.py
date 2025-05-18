# main.py
import logging
import asyncio
from aiogram import executor, types
from bot import dp, bot
from project_config.config import account_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Не передавайте 'encoding' здесь
        logging.FileHandler('app_logs.log', encoding='utf-8'),  # Укажите кодировку только для FileHandler
    ]
)

logger = logging.getLogger(__name__)

log_file = 'app_logs.log'
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

async def on_startup(dp):
    #await bot.set_my_commands([types.BotCommand("/start", "Запустить бота")])
    logger.info("Команды бота установлены.")
    #await account_manager.connect_account()
    logger.info("Менеджер аккаунтов подключен.")

    #asyncio.create_task(account_manager.wait_for_account_connection())
    logger.info("Ожидание подключения аккаунтов запущено.")

async def on_shutdown(dp):
    await dp.storage.close()
    await dp.storage.wait_closed()
    await dp.bot.close()
    await dp.bot.wait_closed()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)
    except KeyboardInterrupt:
        loop.run_until_complete(on_shutdown(dp))
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
    finally:
        loop.close()