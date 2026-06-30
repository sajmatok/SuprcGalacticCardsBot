import asyncio
import time
import os
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from database import Database

# --- КОНФІГУРАЦІЯ ---
TOKEN = os.getenv("BOT_TOKEN")
MY_ID = 7518373450
ADMINS = [7518373450, 6951417132, 1834172177]
DB_URL = os.getenv("DATABASE_URL", "ВАШ_URL")
GLOBAL_COOLDOWN = 60
CASINO_COOLDOWN = 70
STEAL_COOLDOWN = 120
BLACK_LIST = [5398023503]
BOT_ACTIVE = True

bot = Bot(token=TOKEN)
dp = Dispatcher()
db = Database(DB_URL)

# Магазин товарів (виправлено: раніше змінна не існувала і команда "купити" падала з помилкою)
SHOP_ITEMS = {
    "1": {"name": "VIP на 1 день",     "price": 300,  "type": "vip",     "seconds": 86400,       "emoji": "👑"},
    "2": {"name": "VIP на 7 днів",     "price": 1500, "type": "vip",     "seconds": 7 * 86400,   "emoji": "👑"},
    "3": {"name": "Буст x2 на 1 год",  "price": 200,  "type": "boost",   "seconds": 3600,        "emoji": "🚀"},
    "4": {"name": "Буст x2 на 6 год",  "price": 900,  "type": "boost",   "seconds": 6 * 3600,    "emoji": "🚀"},
    "5": {"name": "Захист на 1 день",  "price": 400,  "type": "shield",  "seconds": 86400,       "emoji": "🛡"},
    "6": {"name": "Лотерейний квиток", "price": 150,  "type": "lottery", "seconds": 0,           "emoji": "🎟"},
}

# Кастомні шанси на виграш в казино для конкретних гравців (встановлює власник)
# user_id -> шанс виграшу від 0.0 до 1.0
casino_chance: dict[int, float] = {}

# --- КЛАВІАТУРИ ---
def get_main_keyboard(user_id):
    if user_id in BLACK_LIST:
        return ReplyKeyboardRemove()
    buttons = [
        [KeyboardButton(text="🃏 Картка"),     KeyboardButton(text="👤 Профіль")],
        [KeyboardButton(text="🏆 Топ"),        KeyboardButton(text="🎁 Подарунок")],
        [KeyboardButton(text="🎰 Казино")],
        [KeyboardButton(text="⚔️ Дуель")],
        [KeyboardButton(text="❓ Допомога")],
    ]
    if user_id in ADMINS or user_id == MY_ID:
        buttons.append([KeyboardButton(text="🛠 Адмін панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- ЛОГІКА КАРТОК ---
def get_card_rarity():
    r = random.random() * 100
    if r <= 0.1:  return "🛠 УНІКАЛЬНА",  250, "🔥"
    if r <= 1.0:  return "💎 VIP КАРТКА", 200, "👑"
    if r <= 10.0: return "🟡 ЛЕГЕНДАРНА", 100, "🌟"
    if r <= 20.0: return "🟣 ЕПІЧНА",      50, "✨"
    if r <= 45.0: return "🔵 РІДКІСНА",    30, "🔹"
    return              "⚪️ ЗВИЧАЙНА",     15, "▫️"

# --- УТИЛІТИ ---
def escape_md(text: str) -> str:
    special = r"_*[]()~`>#+-=|{}.!\\"
    return "".join(f"\\{c}" if c in special else c for c in str(text))

def today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")

def streak_bonus(streak: int) -> int:
    return min(streak, 10) * 10  # +10% за день, макс +100%

# ================================================================
# ХЕНДЛЕРИ — КНОПКИ
# ================================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    db.update_user(uid, message.from_user.full_name)
    await message.answer(
        f"👋 Привіт, {escape_md(message.from_user.first_name)}\\!\n"
        f"Готовий збирати колекцію трофеїв?\n\n"
        f"Натисни *❓ Допомога* щоб дізнатись всі команди\\!",
        reply_markup=get_main_keyboard(uid),
        parse_mode="MarkdownV2"
    )

# --- ЗМІНА ІМЕНІ ---
@dp.message(F.text.regexp(r"(?i)^ім'я\s+(.+)$"))
async def change_name(message: types.Message):
    uid = message.from_user.id
    new_name = message.text.split(maxsplit=1)[1].strip()
    if len(new_name) > 30:
        return await message.reply("❌ Ім'я занадто довге\\! Максимум 30 символів\\.", parse_mode="MarkdownV2")
    db.set_user_name(uid, new_name)
    await message.reply(f"✅ Ім'я змінено на: *{escape_md(new_name)}*", parse_mode="MarkdownV2")

# --- ПРОФІЛЬ ---
@dp.message(F.text == "👤 Профіль")
async def show_profile(message: types.Message):
    uid = message.from_user.id
    db.update_user(uid, message.from_user.full_name)

    coins, msgs = db.get_user_data(uid)
    rank        = db.get_user_rank(uid)
    collected   = db.get_total_collected(uid)
    total       = db.get_total_players()
    streak, _   = db.get_streak_data(uid)
    achievements = db.get_user_achievements(uid)

    ach_list = [f"{i+1}\\. {escape_md(a)}" for i, a in enumerate(achievements)]
    ach_str  = "\n".join(ach_list) if ach_list else "Немає нагород 🎖"

    user_name = db.get_user_name(uid) or message.from_user.full_name
    role = "Власник 👑" if uid == MY_ID else ("VIP Гравець ⭐" if db.check_vip(uid) else "Учасник")

    vip_str    = "✅" if db.check_vip(uid)    else "❌"
    boost_str  = "✅" if db.check_boost(uid)  else "❌"
    shield_str = "✅" if db.check_shield(uid) else "❌"

    caption = (
        f"👤 *Ім'я:* {escape_md(user_name)}\n"
        f"🆔 *ID:* `{uid}`\n"
        f"🎭 *Роль:* {escape_md(role)}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🏆 *Трофеїв:* {escape_md(str(coins))}\n"
        f"🥇 *Місце в топі:* \\#{escape_md(str(rank))}\n"
        f"✉️ *Повідомлень:* `{msgs}`\n"
        f"🃏 *Колекція:* `{collected}/{total}`\n"
        f"🔥 *Стрік:* `{streak}` дн\\.\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🎖 *Нагороди:*\n{ach_str}"
    )
    try:
        photos = await bot.get_user_profile_photos(uid, limit=1)
        if photos.total_count > 0:
            await message.answer_photo(photos.photos[0][-1].file_id, caption=caption, parse_mode="MarkdownV2")
            return
    except Exception:
        pass
    await message.answer(caption, parse_mode="MarkdownV2")

# --- КАРТКА ---
@dp.message(F.text == "🃏 Картка")
async def give_card(message: types.Message):
    if not BOT_ACTIVE and message.from_user.id not in ADMINS:
        return
    try:
        uid = message.from_user.id
        db.update_user(uid, message.from_user.full_name)
        now = time.time()
        last_time = db.get_last_card_time(uid)
        if uid != MY_ID and (now - last_time < GLOBAL_COOLDOWN):
            wait = int(GLOBAL_COOLDOWN - (now - last_time))
            return await message.reply(f"⏳ Зачекай *{wait}* сек\\.", parse_mode="MarkdownV2")

        target = db.get_random_user()
        if not target:
            return await message.reply("База порожня\\!", parse_mode="MarkdownV2")

        rarity, bonus, icon = get_card_rarity()
        if target[0] == MY_ID:
            rarity, bonus, icon = "🛠 УНІКАЛЬНА", 250, "🔥"
        if db.check_vip(uid):
            bonus *= 2
            if target[0] == uid and target[0] != MY_ID:
                rarity, icon = "💎 VIP КАРТКА", "👑"
        if db.check_boost(uid):
            bonus *= 2

        db.add_to_collection(uid, target[0], rarity)
        db.add_coins(uid, bonus)
        db.set_last_card_time(uid, now)

        await message.answer(
            f"🎊 *ТОБІ ВИПАЛА КАРТКА\\!*\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"👤 Гравець: `{escape_md(target[1])}`\n"
            f"{icon} Рідкість: *{escape_md(rarity)}*\n"
            f"🏆 Бонус: \\+{bonus} трофеїв",
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        await message.reply(f"❌ Помилка: {escape_md(str(e))}", parse_mode="MarkdownV2")

# --- ЩОДЕННИЙ ПОДАРУНОК ---
@dp.message(F.text == "🎁 Подарунок")
async def daily_gift(message: types.Message):
    uid = message.from_user.id
    db.update_user(uid, message.from_user.full_name)
    now = time.time()
    last_gift = db.get_last_gift_time(uid)

    if now - last_gift < 86400:
        remaining = int(86400 - (now - last_gift))
        h = remaining // 3600
        m = (remaining % 3600) // 60
        return await message.reply(
            f"🎁 Наступний подарунок через *{escape_md(str(h))}г {escape_md(str(m))}хв*",
            parse_mode="MarkdownV2"
        )

    streak, last_day = db.get_streak_data(uid)
    today     = today_str()
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    if last_day == yesterday:
        streak += 1
    elif last_day != today:
        streak = 1

    db.update_streak(uid, streak, today)

    base    = random.randint(50, 500)
    pct     = streak_bonus(streak)
    bonus   = int(base * pct / 100)
    total_r = base + bonus

    db.add_coins(uid, total_r)
    db.set_last_gift_time(uid, now)

    streak_line = (
        f"🔥 Стрік: *{streak}* дн\\. \\(\\+{pct}% бонус\\)" if streak > 1
        else "🔥 Стрік: *1* день — приходь завтра за бонусом\\!"
    )
    await message.answer(
        f"🎁 *ЩОДЕННИЙ ПОДАРУНОК\\!*\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"Базовий: *\\+{escape_md(str(base))}* 🏆\n"
        f"Стрік бонус: *\\+{escape_md(str(bonus))}* 🏆\n"
        f"Разом: *\\+{escape_md(str(total_r))}* 🏆\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"{streak_line}",
        parse_mode="MarkdownV2"
    )

# --- ТОП ---
@dp.message(F.text == "🏆 Топ")
async def show_top(message: types.Message):
    top_users = db.get_leaderboard()
    res = "🏆 *ТОП\\-10 ПУШЕРІВ \\(Трофеї\\):*\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, user in enumerate(top_users, 1):
        icon = medals.get(i, f"{i}\\.")
        res += f"{icon} {escape_md(user[0])} — *{escape_md(str(user[1]))}* 🏆\n"
    await message.answer(res, parse_mode="MarkdownV2")

# --- КАЗИНО (КНОПКА) ---
@dp.message(F.text == "🎰 Казино")
async def casino_menu(message: types.Message):
    uid = message.from_user.id
    db.update_user(uid, message.from_user.full_name)
    coins, _ = db.get_user_data(uid)
    await message.reply(
        f"🎰 *КАЗИНО*\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"💰 Баланс: *{escape_md(str(coins))}* 🏆",
        parse_mode="MarkdownV2"
    )

# --- ДУЕЛЬ (КНОПКА) ---
@dp.message(F.text == "⚔️ Дуель")
async def duel_menu(message: types.Message):
    await message.reply(
        "⚔️ *ДУЕЛЬ*\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "Виклич суперника\\! Шанс виграшу — рівно *50/50*\\.",
        parse_mode="MarkdownV2"
    )

# --- ДОПОМОГА ---
@dp.message(F.text == "❓ Допомога")
async def help_all(message: types.Message):
    text = (
        "❓ *ДОПОМОГА*\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "Користуйся кнопками меню нижче, щоб збирати картки, отримувати подарунки та грати в ігри\\."
    )
    await message.reply(text, parse_mode="MarkdownV2")

# ================================================================
# АКТИВНІ ДУЕЛІ та МОНЕТКА
# ================================================================
duels = {}
last_coin_flip: dict[int, float] = {}
last_casino_play: dict[int, float] = {}
last_steal: dict[int, float] = {}


def resolve_target_and_args(message: types.Message, parts: list[str], start_idx: int = 1):
    """
    Визначає id цільового гравця та залишок аргументів.
    Якщо повідомлення є відповіддю на чиєсь повідомлення — беремо айді звідти,
    а всі параметри після команди вважаються додатковими аргументами (наприклад ставкою/сумою).
    Інакше перший параметр після команди — це айді, а решта — аргументи.
    Повертає (target_id, args) або (None, []) якщо не вдалось визначити.
    """
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id, parts[start_idx:]
    if len(parts) <= start_idx:
        return None, []
    try:
        target_id = int(parts[start_idx])
    except ValueError:
        return None, []
    return target_id, parts[start_idx + 1:]

# ================================================================
# УНІВЕРСАЛЬНИЙ ОБРОБНИК
# ================================================================
@dp.message()
async def universal_handler(message: types.Message):
    global BOT_ACTIVE, GLOBAL_COOLDOWN, CASINO_COOLDOWN

    uid = message.from_user.id
    if uid in BLACK_LIST:
        return

    # Реєструємо юзера одразу
    db.update_user(uid, message.from_user.full_name)

    if not message.text:
        db.update_message_count(uid)
        return

    original_parts = message.text.split()
    text_lower     = message.text.lower().split()
    cmd            = text_lower[0] if text_lower else ""

    # ================================================================
    # КОМАНДИ ДЛЯ ВСІХ
    # ================================================================

    # --- КУПИТИ ---
    if cmd == "купити" and len(text_lower) > 1:
        item_key = text_lower[1]
        item = SHOP_ITEMS.get(item_key)
        if not item:
            return await message.reply("❌ Такого товару немає\\.", parse_mode="MarkdownV2")
        coins, _ = db.get_user_data(uid)
        if coins < item["price"]:
            return await message.reply(
                f"❌ Не вистачає трофеїв\\. Треба *{escape_md(str(item['price']))}* 🏆, "
                f"у тебе *{escape_md(str(coins))}* 🏆\\.",
                parse_mode="MarkdownV2"
            )
        db.add_coins(uid, -item["price"])
        if   item["type"] == "vip":     db.add_vip_time(uid, item["seconds"])
        elif item["type"] == "boost":   db.add_boost_time(uid, item["seconds"])
        elif item["type"] == "shield":  db.add_shield_time(uid, item["seconds"])
        elif item["type"] == "lottery": db.add_lottery_ticket(uid)
        await message.reply(
            f"✅ Куплено: {item['emoji']} *{escape_md(item['name'])}*\\!\n"
            f"💸 Списано: *{escape_md(str(item['price']))}* 🏆",
            parse_mode="MarkdownV2"
        )
        return

    # --- ЛОТЕРЕЯ ---
    if cmd == "лотерея":
        tickets = db.get_lottery_tickets(uid)
        if tickets <= 0:
            return await message.reply("❌ Немає квитків\\.", parse_mode="MarkdownV2")
        db.use_lottery_ticket(uid)
        # Призи: 10% — джекпот 2000, 30% — 500, 60% — 50-200
        r = random.random()
        if r < 0.10:
            prize = 2000
            result_line = f"🎉 *ДЖЕКПОТ\\!* \\+{prize} 🏆"
        elif r < 0.40:
            prize = 500
            result_line = f"🥳 Великий приз\\! \\+{prize} 🏆"
        else:
            prize = random.randint(50, 200)
            result_line = f"🎟 Приз: \\+{prize} 🏆"
        db.add_coins(uid, prize)
        remaining = tickets - 1
        await message.reply(
            f"🎟 *ЛОТЕРЕЯ\\!*\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"{result_line}\n"
            f"Залишилось квитків: *{escape_md(str(remaining))}*",
            parse_mode="MarkdownV2"
        )
        return

    # --- МОНЕТКА ---
    if cmd == "монетка":
        if len(text_lower) < 2 or text_lower[1] not in ("орел", "решка"):
            return await message.reply(
                "🪙 Напиши *монетка орел* або *монетка решка*\\.",
                parse_mode="MarkdownV2"
            )
        choice = text_lower[1]
        now = time.time()
        last = last_coin_flip.get(uid, 0)
        cooldown = 300  # 5 хв
        if now - last < cooldown:
            wait = int(cooldown - (now - last))
            return await message.reply(
                f"🪙 Монетка відпочиває ще *{escape_md(str(wait))}* сек\\.",
                parse_mode="MarkdownV2"
            )
        last_coin_flip[uid] = now
        result = random.choice(["орел", "решка"])
        win = (result == choice)
        result_icon = "🦅" if result == "орел" else "🪙"
        if win:
            prize = random.randint(10, 50)
            db.add_coins(uid, prize)
            await message.reply(
                f"{result_icon} Випав *{escape_md(result.upper())}\\!* Ти вгадав і виграв *\\+{prize}* 🏆",
                parse_mode="MarkdownV2"
            )
        else:
            await message.reply(
                f"{result_icon} Випав *{escape_md(result.upper())}\\!* Ти не вгадав\\. Удачі наступного разу\\!",
                parse_mode="MarkdownV2"
            )
        return

    # --- КАЗИНО ---
    if cmd == "казино" and len(text_lower) > 1:
        try:
            # --- ПЕРЕВІРКА КУЛДАУНУ (у власника кулдауну немає) ---
            now = time.time()
            last = last_casino_play.get(uid, 0)

            if uid != MY_ID and (now - last < CASINO_COOLDOWN):
                wait = int(CASINO_COOLDOWN - (now - last))
                return await message.reply(
                    f"🎰 Казино ще не доступне\\! Зачекай ще *{escape_md(str(wait))}* сек\\.",
                    parse_mode="MarkdownV2"
                )
            # ---------------------------

            bet = int(text_lower[1])
            if bet <= 0:
                return await message.reply("❌ Ставка має бути більше 0\\.", parse_mode="MarkdownV2")
            coins, _ = db.get_user_data(uid)
            if coins < bet:
                return await message.reply(
                    f"❌ Недостатньо трофеїв\\. У тебе *{escape_md(str(coins))}* 🏆",
                    parse_mode="MarkdownV2"
                )

            # Оновлюємо час останньої гри (кулдаун зараховується лише при спробі зіграти)
            last_casino_play[uid] = now

            chance = casino_chance.get(uid, 0.5)
            win = random.random() < chance
            if win:
                prize = bet // 2
                db.add_coins(uid, prize)
                await message.reply(
                    f"🎰 *ВИГРАШ\\!*\n"
                    f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                    f"Ставка: *{escape_md(str(bet))}* 🏆\n"
                    f"Прибуток: *\\+{escape_md(str(prize))}* 🏆\n"
                    f"🍀 Удача на твоєму боці\\!",
                    parse_mode="MarkdownV2"
                )
            else:
                db.add_coins(uid, -bet)
                await message.reply(
                    f"🎰 *ПРОГРАШ\\!*\n"
                    f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                    f"Ставка: *{escape_md(str(bet))}* 🏆\n"
                    f"Збиток: *\\-{escape_md(str(bet))}* 🏆\n"
                    f"😔 Спробуй ще раз\\!",
                    parse_mode="MarkdownV2"
                )
        except (ValueError, IndexError):
            await message.reply("❌ Неправильна ставка\\.", parse_mode="MarkdownV2")
        return

    # --- ПЕРЕДАТИ ---
    if cmd == "передати" and len(text_lower) > 1:
        try:
            target_id, args = resolve_target_and_args(message, text_lower, 1)
            if target_id is None or not args:
                return await message.reply("❌ Вкажи айді та кількість, або дай відповідь на повідомлення гравця\\.", parse_mode="MarkdownV2")
            amount = int(args[0])
            if amount <= 0:
                return await message.reply("❌ Сума має бути більше нуля\\.", parse_mode="MarkdownV2")
            if target_id == uid:
                return await message.reply("❌ Не можна передавати собі\\.", parse_mode="MarkdownV2")
            coins, _ = db.get_user_data(uid)
            if coins < amount:
                return await message.reply(
                    f"❌ Недостатньо трофеїв\\. У тебе *{escape_md(str(coins))}* 🏆",
                    parse_mode="MarkdownV2"
                )
            target_name = db.get_user_name(target_id)
            if not target_name:
                return await message.reply("❌ Гравця не знайдено\\.", parse_mode="MarkdownV2")
            db.add_coins(uid, -amount)
            db.add_coins(target_id, amount)
            sender_name = db.get_user_name(uid) or message.from_user.full_name
            await message.reply(
                f"✅ Передано *{escape_md(str(amount))}* 🏆 → *{escape_md(target_name)}*",
                parse_mode="MarkdownV2"
            )
            try:
                await bot.send_message(
                    target_id,
                    f"🎁 *{escape_md(sender_name)}* передав тобі *{escape_md(str(amount))}* 🏆",
                    parse_mode="MarkdownV2"
                )
            except Exception:
                pass
        except (ValueError, IndexError):
            await message.reply("❌ Неправильні параметри\\.", parse_mode="MarkdownV2")
        return

    # --- ТОП МІСЦЕ ---
    if cmd == "топ" and len(text_lower) > 1:
        try:
            place = int(text_lower[1])
            if place < 1:
                return await message.reply("❌ Місце має бути більше 0\\.", parse_mode="MarkdownV2")
            result = db.get_user_at_rank(place)
            if not result:
                return await message.reply(
                    f"❌ На місці *{escape_md(str(place))}* нікого немає\\.",
                    parse_mode="MarkdownV2"
                )
            name, coins_val = result
            await message.reply(
                f"🥇 *Місце \\#{escape_md(str(place))}*\n"
                f"👤 {escape_md(name)}\n"
                f"🏆 {escape_md(str(coins_val))} трофеїв",
                parse_mode="MarkdownV2"
            )
        except (ValueError, IndexError):
            await message.reply("❌ Неправильний номер місця\\.", parse_mode="MarkdownV2")
        return

    # --- МІЙ ТОП ---
    if cmd == "мій" and len(text_lower) > 1 and text_lower[1] == "топ":
        rank  = db.get_user_rank(uid)
        total = db.get_total_players()
        coins, _ = db.get_user_data(uid)
        name  = db.get_user_name(uid) or message.from_user.full_name
        await message.reply(
            f"📍 *{escape_md(name)}*\n"
            f"Місце: *\\#{escape_md(str(rank))}* з {escape_md(str(total))}\n"
            f"🏆 {escape_md(str(coins))} трофеїв",
            parse_mode="MarkdownV2"
        )
        return

    # --- ДУЕЛЬ: ВИКЛИК ---
    if cmd == "дуель" and len(text_lower) > 1:
        try:
            target_id, args = resolve_target_and_args(message, text_lower, 1)
            if target_id is None or not args:
                return await message.reply("❌ Вкажи айді та ставку, або дай відповідь на повідомлення гравця\\.", parse_mode="MarkdownV2")
            bet = int(args[0])
            if target_id == uid:
                return await message.reply("❌ Не можна викликати себе\\.", parse_mode="MarkdownV2")
            if bet <= 0:
                return await message.reply("❌ Ставка має бути більше 0\\.", parse_mode="MarkdownV2")
            coins, _ = db.get_user_data(uid)
            if coins < bet:
                return await message.reply(
                    f"❌ Недостатньо трофеїв\\. У тебе *{escape_md(str(coins))}* 🏆",
                    parse_mode="MarkdownV2"
                )
            target_name = db.get_user_name(target_id)
            if not target_name:
                return await message.reply("❌ Гравця не знайдено\\.", parse_mode="MarkdownV2")
            if db.check_shield(target_id):
                return await message.reply(
                    f"🛡 *{escape_md(target_name)}* захищений від дуелей\\!",
                    parse_mode="MarkdownV2"
                )
            target_coins, _ = db.get_user_data(target_id)
            if target_coins < bet:
                return await message.reply(
                    "❌ У суперника недостатньо трофеїв для цієї ставки\\.",
                    parse_mode="MarkdownV2"
                )
            my_name = db.get_user_name(uid) or message.from_user.full_name
            duels[target_id] = {
                "challenger_id":   uid,
                "challenger_name": my_name,
                "bet":             bet,
                "time":            time.time()
            }
            await message.reply(
                f"⚔️ Виклик надіслано *{escape_md(target_name)}* на *{escape_md(str(bet))}* 🏆",
                parse_mode="MarkdownV2"
            )
            try:
                await bot.send_message(
                    target_id,
                    f"⚔️ *{escape_md(my_name)}* викликає тебе на дуель\\!\n"
                    f"🏆 Ставка: *{escape_md(str(bet))}* трофеїв\n\n"
                    f"Відповідай: `прийняти` або `відхилити`",
                    parse_mode="MarkdownV2"
                )
            except Exception:
                pass
        except (ValueError, IndexError):
            await message.reply("❌ Неправильні параметри\\.", parse_mode="MarkdownV2")
        return

    # --- ДУЕЛЬ: ПРИЙНЯТИ ---
    if cmd == "прийняти":
        duel = duels.get(uid)
        if not duel:
            return await message.reply("❌ У тебе немає активних викликів\\.", parse_mode="MarkdownV2")
        if time.time() - duel["time"] > 120:
            del duels[uid]
            return await message.reply("❌ Час виклику вийшов\\.", parse_mode="MarkdownV2")

        challenger_id = duel["challenger_id"]
        bet = duel["bet"]
        del duels[uid]

        c_coins, _ = db.get_user_data(challenger_id)
        t_coins, _ = db.get_user_data(uid)
        if c_coins < bet or t_coins < bet:
            return await message.reply("❌ У когось не вистачає трофеїв\\.", parse_mode="MarkdownV2")

        winner_id = random.choice([challenger_id, uid])
        loser_id  = uid if winner_id == challenger_id else challenger_id
        winner_name = db.get_user_name(winner_id) or "?"
        loser_name  = db.get_user_name(loser_id)  or "?"

        db.add_coins(winner_id,  bet)
        db.add_coins(loser_id,  -bet)

        result_text = (
            f"⚔️ *РЕЗУЛЬТАТ ДУЕЛІ\\!*\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"🏆 Ставка: *{escape_md(str(bet))}* трофеїв\n\n"
            f"🥇 Переможець: *{escape_md(winner_name)}*\n"
            f"💀 Переможений: *{escape_md(loser_name)}*\n\n"
            f"*\\+{escape_md(str(bet))}* 🏆 → {escape_md(winner_name)}"
        )
        await message.answer(result_text, parse_mode="MarkdownV2")
        try:
            await bot.send_message(challenger_id, result_text, parse_mode="MarkdownV2")
        except Exception:
            pass
        return

    # --- ДУЕЛЬ: ВІДХИЛИТИ ---
    if cmd == "відхилити":
        duel = duels.get(uid)
        if not duel:
            return await message.reply("❌ У тебе немає активних викликів\\.", parse_mode="MarkdownV2")
        challenger_id = duel["challenger_id"]
        del duels[uid]
        my_name = db.get_user_name(uid) or message.from_user.full_name
        await message.reply("✅ Ти відхилив виклик\\.", parse_mode="MarkdownV2")
        try:
            await bot.send_message(
                challenger_id,
                f"😔 *{escape_md(my_name)}* відхилив твій виклик\\.",
                parse_mode="MarkdownV2"
            )
        except Exception:
            pass
        return

    # --- ПОЦУПИТИ ---
    if cmd == "поцупити":
        now = time.time()
        last = last_steal.get(uid, 0)
        if uid != MY_ID and (now - last < STEAL_COOLDOWN):
            wait = int(STEAL_COOLDOWN - (now - last))
            return await message.reply(
                f"🕵️ Зачекай *{escape_md(str(wait))}* сек\\, перш ніж знову красти\\.",
                parse_mode="MarkdownV2"
            )

        target_id, _ = resolve_target_and_args(message, text_lower, 1)
        if target_id is None:
            target = db.get_random_rich_user(uid)
            if not target:
                return await message.reply("❌ Немає в кого красти\\.", parse_mode="MarkdownV2")
            target_id = target[0]

        if target_id == uid:
            return await message.reply("❌ Не можна красти у себе\\.", parse_mode="MarkdownV2")

        target_name = db.get_user_name(target_id)
        if not target_name:
            return await message.reply("❌ Гравця не знайдено\\.", parse_mode="MarkdownV2")

        if db.check_shield(target_id):
            return await message.reply(
                f"🛡 *{escape_md(target_name)}* захищений і не дав себе обікрасти\\!",
                parse_mode="MarkdownV2"
            )

        last_steal[uid] = now
        target_coins, _ = db.get_user_data(target_id)
        success = random.random() < 0.5

        if not success:
            return await message.reply(
                f"🕵️ Спроба обікрасти *{escape_md(target_name)}* провалилась\\!",
                parse_mode="MarkdownV2"
            )

        amount = min(random.randint(1, 1000), max(target_coins, 0))
        if amount <= 0:
            return await message.reply(
                f"🕵️ У *{escape_md(target_name)}* нічого вкрасти\\.",
                parse_mode="MarkdownV2"
            )

        db.add_coins(target_id, -amount)
        db.add_coins(uid, amount)
        await message.reply(
            f"🕵️ *КРАДІЖКА ВДАЛАСЬ\\!*\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"Ти вкрав у *{escape_md(target_name)}* *\\+{escape_md(str(amount))}* 🏆",
            parse_mode="MarkdownV2"
        )
        try:
            await bot.send_message(
                target_id,
                f"😱 У тебе вкрали *{escape_md(str(amount))}* 🏆\\!",
                parse_mode="MarkdownV2"
            )
        except Exception:
            pass
        return

    # --- Лічильник повідомлень ---
    db.update_message_count(uid)

    is_admin = (uid in ADMINS) or (uid == MY_ID)
    if not is_admin:
        return

    # ================================================================
    # АДМІН КОМАНДИ
    # ================================================================
    try:
        if cmd == "стоп":
            BOT_ACTIVE = False
            await message.reply("🔴 Бот зупинено\\.", parse_mode="MarkdownV2")

        elif cmd == "старт":
            BOT_ACTIVE = True
            await message.reply("🟢 Бот запущено\\!", parse_mode="MarkdownV2")

        elif cmd == "кд" and len(text_lower) > 1:
            GLOBAL_COOLDOWN = int(text_lower[1])
            await message.reply(f"⏳ Кулдаун карток: *{GLOBAL_COOLDOWN}* сек\\.", parse_mode="MarkdownV2")

        elif cmd == "кд_казино" and len(text_lower) > 1:
            CASINO_COOLDOWN = int(text_lower[1])
            await message.reply(f"⏳ Кулдаун казино: *{CASINO_COOLDOWN}* сек\\.", parse_mode="MarkdownV2")

        elif cmd == "шанс_казино" and len(text_lower) > 1:
            target_id, args = resolve_target_and_args(message, text_lower, 1)
            if target_id is None or not args:
                await message.reply("❌ Вкажи айді та відсоток, або дай відповідь на повідомлення гравця\\.", parse_mode="MarkdownV2")
            else:
                percent = max(0, min(100, int(args[0])))
                casino_chance[target_id] = percent / 100
                target_name = db.get_user_name(target_id) or str(target_id)
                await message.reply(
                    f"🎰 Шанс виграшу для *{escape_md(target_name)}* встановлено на *{escape_md(str(percent))}%*\\.",
                    parse_mode="MarkdownV2"
                )

        elif cmd == "видати" and len(text_lower) > 2:
            amount = int(text_lower[2])
            if text_lower[1] == "всім":
                for user in db.get_all_users():
                    db.add_coins(user[0], amount)
                await message.reply(f"✅ Всім видано по *{escape_md(str(amount))}* 🏆", parse_mode="MarkdownV2")
            else:
                db.add_coins(int(text_lower[1]), amount)
                await message.reply(f"✅ Видано *{escape_md(str(amount))}* 🏆", parse_mode="MarkdownV2")

        elif cmd == "забрати" and len(text_lower) > 2:
            amount = int(text_lower[2])
            if text_lower[1] == "всіх":
                for user in db.get_all_users():
                    db.add_coins(user[0], -amount)
                await message.reply(f"✅ У всіх забрано *{escape_md(str(amount))}* 🏆", parse_mode="MarkdownV2")
            else:
                db.add_coins(int(text_lower[1]), -amount)
                await message.reply(f"✅ Забрано *{escape_md(str(amount))}* 🏆", parse_mode="MarkdownV2")

        elif cmd == "нагородити" and (message.reply_to_message or len(original_parts) > 2):
            if message.reply_to_message and message.reply_to_message.from_user:
                target_id = message.reply_to_message.from_user.id
                ach_text  = " ".join(original_parts[1:])
            else:
                target_id = int(original_parts[1])
                ach_text  = " ".join(original_parts[2:])
            if not ach_text:
                await message.reply("❌ Вкажи текст нагороди\\.", parse_mode="MarkdownV2")
            else:
                db.add_achievement(target_id, ach_text)
                await message.reply("✅ Нагорода видана\\!", parse_mode="MarkdownV2")
                try:
                    await bot.send_message(
                        target_id,
                        f"🎊 Нова нагорода: *{escape_md(ach_text)}*",
                        parse_mode="MarkdownV2"
                    )
                except Exception:
                    pass

        elif cmd == "зняти" and len(text_lower) > 2:
            target_id = int(text_lower[1])
            idx       = int(text_lower[2]) - 1
            achievements = db.get_user_achievements(target_id)
            if idx < 0 or idx >= len(achievements):
                await message.reply(
                    f"❌ У гравця лише *{escape_md(str(len(achievements)))}* нагород\\.",
                    parse_mode="MarkdownV2"
                )
            else:
                removed = achievements[idx]
                db.remove_achievement(target_id, idx)
                await message.reply(f"✅ Нагороду *{escape_md(removed)}* знято\\.", parse_mode="MarkdownV2")

        elif cmd == "віп" and len(text_lower) > 1:
            target_id, args = resolve_target_and_args(message, text_lower, 1)
            if target_id is None or not args:
                await message.reply("❌ Вкажи айді та кількість днів, або дай відповідь на повідомлення гравця\\.", parse_mode="MarkdownV2")
            else:
                db.add_vip_time(target_id, int(args[0]) * 86400)
                await message.reply("✅ VIP активовано\\!", parse_mode="MarkdownV2")

        elif cmd == "зняти_віп" and len(text_lower) > 1:
            db.remove_vip(int(text_lower[1]))
            await message.reply("✅ VIP знято\\.", parse_mode="MarkdownV2")

        elif cmd == "буст" and len(text_lower) > 1:
            target_id, args = resolve_target_and_args(message, text_lower, 1)
            if target_id is None or not args:
                await message.reply("❌ Вкажи айді та кількість годин, або дай відповідь на повідомлення гравця\\.", parse_mode="MarkdownV2")
            else:
                db.add_boost_time(target_id, int(args[0]) * 3600)
                await message.reply("✅ Буст активовано\\!", parse_mode="MarkdownV2")

        elif cmd == "профіль" and (message.reply_to_message or len(text_lower) > 1):
            target_id = message.reply_to_message.from_user.id if message.reply_to_message and message.reply_to_message.from_user else int(text_lower[1])
            target_name = db.get_user_name(target_id)
            if not target_name:
                return await message.reply("❌ Гравця не знайдено\\.", parse_mode="MarkdownV2")
            # будуємо профіль як для show_profile
            coins, msgs  = db.get_user_data(target_id)
            rank         = db.get_user_rank(target_id)
            collected    = db.get_total_collected(target_id)
            total        = db.get_total_players()
            streak, _    = db.get_streak_data(target_id)
            achievements = db.get_user_achievements(target_id)
            ach_list     = [f"{i+1}\\. {escape_md(a)}" for i, a in enumerate(achievements)]
            ach_str      = "\n".join(ach_list) if ach_list else "Немає нагород 🎖"
            role = "Власник 👑" if target_id == MY_ID else ("VIP Гравець ⭐" if db.check_vip(target_id) else "Учасник")
            caption = (
                f"👤 *Ім'я:* {escape_md(target_name)}\n"
                f"🆔 *ID:* `{target_id}`\n"
                f"🎭 *Роль:* {escape_md(role)}\n"
                f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                f"🏆 *Трофеїв:* {escape_md(str(coins))}\n"
                f"🥇 *Місце:* \\#{escape_md(str(rank))}\n"
                f"👑 VIP: {'✅' if db.check_vip(target_id) else '❌'}  "
                f"🚀 Буст: {'✅' if db.check_boost(target_id) else '❌'}  "
                f"🛡 Захист: {'✅' if db.check_shield(target_id) else '❌'}\n"
                f"✉️ *Повідомлень:* `{msgs}`\n"
                f"🃏 *Колекція:* `{collected}/{total}`\n"
                f"🔥 *Стрік:* `{streak}` дн\\.\n"
                f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                f"🎖 *Нагороди:*\n{ach_str}"
            )
            try:
                photos = await bot.get_user_profile_photos(target_id, limit=1)
                if photos.total_count > 0:
                    await message.answer_photo(photos.photos[0][-1].file_id, caption=caption, parse_mode="MarkdownV2")
                    return
            except Exception:
                pass
            await message.answer(caption, parse_mode="MarkdownV2")

        elif cmd == "гравці":
            page      = int(text_lower[1]) if len(text_lower) > 1 else 1
            per_page  = 20
            users     = db.get_all_users_paged(page, per_page)
            total     = db.get_total_players()
            tot_pages = (total + per_page - 1) // per_page
            if not users:
                return await message.reply("❌ Порожньо\\.", parse_mode="MarkdownV2")
            res = f"📋 *ГРАВЦІ \\(стор\\. {escape_md(str(page))}/{escape_md(str(tot_pages))}\\):*\n\n"
            for u in users:
                res += f"`{u[0]}` — {escape_md(u[1])} — {escape_md(str(u[2]))} 🏆\n"
            if page < tot_pages:
                res += f"\n➡️ `гравці {page+1}`"
            await message.answer(res[:4096], parse_mode="MarkdownV2")

        elif cmd == "скинути" and len(text_lower) > 1:
            db.reset_coins(int(text_lower[1]))
            await message.reply("✅ Трофеї скинуто до 0\\.", parse_mode="MarkdownV2")

        elif cmd == "розсилка" and len(original_parts) > 1:
            broadcast_text = " ".join(original_parts[1:])
            users  = db.get_all_users()
            sent   = 0
            failed = 0
            for user in users:
                try:
                    await bot.send_message(user[0], broadcast_text)
                    sent += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    failed += 1
            await message.reply(
                f"📢 Розсилка завершена\\!\n✅ *{escape_md(str(sent))}* надіслано\n❌ *{escape_md(str(failed))}* не вдалося",
                parse_mode="MarkdownV2"
            )

        elif cmd == "написати" and len(original_parts) > 2:
            try:
                target_id = int(original_parts[1])
                dm_text   = " ".join(original_parts[2:])
                await bot.send_message(target_id, dm_text)
                await message.reply("✅ Повідомлення надіслано\\.", parse_mode="MarkdownV2")
            except Exception as e:
                await message.reply(f"❌ Не вдалося: {escape_md(str(e))}", parse_mode="MarkdownV2")

        elif cmd == "інфо":
            total = db.get_total_players()
            stats = db.get_global_stats()
            await message.reply(
                f"🤖 *ІНФО БОТА*\n"
                f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                f"👥 Гравців: *{escape_md(str(total))}*\n"
                f"🏆 Трофеїв у грі: *{escape_md(str(stats['total_coins']))}*\n"
                f"🃏 Карток: *{escape_md(str(stats['total_cards']))}*\n"
                f"⏳ Кулдаун: *{escape_md(str(GLOBAL_COOLDOWN))} сек*\n"
                f"🟢 Статус: *{'Активний' if BOT_ACTIVE else 'Зупинено'}*",
                parse_mode="MarkdownV2"
            )

        elif cmd == "допомога":
            await message.reply(
                "🛠 *КОМАНДИ АДМІНА*\n"
                "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                "`стоп` / `старт` — бот вкл/викл\n"
                "`кд <сек>` — кулдаун картки\n"
                "`кд_казино <сек>` — кулдаун казино\n"
                "`шанс_казино <айді|відповідь> <%>` — шанс виграшу гравця\n"
                "`інфо` — статистика бота\n\n"
                "`профіль <айді|відповідь>`\n"
                "`гравці [стор]`\n"
                "`видати <айді|всім> <к-сть>`\n"
                "`забрати <айді|всіх> <к-сть>`\n"
                "`скинути <айді>`\n\n"
                "`нагородити <айді|відповідь> <текст>`\n"
                "`зняти <айді> <номер>`\n"
                "`віп <айді|відповідь> <днів>`\n"
                "`зняти_віп <айді>`\n"
                "`буст <айді|відповідь> <годин>`\n\n"
                "`написати <айді> <текст>`\n"
                "`розсилка <текст>`",
                parse_mode="MarkdownV2"
            )

        elif cmd == "база" and uid == MY_ID:
            users = db.get_all_users()
            res   = "📊 ГРАВЦІ:\n" + "\n".join([f"{u[0]}: {u[1]}" for u in users])
            await message.answer(res[:4000])

    except Exception as e:
        await message.reply(f"❌ Помилка адмінки: {escape_md(str(e))}", parse_mode="MarkdownV2")


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
