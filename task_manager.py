#task_manager.py
import os
import json 
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
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


class TaskManager:
    def __init__(self, account_manager):
        self.tasks = asyncio.Queue()
        self.tasks_dir = "tasks"
        self.account_manager = account_manager
        self.comment_sender = None
        if not os.path.exists(self.tasks_dir):
            os.makedirs(self.tasks_dir)
    
    def set_comment_sender(self, comment_sender):
        self.comment_sender = comment_sender
    
    async def add_task_to_queue(self, task):
        await self.tasks.put(task)

    async def get_next_task(self):
        return await self.tasks.get()
    
    async def create_task(self, channel_username, post_id, comments, delay):
        try:
            task = {
                'channel_username': channel_username,
                'post_id': post_id,
                'comments': comments,
                'num_comments': len(comments),
                'status': 'pending',
                'delay': delay  
            }

            await self.add_task_to_queue(task)  
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            task_file = os.path.join(self.tasks_dir, f"task_{timestamp}.json")

            with open(task_file, 'w') as f:
                json.dump(task, f)

            logger.info(f"Создана задача: {task}")

        except Exception as e:
            logger.error(f"Ошибка при создании задачи: {str(e)}")

    async def execute_tasks(self):
        while True:
            if not self.tasks.empty():
                try:
                    task = await self.tasks.get()
                    # Извлекаем значения из задачи
                    channel_username = task['channel_username']
                    post_id = task['post_id']
                    comments = task['comments']
                    
                    # Здесь задача будет обрабатываться CommentSender, передаем параметры в метод
                    await self.comment_sender.send_reply_comment(channel_username, post_id, comments)
                    
                    self.tasks.task_done()
                except Exception as e:
                     logger.error(f"Ошибка при выполнении задачи: {str(e)}")
            await asyncio.sleep(8)