import asyncio
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import BOT_TOKEN
from handlers import router
from middlewares import RoleMiddleware
import database as db

async def send_reminders(bot: Bot):
    debtors = await db.get_debtors_to_remind()
    for user in debtors:
        try:
            text = (f"⚠️ <b>Ескертиў!</b>\n"
                    f"Сиздин қарызыңыз бар.\n"
                    f"Сумма: <b>{user['total_debt']} сум</b>.\n"
                    f"Төлеп қойыўыңызды соранамыз.")
            await bot.send_message(user['id'], text, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка при отправке напоминания: {e}")

async def main():
    # Инициализация базы данных
    await db.init_db()
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Подключение middleware и роутера
    dp.message.middleware(RoleMiddleware())
    dp.include_router(router)
    
    # Настройка планировщика (проверка каждый день в 09:00)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, 'cron', hour=9, minute=0, args=(bot,))
    scheduler.start()
    
    print("=== SYSTEM START ===")
    print("Telegram bot runs perfectly...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())