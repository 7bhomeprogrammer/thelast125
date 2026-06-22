import aiosqlite
import sqlite3

from config import DB_PATH, ADMIN_IDS
from datetime import datetime, timedelta


def get_admin_exclusion_clause():
    if not ADMIN_IDS:
        return "", []
    placeholders = ",".join("?" for _ in ADMIN_IDS)
    return f" AND id NOT IN ({placeholders})", ADMIN_IDS

def is_real_username(username) -> bool:
    return bool(username) and username not in ('NoUsername', 'user')

def is_placeholder_name(name) -> bool:
    if not name:
        return True
    return name.startswith('Клиент_') or name.startswith('Админ_') or name.startswith('User_')

def get_client_display_name(user: dict) -> str:
    username = user.get('username') or ''
    if is_real_username(username):
        return f"@{username}"
    full_name = user.get('full_name') or ''
    if full_name and not is_placeholder_name(full_name):
        return full_name
    return f"@{username}" if username else f"ID {user['id']}"

def needs_profile_refresh(user: dict) -> bool:
    return not is_real_username(user.get('username')) or is_placeholder_name(user.get('full_name'))

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS Users (id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, total_debt REAL DEFAULT 0.0, language TEXT DEFAULT 'kaa')''')
        await db.execute('''CREATE TABLE IF NOT EXISTS Invoices (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, photo_id TEXT, comment TEXT, date TEXT, deadline_date TEXT, payment_type TEXT DEFAULT 'Товар', FOREIGN KEY(user_id) REFERENCES Users(id))''')
        await db.execute('''CREATE TABLE IF NOT EXISTS StoreSellers (id INTEGER PRIMARY KEY, full_name TEXT)''')
        await db.commit()

async def get_user_by_id(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM Users WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def upsert_user(user_id: int, username: str, full_name: str):
    username = username or "NoUsername"
    full_name = full_name or ""
    existing = await get_user_by_id(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        if not existing:
            await db.execute(
                "INSERT INTO Users (id, username, full_name) VALUES (?, ?, ?)",
                (user_id, username, full_name)
            )
        else:
            new_username = username if is_real_username(username) else existing['username']
            if is_placeholder_name(existing['full_name']):
                new_full_name = full_name if full_name and not is_placeholder_name(full_name) else existing['full_name']
            elif full_name and not is_placeholder_name(full_name):
                new_full_name = full_name
            else:
                new_full_name = existing['full_name']
            await db.execute(
                "UPDATE Users SET username = ?, full_name = ? WHERE id = ?",
                (new_username, new_full_name, user_id)
            )
        await db.commit()

async def set_user_lang(user_id: int, lang: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE Users SET language = ? WHERE id = ?", (lang, user_id))
        await db.commit()

async def add_debt_to_db(user_id: int, amount: float, photo_id: str, comment: str, date_str: str, days: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO Invoices (user_id, amount, photo_id, comment, date, deadline_date, payment_type) VALUES (?, ?, ?, ?, ?, datetime(?, '+' || ? || ' days'), 'Товар')",
            (user_id, amount, photo_id, comment, date_str, date_str, days)
        )
        await db.execute("UPDATE Users SET total_debt = total_debt + ? WHERE id = ?", (amount, user_id))
        await db.commit()

async def get_active_debts(user_id: int):
    """Получить все активные долги пользователя (только тип 'Товар')"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM Invoices WHERE user_id = ? AND payment_type = 'Товар' ORDER BY date DESC", 
            (user_id,)
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def reduce_debt_in_db(user_id: int, amount: float, payment_type: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO Invoices (user_id, amount, photo_id, comment, date, payment_type) VALUES (?, ?, NULL, ?, ?, ?)",
            (user_id, amount, f"Қарз төленди ({payment_type})", now, payment_type)
        )
        await db.execute("UPDATE Users SET total_debt = MAX(0, total_debt - ?) WHERE id = ?", (amount, user_id))
        await db.commit()

async def get_invoices_by_period(user_id: int, months: int):
    cutoff_date = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM Invoices WHERE user_id = ? AND date >= ? ORDER BY date DESC", 
            (user_id, cutoff_date)
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def get_debtors_to_remind():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        ten_days_ago = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        query = '''
            SELECT DISTINCT u.id, u.total_debt 
            FROM Users u
            JOIN Invoices i ON u.id = i.user_id
            WHERE u.total_debt > 0 AND i.date <= ?
        '''
        async with db.execute(query, (ten_days_ago,)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def add_seller_to_db(user_id: int, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO StoreSellers (id, full_name) VALUES (?, ?)", (user_id, full_name))
        await db.commit()

async def remove_seller_from_db(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM StoreSellers WHERE id = ?", (user_id,))
        await db.commit()

async def get_all_sellers():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM StoreSellers") as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def is_user_seller(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM StoreSellers WHERE id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

async def search_users_by_name(name: str, only_with_debt: bool = True):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        search = f"%{name}%"
        admin_clause, admin_params = get_admin_exclusion_clause()
        query = (
            "SELECT * FROM Users WHERE (full_name LIKE ? OR username LIKE ?)" + admin_clause +
            " AND id NOT IN (SELECT id FROM StoreSellers)"
        )
        params = [search, search] + admin_params
        if only_with_debt:
            query += " AND total_debt > 0"
        query += " ORDER BY username, full_name"
        async with db.execute(query, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def get_zero_debt_clients():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        admin_clause, admin_params = get_admin_exclusion_clause()
        query = (
            "SELECT * FROM Users WHERE total_debt <= 0" + admin_clause +
            " AND id NOT IN (SELECT id FROM StoreSellers) ORDER BY username, full_name"
        )
        async with db.execute(query, params=admin_params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

async def delete_client_from_db(user_id: int):
    if user_id in ADMIN_IDS:
        return False, "cannot_delete_admin"
    if await is_user_seller(user_id):
        return False, "cannot_delete_seller"
    user = await get_user_by_id(user_id)
    if not user:
        return False, "client_not_found"
    if user['total_debt'] > 0:
        return False, "has_debt"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM Invoices WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM Users WHERE id = ?", (user_id,))
        await db.commit()
    return True, "deleted"

async def update_user_name(user_id: int, full_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE Users SET full_name = ? WHERE id = ?", (full_name, user_id))
        await db.commit()

async def delete_all_zero_debt_clients():
    clients = await get_zero_debt_clients()
    deleted = 0
    for client in clients:
        ok, _ = await delete_client_from_db(client['id'])
        if ok:
            deleted += 1
    return deleted

def get_all_invoices_sync():
    import sqlite3
    from config import DB_PATH
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Invoices ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_users_sync():
    import sqlite3
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Users")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]