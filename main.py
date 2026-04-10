import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8653242237:AAGp4Zx8ubl80ie1tnCJy1dQDsWP2i8szNw"
SUPPORT_USERNAME = "gffgvvvxzz"
PHOTO_PATH = "horor_vpn_photo.jpg"

# Outline VPN (закомментировано для тестирования)
# from outline_vpn.outline_vpn import OutlineVPN
# OUTLINE_API_URL = "https://127.0.0.1:51083/xlUG4F5BBft4rSrIvDSWuw/"
# OUTLINE_CERT_SHA256 = "4EFF7BB90BCE5D4A172D338DC91B5B9975E197E39E3FA4FC42353763C4E58765"

# Цены в рублях за дни
PRICES = {"10": 20, "20": 45, "30": 60}

# База данных пользователей
user_balances = {}  # {user_id: {"expire_date": date, "key_id": str, "rub": int}}

REFERRAL_RUB = 10

# ========== ТЕСТОВЫЙ РЕЖИМ (без реального Outline) ==========
async def create_outline_key(user_id, days):
    """Тестовая функция - создает фейковый ключ"""
    return f"ss://test://user_{user_id}_{datetime.now().timestamp()}@horor-vpn.com"

async def delete_outline_key(key_id):
    """Тестовая функция"""
    return True

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== КЛАВИАТУРЫ ==========
def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Меню", callback_data="menu")],
        [InlineKeyboardButton(text="🎁 Рефералка", callback_data="referral")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")]
    ])

def kb_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="💳 Пополнить", callback_data="topup")],
        [InlineKeyboardButton(text="🔑 Получить ключ", callback_data="get_key")],
        [InlineKeyboardButton(text="🔄 Заменить ключ", callback_data="replace_key")],
        [InlineKeyboardButton(text="🗑 Удалить ключ", callback_data="delete_key")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])

def kb_back():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="back")]])

def kb_topup():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="10 дней - 20 ₽", callback_data="topup_10")],
        [InlineKeyboardButton(text="20 дней - 45 ₽", callback_data="topup_20")],
        [InlineKeyboardButton(text="30 дней - 60 ₽", callback_data="topup_30")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])

def kb_confirm_delete():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Да, удалить", callback_data="confirm_delete")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_expire_date(days):
    return datetime.now().date() + timedelta(days=days)

def get_balance_days(user_id):
    if user_id not in user_balances or user_balances[user_id].get("expire_date") is None:
        return 0
    delta = (user_balances[user_id]["expire_date"] - datetime.now().date()).days
    return max(delta, 0)

# ========== ОБРАБОТЧИКИ ==========
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    
    # Реферальная логика
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].split("_")[1])
            if referrer_id != user_id and referrer_id not in user_balances.get(user_id, {}):
                if referrer_id in user_balances:
                    user_balances[referrer_id]["rub"] = user_balances[referrer_id].get("rub", 0) + REFERRAL_RUB
                    try:
                        await bot.send_message(referrer_id, f"🎉 +{REFERRAL_RUB} ₽ за приглашение!")
                    except:
                        pass
        except:
            pass
    
    # Новый пользователь
    if user_id not in user_balances:
        user_balances[user_id] = {
            "expire_date": get_expire_date(7),
            "key_id": None,
            "rub": 0
        }
    
    text = "🌟 Добро пожаловать в Horor VPN!\n🚀 Высокая скорость\n💰 Низкие цены\n👇 Выберите действие"
    try:
        await message.answer_photo(photo=FSInputFile(PHOTO_PATH), caption=text, reply_markup=kb_main())
    except:
        await message.answer(text, reply_markup=kb_main())

@dp.callback_query(F.data == "menu")
async def menu(callback: types.CallbackQuery):
    await callback.message.edit_text("📋 Меню:", reply_markup=kb_menu())
    await callback.answer()

@dp.callback_query(F.data == "back")
async def back(callback: types.CallbackQuery):
    await callback.message.edit_text("🌟 Главное меню:", reply_markup=kb_main())
    await callback.answer()

@dp.callback_query(F.data == "referral")
async def referral(callback: types.CallbackQuery):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{callback.from_user.id}"
    await callback.message.edit_text(
        f"🎁 Реферальная ссылка:\n<code>{ref_link}</code>\n+{REFERRAL_RUB}₽ за друга",
        parse_mode="HTML", reply_markup=kb_back()
    )
    await callback.answer()

@dp.callback_query(F.data == "support")
async def support(callback: types.CallbackQuery):
    await callback.message.edit_text(f"🆘 Поддержка: @{SUPPORT_USERNAME}", reply_markup=kb_back())
    await callback.answer()

@dp.callback_query(F.data == "balance")
async def balance(callback: types.CallbackQuery):
    uid = callback.from_user.id
    days = get_balance_days(uid)
    rub = user_balances[uid].get("rub", 0)
    days_text = "❌ Истёк" if days <= 0 else f"✅ {days} дн."
    await callback.message.edit_text(
        f"💰 Баланс:\n💵 Рублей: {rub}₽\n📆 Подписка: {days_text}",
        reply_markup=kb_back()
    )
    await callback.answer()

@dp.callback_query(F.data == "topup")
async def topup(callback: types.CallbackQuery):
    await callback.message.edit_text("💳 Выберите тариф:", reply_markup=kb_topup())
    await callback.answer()

@dp.callback_query(F.data.startswith("topup_"))
async def process_topup(callback: types.CallbackQuery):
    days = int(callback.data.split("_")[1])
    amount = PRICES[str(days)]
    uid = callback.from_user.id
    
    if user_balances[uid].get("rub", 0) >= amount:
        user_balances[uid]["rub"] -= amount
        new_date = max(user_balances[uid].get("expire_date", datetime.now().date()), datetime.now().date()) + timedelta(days=days)
        user_balances[uid]["expire_date"] = new_date
        await callback.message.edit_text(
            f"✅ Оплачено! Подписка до {new_date.strftime('%d.%m.%Y')}",
            reply_markup=kb_back()
        )
    else:
        need = amount - user_balances[uid].get("rub", 0)
        await callback.message.edit_text(
            f"⚠️ Не хватает {need}₽\n\n💳 Реквизиты: +7 XXX XXX XX-XX",
            reply_markup=kb_back()
        )
    await callback.answer()

@dp.callback_query(F.data == "get_key")
async def get_key(callback: types.CallbackQuery):
    uid = callback.from_user.id
    days = get_balance_days(uid)
    
    if days <= 0:
        await callback.message.edit_text("❌ Нет активной подписки", reply_markup=kb_back())
        await callback.answer()
        return
    
    # Если ключ уже есть - показываем его
    if user_balances[uid].get("key_id"):
        await callback.message.edit_text(
            f"🔑 Ваш активный ключ:\n<code>ss://...{uid}</code>\n📅 Действует {days} дн.",
            parse_mode="HTML", reply_markup=kb_back()
        )
        await callback.answer()
        return
    
    # Создаём новый ключ
    await callback.message.edit_text("🔄 Создаём ключ...")
    
    access_url = await create_outline_key(uid, days)
    
    if access_url:
        user_balances[uid]["key_id"] = f"key_{uid}"
        await callback.message.edit_text(
            f"✅ VPN ключ создан!\n\n🔑 <code>{access_url}</code>\n\n📅 Действует {days} дн.\n⚠️ Ключ персональный",
            parse_mode="HTML", reply_markup=kb_back()
        )
    else:
        await callback.message.edit_text("❌ Ошибка создания ключа", reply_markup=kb_back())
    
    await callback.answer()

@dp.callback_query(F.data == "replace_key")
async def replace_key(callback: types.CallbackQuery):
    uid = callback.from_user.id
    days = get_balance_days(uid)
    
    if days <= 0:
        await callback.message.edit_text("❌ Нет активной подписки", reply_markup=kb_back())
        await callback.answer()
        return
    
    # Удаляем старый ключ
    if user_balances[uid].get("key_id"):
        await delete_outline_key(user_balances[uid]["key_id"])
        user_balances[uid]["key_id"] = None
    
    # Создаём новый
    await callback.message.edit_text("🔄 Создаём новый ключ...")
    
    access_url = await create_outline_key(uid, days)
    
    if access_url:
        user_balances[uid]["key_id"] = f"key_{uid}_{int(datetime.now().timestamp())}"
        await callback.message.edit_text(
            f"🔄 Новый ключ:\n<code>{access_url}</code>",
            parse_mode="HTML", reply_markup=kb_back()
        )
    else:
        await callback.message.edit_text("❌ Ошибка", reply_markup=kb_back())
    
    await callback.answer()

@dp.callback_query(F.data == "delete_key")
async def delete_key_menu(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if not user_balances[uid].get("key_id"):
        await callback.message.edit_text("❌ Нет активного ключа", reply_markup=kb_back())
    else:
        await callback.message.edit_text(
            "⚠️ Удалить ключ? VPN перестанет работать.",
            reply_markup=kb_confirm_delete()
        )
    await callback.answer()

@dp.callback_query(F.data == "confirm_delete")
async def confirm_delete(callback: types.CallbackQuery):
    uid = callback.from_user.id
    key_id = user_balances[uid].get("key_id")
    if key_id:
        await delete_outline_key(key_id)
        user_balances[uid]["key_id"] = None
    await callback.message.edit_text("✅ Ключ удалён", reply_markup=kb_back())
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот Horor VPN запущен!")
    print("📌 Режим: ТЕСТОВЫЙ (без реального Outline)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())