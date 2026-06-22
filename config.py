import os
import secrets

BOT_TOKEN = "8903142933:AAEHtd2rd8eTEk5ULzaIgOAwoZ34MbC3ftg"
ADMIN_IDS = [8766579960, 8487320282]
MAIN_ADMIN_ID = ADMIN_IDS[0]

# Исправлено имя переменной file (было file) для корректного поиска базы данных
DB_PATH = os.path.join(os.path.dirname(__file__), "debts_kaa.db")
SECRET_KEY = secrets.token_hex(24)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# Твой новый адрес от Railway вместо ngrok
RAILWAY_URL = "thelast125-production.up.railway.app"

# Web App URL теперь будет вести на твой сайт на Railway (в меню статистики)
WEB_APP_URL = f"{RAILWAY_URL}/stats"
