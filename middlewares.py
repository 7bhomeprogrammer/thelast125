from aiogram import BaseMiddleware
from aiogram.types import Message
import database as db

class RoleMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        user_id = event.from_user.id
        username = event.from_user.username or "NoUsername"
        full_name = event.from_user.full_name
        
        # Обновляем username и имя при каждом сообщении
        await db.upsert_user(user_id, username, full_name)
        
        # Получаем актуальные данные из БД (через вашу функцию)
        user = await db.get_user_by_id(user_id)
        data['user'] = user  # Полезно передать данные пользователя дальше в хендлеры
        
        return await handler(event, data)