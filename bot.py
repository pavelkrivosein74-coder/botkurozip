import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
import aiosqlite

# ----------------- НАСТРОЙКИ -----------------
BOT_TOKEN = "8879121545:AAEp55PEK5hqQmPcfwjyl4z7kHg-1VSSJLM"
ADMIN_ID = 1109966636  # Ваш Telegram ID (число)
CHANNEL_URL = "https://t.me/+3Z9Cu377VGxhZjky"  # Ссылка на ваш канал
MANAGER_USERNAME = "pashocc1337"  # Ваш юзернейм без @

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# ----------------- БАЗА ДАННЫХ -----------------
DB_NAME = "shop.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL,
                photo_id TEXT NOT NULL
            )
        """)
        await db.commit()

# ----------------- FSM (СОСТОЯНИЯ) -----------------
class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    stock = State()
    photo = State()

# ----------------- КЛАВИАТУРЫ -----------------
def get_main_kb(user_id: int):
    buttons = [
        [InlineKeyboardButton(text="🛍️ Каталог товаров", callback_data="catalog")],
        [InlineKeyboardButton(text="📢 Наш канал", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="👨‍💼 Связаться с менеджером", url=f"https://t.me/{MANAGER_USERNAME}")],
    ]
    if user_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="add_product")],
        [InlineKeyboardButton(text="🗑️ Удалить товар", callback_data="delete_product_list")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])

# ----------------- ХЕНДЛЕРЫ -----------------
@router.message(CommandStart())
async def cmd_start(message: Message):
    text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "✨ Добро пожаловать в наш онлайн-магазин!\n"
        "💎 Здесь вы можете ознакомиться с ассортиментом и оформить заказ."
    )
    await message.answer(text, reply_markup=get_main_kb(message.from_user.id))

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery):
    text = (
        "✨ Главное меню\n\n"
        "👇 Выберите нужный раздел ниже:"
    )
    await call.message.edit_text(text, reply_markup=get_main_kb(call.from_user.id))

# --- КАТАЛОГ ---
@router.callback_query(F.data == "catalog")
async def show_catalog(call: CallbackQuery):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, name, price, stock FROM products") as cursor:
            products = await cursor.fetchall()

    if not products:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]])
        await call.message.edit_text("📦 К сожалению, каталог сейчас пуст 😔", reply_markup=kb)
        return

    buttons = []
    for p_id, name, price, stock in products:
        status = "✅ В наличии" if stock > 0 else "❌ Нет в наличии"
        buttons.append([InlineKeyboardButton(
            text=f"🏷️ {name} | 💰 {price} ₽ | {status}", 
            callback_data=f"prod_{p_id}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])

    await call.message.edit_text("🛍️ *Наш каталог товаров:*", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@router.callback_query(F.data.startswith("prod_"))
async def show_product(call: CallbackQuery):
    prod_id = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT name, description, price, stock, photo_id FROM products WHERE id = ?", (prod_id,)) as cursor:
            product = await cursor.fetchone()

    if not product:
        await call.answer("❌ Товар не найден!", show_alert=True)
        return

    name, desc, price, stock, photo_id = product
    status_text = f"📦 В наличии: {stock} шт. 🔥" if stock > 0 else "❌ Нет в наличии 😔"

    caption = (
        f"🏷️ *{name}*\n\n"
        f"📝 *Описание:*\n{desc}\n\n"
        f"💵 *Цена:* {price} ₽ 💸\n"
        f"📊 *Статус:* {status_text}\n"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Заказать у менеджера", url=f"https://t.me/{MANAGER_USERNAME}")],
        [InlineKeyboardButton(text="🔙 Назад в каталог", callback_data="catalog")]
    ])

    await call.message.delete()
    await call.message.answer_photo(photo=photo_id, caption=caption, reply_markup=kb, parse_mode="Markdown")

# --- АДМИН ПАНЕЛЬ И ДОБАВЛЕНИЕ ---
@router.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    await call.message.edit_text("⚙️ *Панель администратора:*", reply_markup=get_admin_kb(), parse_mode="Markdown")

@router.callback_query(F.data == "add_product")
async def add_prod_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddProduct.name)
    await call.message.answer("🏷️ Введите название товара:")

@router.message(AddProduct.name)
async def add_prod_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProduct.description)
    await message.answer("📝 Введите описание товара:")

@router.message(AddProduct.description)
async def add_prod_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddProduct.price)
    await message.answer("💰 Введите цену товара (число):")

@router.message(AddProduct.price)
async def add_prod_price(message: Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price=price)
        await state.set_state(AddProduct.stock)
        await message.answer("📊 Введите количество товара на складе (число):")
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректную цену (число):")

@router.message(AddProduct.stock)
async def add_prod_stock(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Введите целое число для количества:")
        return
    await state.update_data(stock=int(message.text))
    await state.set_state(AddProduct.photo)
    await message.answer("🖼️ Отправьте фотографию товара:")

@router.message(AddProduct.photo, F.photo)
async def add_prod_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO products (name, description, price, stock, photo_id) VALUES (?, ?, ?, ?, ?)",
            (data['name'], data['description'], data['price'], data['stock'], photo_id)
        )
        await db.commit()

    await state.clear()
    await message.answer("✅ Товар успешно добавлен в каталог! 🎉", reply_markup=get_admin_kb())

# --- УДАЛЕНИЕ ТОВАРА ---
@router.callback_query(F.data == "delete_product_list")
async def delete_list(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, name FROM products") as cursor:
            products = await cursor.fetchall()

    if not products:
        await call.answer("❌ Нет товаров для удаления", show_alert=True)
        return

    buttons = []
    for p_id, name in products:
        buttons.append([InlineKeyboardButton(text=f"🗑️ Удалить: {name}", callback_data=f"del_{p_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])

    await call.message.edit_text("🗑️ Выберите товар для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("del_"))
async def delete_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    prod_id = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM products WHERE id = ?", (prod_id,))
        await db.commit()
    await call.answer("🗑️ Товар удален!", show_alert=True)
    await delete_list(call)

# ----------------- ЗАПУСК -----------------
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
