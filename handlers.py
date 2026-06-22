from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    KeyboardButtonRequestUser, WebAppInfo
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import database as db
from config import MAIN_ADMIN_ID, WEB_APP_URL, is_admin
from lexicon import MESSAGES
from datetime import datetime

router = Router()
ITEMS_PER_PAGE = 10 

class DebtStates(StatesGroup):
    SearchName = State()
    ClientMenu = State()
    RenameClient = State()
    AddDebtPhoto = State()
    AddDebtComment = State()
    AddDebtAmount = State()
    AddDebtDeadline = State()
    AddDebtDate = State()
    PayDebtAmount = State()
    PayDebtType = State()
    DeleteSeller = State()

async def get_txt(user_id: int, key: str, *args):
    user = await db.get_user_by_id(user_id)
    lang = user['language'] if user and user['language'] else 'kaa'
    text = MESSAGES.get(lang, MESSAGES['kaa']).get(key, "")
    return text.format(*args) if args else text

async def refresh_user_from_telegram(bot: Bot, user_id: int):
    user = await db.get_user_by_id(user_id)
    if user and not db.needs_profile_refresh(user):
        return user
    try:
        chat = await bot.get_chat(user_id)
        await db.upsert_user(
            user_id,
            chat.username or "NoUsername",
            chat.full_name or chat.first_name or ""
        )
    except Exception:
        pass
    return await db.get_user_by_id(user_id)

async def refresh_users_list(bot: Bot, users: list):
    refreshed = []
    for user in users:
        if db.needs_profile_refresh(user):
            user = await refresh_user_from_telegram(bot, user['id']) or user
        refreshed.append(user)
    return refreshed

def get_main_menu(user_id, is_seller=False):
    if is_admin(user_id):
        return ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="👥 Клиентлер"), KeyboardButton(text="📇 Контакт арқалы сайлаў", request_user=KeyboardButtonRequestUser(request_id=2, user_is_bot=False))],
            [KeyboardButton(text="📊 Статистика (Mini App)", web_app=WebAppInfo(url=WEB_APP_URL))],
            [KeyboardButton(text="⚙️ Сазламалар"), KeyboardButton(text="🌐 Тилди өзгертиў / Язык")]
        ], resize_keyboard=True)
    elif is_seller:
        return ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="👥 Клиентлер"), KeyboardButton(text="📇 Контакт арқалы сайлаў", request_user=KeyboardButtonRequestUser(request_id=2, user_is_bot=False))],
            [KeyboardButton(text="📊 Статистика (Mini App)", web_app=WebAppInfo(url=WEB_APP_URL))]
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="💰 Мениң қарзым"), KeyboardButton(text="🧾 Накладнойлар")],
            [KeyboardButton(text="🌐 Тилди өзгертиў / Язык")]
        ], resize_keyboard=True)

def get_settings_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Сатыушы (Админ) қосыў", request_user=KeyboardButtonRequestUser(request_id=1, user_is_bot=False))],
        [KeyboardButton(text="❌ Сатыушыны (Админ) өшириў")],
        [KeyboardButton(text="🗑 Қарзы жоқ клиентлер")],
        [KeyboardButton(text="⬅️ Бас менюге қайтыў")]
    ], resize_keyboard=True)

def get_client_menu_keyboard(client: dict, viewer_id: int):
    buttons = [
        [KeyboardButton(text="🛍 Товар бериў"), KeyboardButton(text="💰 Қарзын қайтарыў")],
        [KeyboardButton(text="📊 Қарз тарыхын көриў")],
    ]
    if is_admin(viewer_id):
        buttons.insert(0, [KeyboardButton(text="📝 Атын озгертү")])
        if client['total_debt'] <= 0:
            buttons.append([KeyboardButton(text="🗑 Клиентти өшириў")])
    buttons.append([KeyboardButton(text="⬅️ Бас менюге қайтыў")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Қарақалпақша", callback_data="setlang_kaa")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru")]
    ])

async def get_clients_pagination_keyboard(page: int = 1, search_query: str = None, bot: Bot = None):
    if search_query:
        users = await db.search_users_by_name(search_query)
    else:
        users = await db.search_users_by_name("")
    
    if bot:
        users = await refresh_users_list(bot, users)
    
    if not users:
        return None, 0

    total_pages = (len(users) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_users = users[start_idx:end_idx]

    inline_kbd = []
    for u in page_users:
        display_name = db.get_client_display_name(u)
        inline_kbd.append([InlineKeyboardButton(text=f"{display_name} ({u['total_debt']} сум)", callback_data=f"cli_{u['id']}")])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"clipage_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"clipage_{page+1}"))
    
    if nav_buttons:
        inline_kbd.append(nav_buttons)
        
    return InlineKeyboardMarkup(inline_keyboard=inline_kbd), total_pages

@router.message(F.text == "⬅️ Бас менюге қайтыў")
async def cancel_to_main_menu(message: Message, state: FSMContext):
    await state.clear()
    is_seller = await db.is_user_seller(message.from_user.id)
    await message.answer(await get_txt(message.from_user.id, 'main_menu'), reply_markup=get_main_menu(message.from_user.id, is_seller))

@router.message(CommandStart())
async def cmd_start(message: Message):
    is_seller = await db.is_user_seller(message.from_user.id)
    await message.answer(await get_txt(message.from_user.id, 'welcome'), reply_markup=get_main_menu(message.from_user.id, is_seller))

@router.message(F.text == "🌐 Тилди өзгертиў / Язык")
async def show_lang_selection(message: Message):
    await message.answer("Тилди сайлаң / Выберите язык:", reply_markup=get_lang_keyboard())

@router.message(DebtStates.AddDebtAmount)
async def ask_deadline(message: Message, state: FSMContext):
    if not message.text.replace(" ", "").isdigit():
        await message.answer("Тек сан киргизиң!")
        return
    await state.update_data(amount=float(message.text.replace(" ", "")))
    await message.answer("Төлеў мүддетин киргизиң (неше күннен кейин ескертиў керек?) ямаса 'Өткізиў' басыңыз:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Өткізиў")], [KeyboardButton(text="⬅️ Бас менюге қайтыў")]], resize_keyboard=True))
    await state.set_state(DebtStates.AddDebtDeadline)

@router.message(DebtStates.AddDebtDeadline)
async def save_debt_with_deadline(message: Message, state: FSMContext):
    days = 0
    if message.text == "Өткізиў":
        days = 0
    elif not message.text.isdigit():
        await message.answer("Сан киргизиң ямаса 'Өткізиў' басыңыз!")
        return
    else:
        days = int(message.text)
    
    data = await state.get_data()
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    await db.add_debt_to_db(data['target_user_id'], data['amount'], data['photo_id'], data['comment'], today, days)
    
    await message.answer("✅ Қарз сақланды!")
    await state.clear()

@router.callback_query(F.data.startswith("setlang_"))
async def change_lang_callback(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    await db.set_user_lang(callback.from_user.id, lang)
    is_seller = await db.is_user_seller(callback.from_user.id)
    msg_key = 'lang_changed'
    text = MESSAGES[lang][msg_key]
    await callback.message.answer(text, reply_markup=get_main_menu(callback.from_user.id, is_seller))
    await callback.answer()

@router.message(F.text == "⚙️ Сазламалар")
async def admin_settings_panel(message: Message):
    if not is_admin(message.from_user.id): return
    await message.answer(await get_txt(message.from_user.id, 'settings_title'), reply_markup=get_settings_keyboard(), parse_mode="HTML")

@router.message(F.user_shared & (F.user_shared.request_id == 1))
async def add_new_seller_handler(message: Message):
    if not is_admin(message.from_user.id): return
    seller_id = message.user_shared.user_id
    user_info = await db.get_user_by_id(seller_id)
    name = user_info['full_name'] if user_info else f"Админ_{seller_id}"
    await db.add_seller_to_db(seller_id, name)
    await message.answer(f"✅ Жаңа Сатыушы (Админ) табыслы қосылды!\n👤 Аты: {name}\n🆔 ID: <code>{seller_id}</code>", parse_mode="HTML")

@router.message(F.text == "❌ Сатыушыны (Админ) өшириў")
async def start_remove_seller(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    sellers = await db.get_all_sellers()
    if not sellers:
        await message.answer("Ҳәзирше ҳеш қандай қосымша adminler жоқ.")
        return
    kbd = []
    for s in sellers:
        kbd.append([InlineKeyboardButton(text=f"❌ {s['full_name']}", callback_data=f"delseller_{s['id']}")])
    await message.answer("Өширип тасламақшы болған админди сайлаң:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kbd))

@router.callback_query(F.data.startswith("delseller_"))
async def process_delete_seller(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    seller_id = int(callback.data.split("_")[1])
    await db.remove_seller_from_db(seller_id)
    await callback.message.answer("🗑 Админлик ҳуқықы табыслы алып тасланды!")
    await callback.answer()

@router.message(F.text == "🗑 Қарзы жоқ клиентлер")
async def start_cleanup_zero_debt_clients(message: Message, bot: Bot):
    if not is_admin(message.from_user.id): return
    clients = await db.get_zero_debt_clients()
    clients = await refresh_users_list(bot, clients)
    if not clients:
        await message.answer(await get_txt(message.from_user.id, 'zero_debt_clients_empty'))
        return
    kbd = [[InlineKeyboardButton(text=f"❌ {db.get_client_display_name(c)}", callback_data=f"delclient_{c['id']}")] for c in clients]
    kbd.append([InlineKeyboardButton(text="🗑 Ҳаммині өшириў", callback_data="delclient_all")])
    await message.answer(
        await get_txt(message.from_user.id, 'zero_debt_clients_title', len(clients)),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kbd)
    )

@router.message(F.text == "📝 Атын озгертү", DebtStates.ClientMenu)
async def start_rename_client(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    client_id = data.get('target_user_id')
    if not client_id:
        await message.answer("Клиент толығымен талымы жок.")
        return
    await state.set_state(DebtStates.RenameClient)
    await message.answer("Жаңа атын жазып җібериң:")

@router.message(DebtStates.RenameClient)
async def save_renamed_client(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Атын жазып җібериң:")
        return
    data = await state.get_data()
    client_id = data.get('target_user_id')
    if not client_id:
        await message.answer("Клиент талымы жоқ.")
        await state.clear()
        return
    await db.update_user_name(client_id, new_name)
    await message.answer("✅ Атын сақталды!")
    is_seller = await db.is_user_seller(message.from_user.id)
    await message.answer(await get_txt(message.from_user.id, 'main_menu'), reply_markup=get_main_menu(message.from_user.id, is_seller))
    await state.clear()

@router.message(F.text == "🗑 Клиентти өшириў", DebtStates.ClientMenu)
async def start_delete_client_from_card(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    client_id = data.get('target_user_id')
    client = await db.get_user_by_id(client_id)
    if not client:
        await message.answer(await get_txt(message.from_user.id, 'delete_client_not_found'))
        return
    if client['total_debt'] > 0:
        await message.answer(await get_txt(message.from_user.id, 'delete_client_has_debt', client['total_debt']))
        return
    display_name = db.get_client_display_name(client)
    await message.answer(
        await get_txt(message.from_user.id, 'delete_client_confirm', display_name),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Иә", callback_data=f"delclient_confirm_{client_id}"),
                InlineKeyboardButton(text="❌ Жоқ", callback_data="delclient_cancel")
            ]
        ]),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("delclient_"))
async def process_delete_client(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return

    if callback.data == "delclient_cancel":
        await callback.message.answer(await get_txt(callback.from_user.id, 'main_menu'), reply_markup=get_main_menu(callback.from_user.id))
        await state.clear()
        await callback.answer()
        return

    if callback.data == "delclient_all":
        clients = await db.get_zero_debt_clients()
        if not clients:
            await callback.message.answer(await get_txt(callback.from_user.id, 'zero_debt_clients_empty'))
            await callback.answer()
            return
        await callback.message.answer(
            await get_txt(callback.from_user.id, 'delete_all_clients_confirm', len(clients)),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Иә", callback_data="delclient_all_confirm"),
                    InlineKeyboardButton(text="❌ Жоқ", callback_data="delclient_cancel")
                ]
            ])
        )
        await callback.answer()
        return

    if callback.data == "delclient_all_confirm":
        deleted = await db.delete_all_zero_debt_clients()
        await callback.message.answer(await get_txt(callback.from_user.id, 'delete_all_clients_success', deleted))
        await state.clear()
        await callback.answer()
        return

    if callback.data.startswith("delclient_confirm_"):
        client_id = int(callback.data.split("_")[2])
    else:
        client_id = int(callback.data.split("_")[1])
        client = await db.get_user_by_id(client_id)
        if not client:
            await callback.message.answer(await get_txt(callback.from_user.id, 'delete_client_not_found'))
            await callback.answer()
            return
        display_name = db.get_client_display_name(client)
        await callback.message.answer(
            await get_txt(callback.from_user.id, 'delete_client_confirm', display_name),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Иә", callback_data=f"delclient_confirm_{client_id}"),
                    InlineKeyboardButton(text="❌ Жоқ", callback_data="delclient_cancel")
                ]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    ok, reason = await db.delete_client_from_db(client_id)
    if ok:
        await callback.message.answer(await get_txt(callback.from_user.id, 'delete_client_success'))
        await state.clear()
    elif reason == "has_debt":
        client = await db.get_user_by_id(client_id)
        debt = client['total_debt'] if client else 0
        await callback.message.answer(await get_txt(callback.from_user.id, 'delete_client_has_debt', debt))
    elif reason == "client_not_found":
        await callback.message.answer(await get_txt(callback.from_user.id, 'delete_client_not_found'))
    else:
        await callback.message.answer(await get_txt(callback.from_user.id, 'delete_client_forbidden'))
    await callback.answer()

@router.message(F.user_shared & (F.user_shared.request_id == 2))
async def contact_select_client(message: Message, state: FSMContext, bot: Bot):
    is_seller = await db.is_user_seller(message.from_user.id)
    if not is_admin(message.from_user.id) and not is_seller: return
    client_id = message.user_shared.user_id
    client = await refresh_user_from_telegram(bot, client_id)
    if not client:
        await db.upsert_user(client_id, "NoUsername", "")
        client = await refresh_user_from_telegram(bot, client_id)
    display_name = db.get_client_display_name(client)
    await state.update_data(target_user_id=client_id, target_user_name=display_name)
    txt = await get_txt(message.from_user.id, 'client_card', display_name, client['total_debt'])
    await message.answer(txt, reply_markup=get_client_menu_keyboard(client, message.from_user.id), parse_mode="HTML")
    await state.set_state(DebtStates.ClientMenu)

@router.message(F.text == "👥 Клиентлер")
async def start_search(message: Message, state: FSMContext, bot: Bot):
    is_seller = await db.is_user_seller(message.from_user.id)
    if not is_admin(message.from_user.id) and not is_seller: return
    await state.set_state(DebtStates.SearchName)
    await state.update_data(current_page=1, current_search="")
    inline_markup, total_pages = await get_clients_pagination_keyboard(page=1, bot=bot)
    if not inline_markup:
        await message.answer(await get_txt(message.from_user.id, 'no_active_clients'), reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Бас менюге қайтыў")]], resize_keyboard=True))
        return
    search_txt = await get_txt(message.from_user.id, 'search_client')
    await message.answer(f"{search_txt}\n\n📖 Страница: 1/{total_pages}", reply_markup=inline_markup)
    await message.answer("Текст арқалы излеў ушын атын жазың ямаса төмендеги дизимнен сайлаң:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Бас менюге қайтыў")]], resize_keyboard=True))

@router.callback_query(F.data.startswith("clipage_"), DebtStates.SearchName)
async def process_client_page(callback: CallbackQuery, state: FSMContext, bot: Bot):
    page = int(callback.data.split("_")[1])
    data = await state.get_data()
    search_query = data.get("current_search", "")
    await state.update_data(current_page=page)
    inline_markup, total_pages = await get_clients_pagination_keyboard(page=page, search_query=search_query, bot=bot)
    if inline_markup:
        await callback.message.edit_text(f"Клиентлер дизими:\n\n📖 Страница: {page}/{total_pages}", reply_markup=inline_markup)
    await callback.answer()

@router.message(DebtStates.SearchName)
async def process_search_name(message: Message, state: FSMContext, bot: Bot):
    search_text = message.text.strip().lstrip('@')
    if search_text == "⬅️ Бас менюге қайтыў":
        await state.clear()
        return
    await state.update_data(current_page=1, current_search=search_text)
    inline_markup, total_pages = await get_clients_pagination_keyboard(page=1, search_query=search_text, bot=bot)
    if not inline_markup:
        await message.answer(await get_txt(message.from_user.id, 'client_not_found'))
        return
    await message.answer(f"Табылған клиентлер (Результаты поиска):\n\n📖 Страница: 1/{total_pages}", reply_markup=inline_markup)

@router.callback_query(F.data.startswith("cli_"), DebtStates.SearchName)
async def select_client_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    client_id = int(callback.data.split("_")[1])
    client = await refresh_user_from_telegram(bot, client_id)
    display_name = db.get_client_display_name(client)
    await state.update_data(target_user_id=client_id, target_user_name=display_name)
    txt = await get_txt(callback.from_user.id, 'client_card', display_name, client['total_debt'])
    await callback.message.answer(txt, reply_markup=get_client_menu_keyboard(client, callback.from_user.id), parse_mode="HTML")
    await state.set_state(DebtStates.ClientMenu)
    await callback.answer()

@router.message(F.text == "📊 Қарз тарыхын көриў", DebtStates.ClientMenu)
async def admin_see_history(message: Message):
    await message.answer("Дәўирди сайлаң:", reply_markup=ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📅 1 айлық"), KeyboardButton(text="📅 3 айлық")],
        [KeyboardButton(text="📅 6 айлық"), KeyboardButton(text="📅 12 айлық")],
        [KeyboardButton(text="⬅️ Бас менюге қайтыў")]
    ], resize_keyboard=True))

@router.message(F.text.in_(["📅 1 айлық", "📅 3 айлық", "📅 6 айлық", "📅 12 айлық"]), DebtStates.ClientMenu)
async def admin_show_period_debt(message: Message, state: FSMContext):
    months = 1
    if "3" in message.text: months = 3
    elif "6" in message.text: months = 6
    elif "12" in message.text: months = 12
    data = await state.get_data()
    invoices = await db.get_invoices_by_period(data['target_user_id'], months)
    if not invoices:
        await message.answer("История бос.")
        return
    for inv in invoices:
        sign = "+" if inv['payment_type'] == 'Товар' else "-"
        text = f"🧾 <b>Накладной №{inv['id']}</b>\n📅 Сене: {inv['date']}\n💰 Сумма: {sign}{inv['amount']} сум\nТип: {inv['payment_type']}\n📝 Коммент: {inv['comment']}"
        if inv['photo_id']:
            await message.answer_photo(photo=inv['photo_id'], caption=text, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🛍 Товар бериў", DebtStates.ClientMenu)
async def start_add_debt_chain(message: Message, state: FSMContext):
    await message.answer("1. Товар сүретин (фото) жибериң:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Бас менюге қайтыў")]], resize_keyboard=True))
    await state.set_state(DebtStates.AddDebtPhoto)

@router.message(F.photo, DebtStates.AddDebtPhoto)
async def chain_photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await message.answer("2. Товар ушын комментарий жазың:")
    await state.set_state(DebtStates.AddDebtComment)

@router.message(DebtStates.AddDebtComment)
async def chain_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await message.answer("3. Товар суммасын киргизиң (тек санларда):")
    await state.set_state(DebtStates.AddDebtAmount)

@router.message(DebtStates.AddDebtDate)
async def chain_final(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    # Бул жерде "target_user_id" ямаса "user_id" деген переменный бар екенине исенимиңиз комил болсын
    user_id = data.get('target_user_id') 
    
    # 1. Қарызды базаға қосамыз
    # Егер date_str - бул менин 2026-06-03 күн болса, оны "today" деп алыўымыз мүмкин
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await db.add_debt_to_db(user_id, data['amount'], data['photo_id'], data['comment'], today, 0)
    
    # 2. Клиентке моментально жибериў
    # "notif_new_debt" текстиңиз lexicon.py файлында бар екенине исенимиңиз комил болсын
    text = await get_txt(user_id, 'notif_new_debt', data['amount'], "...") 
    
    try:
        await bot.send_photo(
            chat_id=user_id,
            photo=data['photo_id'],
            caption=f"{text}\n\n📝 <b>Комментарий:</b> {data['comment']}",
            parse_mode="HTML"
        )
    except Exception as e:
        # Егер бот клиенттиң блогында болса ямаса басқа қәте болса, бул жерде көринеди
        print(f"DEBUG: Клиентке хабарлама жибериў қәтеси -> {e}")

    # 3. Админге жуўап қайтарыў
    await message.answer("✅ Қарыз қосылды ҳәм клиентке хабарланба жиберилди!")
    await state.clear()

@router.message(F.text == "💰 Қарзын қайтарыў", DebtStates.ClientMenu)
async def start_pay_debt_chain(message: Message, state: FSMContext):
    await message.answer("Қайтарылған сумманы киргизиң:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Бас менюге қайтыў")]], resize_keyboard=True))
    await state.set_state(DebtStates.PayDebtAmount)

@router.message(DebtStates.PayDebtAmount)
async def process_pay_amount(message: Message, state: FSMContext):
    if not message.text.replace(" ", "").isdigit():
        await message.answer("Тек сан киргизиң:")
        return
    await state.update_data(pay_amount=float(message.text.replace(" ", "")))
    await message.answer("Төлем түрин сайлаң:", reply_markup=ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="💵 Наличка"), KeyboardButton(text="💳 Карта")],
        [KeyboardButton(text="🏢 Перечисление")],
        [KeyboardButton(text="⬅️ Бас менюге қайтыў")]
    ], resize_keyboard=True))
    await state.set_state(DebtStates.PayDebtType)

@router.message(F.text.in_(["💵 Наличка", "💳 Карта", "🏢 Перечисление"]), DebtStates.PayDebtType)
async def process_pay_type(message: Message, state: FSMContext, bot: Bot):
    if message.text == "⬅️ Бас менюге қайтыў":
        await state.clear()
        is_seller = await db.is_user_seller(message.from_user.id)
        await message.answer(await get_txt(message.from_user.id, 'main_menu'), reply_markup=get_main_menu(message.from_user.id, is_seller))
        return
    p_type = message.text.split()[-1]
    data = await state.get_data()
    user_id = data['target_user_id']
    pay_amount = data['pay_amount']
    await db.reduce_debt_in_db(user_id, pay_amount, p_type)
    client = await db.get_user_by_id(user_id)
    is_seller = await db.is_user_seller(message.from_user.id)
    await message.answer(await get_txt(message.from_user.id, 'debt_reduced_success', client['total_debt']), reply_markup=get_main_menu(message.from_user.id, is_seller))
    try:
        if client['total_debt'] <= 0:
            await bot.send_message(user_id, await get_txt(user_id, 'notif_no_debt'), parse_mode="HTML")
        else:
            await bot.send_message(user_id, await get_txt(user_id, 'notif_still_debt', client['total_debt']), parse_mode="HTML")
    except: pass
    await state.clear()

@router.message(F.text == "💰 Мениң қарзым")
async def client_my_debt(message: Message):
    client = await db.get_user_by_id(message.from_user.id)
    debt = client['total_debt'] if client else 0
    await message.answer(await get_txt(message.from_user.id, 'my_debt', debt), parse_mode="HTML")
    
    # Показать все активные долги с фото и комментом
    debts = await db.get_active_debts(message.from_user.id)
    if not debts:
        await message.answer("Сизиң ҳәзирше ҳеш қандай активті қарзыңыз жоқ.")
        return
    
    await message.answer(f"📊 Сизиң барлық ҳәзирше қарзлар ({len(debts)} шт):")
    for debt in debts:
        text = f"🧾 Накладной №{debt['id']}\n💰 <b>{debt['amount']} сум</b>\n📝 <b>Комментарий:</b> {debt['comment']}\n📅 Сене: {debt['date']}"
        if debt['photo_id']:
            await message.answer_photo(photo=debt['photo_id'], caption=text, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🧾 Накладнойлар")
async def client_periods(message: Message):
    await message.answer(await get_txt(message.from_user.id, 'select_period'), reply_markup=ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📅 1 айлық"), KeyboardButton(text="📅 3 айлық")],
        [KeyboardButton(text="📅 6 айлық"), KeyboardButton(text="📅 12 айлық")],
        [KeyboardButton(text="⬅️ Бас менюге қайтыў")]
    ], resize_keyboard=True))

@router.message(F.text.in_(["📅 1 айлық", "📅 3 айлық", "📅 6 айлық", "📅 12 айлық"]))
async def client_show_invoices(message: Message):
    months = 1
    if "3" in message.text: months = 3
    elif "6" in message.text: months = 6
    elif "12" in message.text: months = 12
    invoices = await db.get_invoices_by_period(message.from_user.id, months)
    if not invoices:
        await message.answer(await get_txt(message.from_user.id, 'no_history'))
        return
    await message.answer(f"📋 Накладнойлар ({len(invoices)} шт):")
    for inv in invoices:
        sign = "+" if inv['payment_type'] == 'Товар' else "-"
        text = f"🧾 Накладной №{inv['id']}\n💰 <b>{sign}{inv['amount']} сум</b>\n📝 <b>Тип:</b> {inv['payment_type']}\n📝 <b>Комментарий:</b> {inv['comment']}\n📅 {inv['date']}"
        if inv['photo_id']:
            await message.answer_photo(photo=inv['photo_id'], caption=text, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML")