import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Временное отключение Outline для тестирования (замените на реальный импорт когда настроите сервер)
# from outline_vpn.outline_vpn import OutlineVPN

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8483157396:AAEnsG9aN8MMLGr5gQm6rDtQcx373d_VREk"  # Ваш токен
SUPPORT_USERNAME = "gffgvvvxzz"  # Username техподдержки

# НАСТРОЙКИ OUTLINE VPN (замените на реальные)
OUTLINE_API_URL = "https://YOUR_SERVER_IP:PORT/TOKEN"
OUTLINE_CERT_SHA256 = "YOUR_CERTIFICATE_SHA256"

# Путь к фото (положите фото в папку с ботом)
PHOTO_PATH = "horor_vpn_photo.jpg"

# Цены в рублях
PRICES = {
    "10": 20,   # 10 дней - 20 руб
    "20": 45,   # 20 дней - 45 руб
    "30": 60    # 30 дней - 60 руб
}

# База данных в памяти
user_balances = {}
user_referrals = {}
referral_counts = {}
user_history = {}

REFERRAL_DAYS = 7
REFERRAL_RUB = 10

# ========== МОК-КЛАСС ДЛЯ OUTLINE (ДЛЯ ТЕСТИРОВАНИЯ) ==========
# Удалите этот класс когда настроите реальный Outline сервер
class MockOutlineManager:
    """Временный класс для тестирования без реального VPN сервера"""
    async def create_key(self, user_id, days_valid, username=None):
        print(f"📝 Создан тестовый ключ для user_{user_id}")
        return {
            "key_id": f"test_key_{user_id}_{int(datetime.now().timestamp())}",
            "access_url": f"ss://test://user_{user_id}@test.server.com",
            "name": username or f"user_{user_id}"
        }
    
    async def delete_key(self, key_id):
        print(f"🗑 Удалён ключ: {key_id}")
        return True
    
    async def get_key_info(self, key_id):
        return {
            "key_id": key_id,
            "name": "test_key",
            "access_url": "ss://test://test.server.com"
        }
    
    async def list_all_keys(self):
        return []

# Используйте мок-класс пока нет реального сервера
outline_manager = MockOutlineManager()
# Раскомментируйте когда настроите реальный сервер:
# from outline_vpn.outline_vpn import OutlineVPN
# outline_manager = OutlineManager(OUTLINE_API_URL, OUTLINE_CERT_SHA256)

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_expire_date(days_from_now=0):
    return datetime.now().date() + timedelta(days=days_from_now)

def get_balance_days(user_id):
    if user_id not in user_balances or user_balances[user_id].get("expire_date") is None:
        return 0
    delta = (user_balances[user_id]["expire_date"] - datetime.now().date()).days
    return max(delta, 0)

def get_rub_balance(user_id):
    if user_id not in user_balances:
        return 0
    return user_balances[user_id].get("rub_balance", 0)

def add_history(user_id, menu_name):
    if user_id not in user_history:
        user_history[user_id] = []
    user_history[user_id].append(menu_name)
    if len(user_history[user_id]) > 10:
        user_history[user_id].pop(0)

def get_previous_menu(user_id):
    if user_id not in user_history or len(user_history[user_id]) <= 1:
        return "main"
    user_history[user_id].pop()
    return user_history[user_id][-1] if user_history[user_id] else "main"

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Меню", callback_data="menu")],
        [InlineKeyboardButton(text="🎁 Реферальная система", callback_data="referral")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")]
    ])
    return keyboard

def get_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="🔑 Получить ключ доступа", callback_data="get_key")],
        [InlineKeyboardButton(text="🔄 Заменить ключ доступа", callback_data="replace_key")],
        [InlineKeyboardButton(text="🗑 Удалить ключ доступа", callback_data="delete_key")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])
    return keyboard

def get_topup_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📆 10 дней - 20 ₽", callback_data="topup_10")],
        [InlineKeyboardButton(text="📆 20 дней - 45 ₽", callback_data="topup_20")],
        [InlineKeyboardButton(text="📆 30 дней - 60 ₽", callback_data="topup_30")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])
    return keyboard

def get_back_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])
    return keyboard

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Реферальная логика
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].split("_")[1])
            if referrer_id != user_id and user_id not in user_referrals:
                user_referrals[user_id] = referrer_id
                referral_counts[referrer_id] = referral_counts.get(referrer_id, 0) + 1
                
                if referrer_id in user_balances:
                    user_balances[referrer_id]["rub_balance"] = user_balances[referrer_id].get("rub_balance", 0) + REFERRAL_RUB
                else:
                    user_balances[referrer_id] = {
                        "expire_date": None,
                        "key_id": None,
                        "rub_balance": REFERRAL_RUB
                    }
                
                try:
                    await bot.send_message(referrer_id, f"🎉 По вашей ссылке присоединился новый пользователь! Вы получили +{REFERRAL_RUB} ₽ на баланс.")
                except:
                    pass
        except:
            pass
    
    # Создаем пользователя
    if user_id not in user_balances:
        user_balances[user_id] = {
            "expire_date": get_expire_date(7),
            "key_id": None,
            "rub_balance": 0
        }
    
    add_history(user_id, "main")
    
    welcome_text = (
        "🌟 <b>Добро пожаловать в Horor VPN!</b> 🌟\n\n"
        "🚀 Высокая скорость\n"
        "📶 Без ограничений по трафику\n"
        "💰 Низкие цены\n"
        "🖱 Настройка в несколько кликов\n"
        "🎁 Вознаграждение за приглашение друзей\n"
        "👩‍💻 Оперативная онлайн поддержка\n\n"
        "👇 Выберите действие ниже 👇"
    )
    
    try:
        photo = FSInputFile(PHOTO_PATH)
        await message.answer_photo(
            photo=photo,
            caption=welcome_text,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except:
        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )

@dp.callback_query(F.data == "back")
async def back_button(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    previous_menu = get_previous_menu(user_id)
    
    await state.clear()
    
    if previous_menu == "main":
        welcome_text = (
            "🌟 <b>Добро пожаловать в Horor VPN!</b> 🌟\n\n"
            "🚀 Высокая скорость\n"
            "📶 Без ограничений по трафику\n"
            "💰 Низкие цены\n"
            "🖱 Настройка в несколько кликов\n"
            "🎁 Вознаграждение за приглашение друзей\n"
            "👩‍💻 Оперативная онлайн поддержка\n\n"
            "👇 Выберите действие ниже 👇"
        )
        try:
            await callback.message.edit_caption(
                caption=welcome_text,
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
        except:
            await callback.message.edit_text(
                welcome_text,
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
    else:
        await callback.message.edit_text(
            "📋 <b>Меню</b>\n\nВыберите нужное действие:",
            parse_mode="HTML",
            reply_markup=get_menu_keyboard()
        )
    
    await callback.answer()

@dp.callback_query(F.data == "referral")
async def referral_system(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    count = referral_counts.get(user_id, 0)
    
    add_history(user_id, "referral")
    
    text = (
        f"🎁 <b>Реферальная система</b>\n\n"
        f"За каждого приведенного друга вы получаете:\n"
        f"💰 +{REFERRAL_RUB} ₽ на баланс\n"
        f"📆 +{REFERRAL_DAYS} дней подписки\n\n"
        f"👥 Приглашено друзей: {count}\n\n"
        f"🔗 <b>Ваша индивидуальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📤 Отправьте её друзьям и получайте бонусы!"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    user_id = callback.from_user.id
    add_history(user_id, "support")
    text = f"👩‍💻 <b>Техническая поддержка</b>\n\nДля связи с техподдержкой напишите сюда:\n👉 @{SUPPORT_USERNAME}\n\nМы ответим в ближайшее время!"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "menu")
async def show_menu(callback: CallbackQuery):
    add_history(callback.from_user.id, "menu")
    
    await callback.message.edit_text(
        "📋 <b>Меню</b>\n\nВыберите нужное действие:",
        parse_mode="HTML",
        reply_markup=get_menu_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "balance")
async def show_balance(callback: CallbackQuery):
    user_id = callback.from_user.id
    days_left = get_balance_days(user_id)
    rub_balance = get_rub_balance(user_id)
    
    add_history(user_id, "balance")
    
    if days_left <= 0:
        days_text = "❌ Истёк"
    else:
        days_text = f"✅ {days_left} дн."
    
    text = (
        f"💰 <b>Ваш баланс</b>\n\n"
        f"💵 <b>Рублевый баланс:</b> {rub_balance} ₽\n"
        f"📆 <b>Подписка активна:</b> {days_text}\n\n"
        f"<i>Пополнить баланс можно через:</i>\n"
        f"• Реферальную систему (приглашайте друзей)\n"
        f"• Кнопку «Пополнить баланс» в меню"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "topup")
async def topup_menu(callback: CallbackQuery):
    add_history(callback.from_user.id, "topup")
    
    text = (
        "💳 <b>Пополнение баланса</b>\n\n"
        "Выберите подходящий тариф:\n\n"
        "📆 10 дней — <b>20 ₽</b>\n"
        "📆 20 дней — <b>45 ₽</b>\n"
        "📆 30 дней — <b>60 ₽</b>\n\n"
        "💰 После оплаты дни будут добавлены к вашей подписке."
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_topup_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("topup_"))
async def process_topup(callback: CallbackQuery):
    days = int(callback.data.split("_")[1])
    amount = PRICES[str(days)]
    user_id = callback.from_user.id
    
    add_history(user_id, "payment")
    
    rub_balance = get_rub_balance(user_id)
    
    if rub_balance >= amount:
        user_balances[user_id]["rub_balance"] = rub_balance - amount
        
        current_expire = user_balances[user_id].get("expire_date")
        if current_expire and current_expire > datetime.now().date():
            new_expire = current_expire + timedelta(days=days)
        else:
            new_expire = get_expire_date(days)
        user_balances[user_id]["expire_date"] = new_expire
        
        await callback.message.edit_text(
            f"✅ <b>Оплата прошла успешно!</b>\n\n"
            f"Списано: {amount} ₽\n"
            f"Добавлено: {days} дней\n\n"
            f"📆 Подписка активна до: {new_expire.strftime('%d.%m.%Y')}",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
    else:
        need = amount - rub_balance
        text = (
            f"⚠️ <b>Недостаточно средств на балансе</b>\n\n"
            f"💰 Ваш баланс: {rub_balance} ₽\n"
            f"💸 Нужно: {amount} ₽\n"
            f"❌ Не хватает: {need} ₽\n\n"
            f"<b>💳 Реквизиты для оплаты:</b>\n"
            f"СБП: +7 XXX XXX XX-XX\n"
            f"Карта: XXXX XXXX XXXX XXXX\n\n"
            f"<i>После оплаты напишите в поддержку для пополнения баланса</i>"
        )
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
    
    await callback.answer()

@dp.callback_query(F.data == "get_key")
async def get_vpn_key(callback: CallbackQuery):
    user_id = callback.from_user.id
    days_left = get_balance_days(user_id)
    
    add_history(user_id, "get_key")
    
    if days_left <= 0:
        await callback.message.edit_text(
            "❌ <b>У вас нет активной подписки</b>\n\n"
            "Пополните баланс, чтобы получить ключ доступа.",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    # Проверяем, есть ли уже ключ
    if user_balances[user_id].get("key_id"):
        key_info = await outline_manager.get_key_info(user_balances[user_id]["key_id"])
        if key_info:
            expire_date = user_balances[user_id].get('expire_date')
            expire_str = expire_date.strftime('%d.%m.%Y') if expire_date else "Неизвестно"
            
            text = (
                f"🔑 <b>Ваш активный ключ</b>\n\n"
                f"<code>{key_info['access_url']}</code>\n\n"
                f"📱 <b>Инструкция по подключению:</b>\n"
                f"1. Скачайте Outline Client из App Store/Google Play\n"
                f"2. Нажмите «Добавить сервер»\n"
                f"3. Вставьте ключ из сообщения выше\n"
                f"4. Подключитесь к VPN\n\n"
                f"📅 Подписка активна до: {expire_str}\n"
                f"⚠️ Ключ привязан только к вашему аккаунту"
            )
            
            await callback.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=get_back_keyboard()
            )
            await callback.answer()
            return
    
    # Создаём новый ключ
    await callback.message.edit_text("🔄 Создаём VPN ключ... Подождите несколько секунд...")
    
    username = f"user_{user_id}"
    vpn_key = await outline_manager.create_key(user_id, days_left, username)
    
    if vpn_key:
        user_balances[user_id]["key_id"] = vpn_key["key_id"]
        expire_date = user_balances[user_id].get('expire_date')
        expire_str = expire_date.strftime('%d.%m.%Y') if expire_date else "Неизвестно"
        
        text = (
            f"✅ <b>VPN ключ успешно создан!</b>\n\n"
            f"🔑 <b>Ваш ключ для подключения:</b>\n"
            f"<code>{vpn_key['access_url']}</code>\n\n"
            f"📱 <b>Инструкция по подключению:</b>\n"
            f"1. Скачайте приложение Outline Client\n"
            f"   • iOS: App Store\n"
            f"   • Android: Google Play\n"
            f"   • Windows/Mac: getoutline.org\n"
            f"2. Нажмите «Добавить сервер»\n"
            f"3. Вставьте ключ из сообщения выше\n"
            f"4. Включите VPN\n\n"
            f"📅 Ключ действителен до: {expire_str}\n"
            f"🔒 Ключ привязан только к вашему аккаунту\n\n"
            f"<i>Сохраните этот ключ! При потере вы сможете создать новый через меню</i>"
        )
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при создании VPN ключа\n\n"
            "Возможные причины:\n"
            "• Проблемы с подключением к VPN серверу\n"
            "• Технические работы\n\n"
            "Попробуйте позже или обратитесь в поддержку.",
            reply_markup=get_back_keyboard()
        )
    
    await callback.answer()

@dp.callback_query(F.data == "replace_key")
async def replace_key(callback: CallbackQuery):
    user_id = callback.from_user.id
    days_left = get_balance_days(user_id)
    
    add_history(user_id, "replace_key")
    
    if days_left <= 0:
        await callback.message.edit_text(
            "❌ <b>Баланс истёк</b>\n\nПополните баланс, чтобы заменить ключ.",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    # Удаляем старый ключ
    old_key_id = user_balances[user_id].get("key_id")
    if old_key_id:
        await outline_manager.delete_key(old_key_id)
        user_balances[user_id]["key_id"] = None
    
    # Создаём новый
    await callback.message.edit_text("🔄 Создаём новый ключ...")
    
    username = f"user_{user_id}_new"
    vpn_key = await outline_manager.create_key(user_id, days_left, username)
    
    if vpn_key:
        user_balances[user_id]["key_id"] = vpn_key["key_id"]
        
        text = (
            f"🔄 <b>Новый ключ создан!</b>\n\n"
            f"🔑 <b>Ваш новый ключ:</b>\n"
            f"<code>{vpn_key['access_url']}</code>\n\n"
            f"Старый ключ больше не работает."
        )
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при создании нового ключа",
            reply_markup=get_back_keyboard()
        )
    
    await callback.answer()

@dp.callback_query(F.data == "delete_key")
async def delete_key_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    add_history(user_id, "delete_key")
    
    if not user_balances[user_id].get("key_id"):
        await callback.message.edit_text(
            "❌ У вас нет активного ключа",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    text = (
        "⚠️ <b>Удаление VPN ключа</b>\n\n"
        "После удаления ключа VPN перестанет работать.\n"
        "Баланс сохранится, вы сможете создать новый ключ позже.\n\n"
        "Удалить ключ?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Да, удалить", callback_data="confirm_delete_key")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back")]
    ])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "confirm_delete_key")
async def confirm_delete_key(callback: CallbackQuery):
    user_id = callback.from_user.id
    key_id = user_balances[user_id].get("key_id")
    
    if key_id:
        await outline_manager.delete_key(key_id)
        user_balances[user_id]["key_id"] = None
    
    await callback.message.edit_text(
        "✅ <b>VPN ключ удалён</b>\n\n"
        "Вы можете создать новый ключ в любой момент через меню.",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Бот Horor VPN успешно запущен!")
    print("📌 Команды:")
    print("   /start - запуск бота")
    print("   Кнопки в меню должны работать")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())