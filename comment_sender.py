# comment_sender.py
import logging
import asyncio
from telethon.errors import UserBannedInChannelError, FloodWaitError, PeerFloodError
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon import TelegramClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Не передавайте 'encoding' здесь
        logging.FileHandler('app_logs.log', encoding='utf-8'),  # Укажите кодировку только для FileHandler
    ]
)

logger = logging.getLogger(__name__)
#logging.getLogger('telethon').setLevel(logging.ERROR)

log_file = 'app_logs.log'
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

class CommentSender:
    def __init__(self, account_manager):
        self.account_manager = account_manager
        self.active_sessions = []

    async def send_reply_comment(self, channel_username, post_id, comments):
        if not self.active_sessions:
            self.active_sessions = await self.account_manager.get_active_clients()

        current_session = self.active_sessions.pop(0)

        try:
            await self._send_comment(current_session, channel_username, post_id, comments)
        except Exception as e:
            logger.error(f"Ошибка при отправке комментария: {str(e)}")
            # Возвращаем сессию обратно в список
            self.active_sessions.append(current_session)

    async def _send_comment(self, current_session: TelegramClient, channel_username, post_id, comments):
        try:
            channel = await current_session.get_entity(channel_username)
            message = await current_session.get_messages(channel, ids=post_id)
            #logger.info(f"сущность: {message}")
            #print(message.id, message.text)
            #message = await current_session.get_messages(channel, ids=post_id)
            #logger.info(f"сущность: {message}")
            #logger.info(f"сущность: {channel}")
            if not channel:
                logger.error(f"Не удалось найти канал {channel_username}")
                return
            
            full_channel_info = await current_session(GetFullChannelRequest(channel))
            # message = await current_session.get_messages(channel, ids=post_id)
            # logger.info(f"сущность: {message}")
            # print(message.id, message.text)
            channel_chat = full_channel_info.chats[1] if full_channel_info.chats else None
            if not channel_chat:
                logger.error("Чат для канала не найден!")
                return

            messages_chat_list = await current_session.get_messages(channel_chat, from_user=channel, limit = 100)
            #print(messages_chat_list)
            
            for message in messages_chat_list:
                try:
                    if message.fwd_from.saved_from_msg_id == post_id:
                        message_chat = message
                        break

                    else:
                        message_chat = None

                except Exception as ex:
                    print(ex)
            else: 
                message_chat = None
          
            #logger.info(f"сущность: {message_to_reply}")
            if message_chat:
                for comment_text in comments:
                    try:
                        result = await current_session.send_message(
                            channel_chat, comment_text, reply_to=message_chat
                        )
                        print("SUCCESSFUL SENDING")
                        # logger.info(f"Комментарий успешно отправлен: {comments}")
                        # await asyncio.sleep(10)  # Пример задержки в 10 секунд
                    except Exception as ex:
                        logger.error(ex)

            else:
                logger.error(f"Сообщение с id {post_id} не найдено!")

        except UserBannedInChannelError:
            logger.error("Пользователь заблокирован в этом канале!")
            current_session.is_working = False
        except FloodWaitError:
            logger.error("Слишком много запросов! Подождите и попробуйте снова позже.")
        except PeerFloodError:
            logger.error("Telegram ограничил отправку сообщений. Попробуйте позже.")
        except Exception as e:
            logger.error(f"Ошибка при отправке комментария: {str(e)}")
            # Если возникла ошибка связи, повторно подключаемся и пытаемся отправить снова
            if not current_session.is_connected():
                await current_session.connect()
        else:
            logger.info(f"Комментарий успешно отправлен: {comments}")
            # Возвращаем сессию обратно в список
            self.active_sessions.append(current_session)