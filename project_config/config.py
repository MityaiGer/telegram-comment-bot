#config.py
from account_manager import AccountManager
from comment_sender import CommentSender
from task_manager import TaskManager

# Создаем экземпляры менеджеров
account_manager = AccountManager()
task_manager = TaskManager(account_manager)
comment_sender = CommentSender(account_manager)

# Инициализируем менеджеры
task_manager.set_comment_sender(comment_sender)