import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from telegram.error import BadRequest

# ==========================================
# ⚙️ تنظیمات ربات (این بخش را ویرایش کنید)
# ==========================================

# 1. توکن جدید را اینجا قرار دهید
TOKEN = "YOUR_NEW_TOKEN_HERE"

# 2. آیدی عددی ادمین‌ها
ADMIN_IDS = [5231734946, 7845217738]

# 3. آیدی کانال (برای قفل عضویت اجباری)
# نکته: ربات باید در این کانال ادمین باشد
CHANNEL_ID = "@Bikalammusicworld"

# 4. تنظیمات آنتی اسپم (ثانیه)
SPAM_THRESHOLD = 2.0

# ==========================================
# 🔧 تنظیمات داخلی (تغییر ندهید)
# ==========================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# مراحل گفتگو
WAITING_INPUT = 1

# حافظه موقت آنتی اسپم
user_last_msg = {}

# ==========================================
# 🛡️ توابع کمکی و امنیتی
# ==========================================

def is_spam(user_id: int) -> bool:
    """بررسی می‌کند آیا کاربر در حال ارسال رگباری پیام است یا خیر"""
    current_time = time.time()
    last_time = user_last_msg.get(user_id, 0)
    
    if (current_time - last_time) < SPAM_THRESHOLD:
        return True
    
    user_last_msg[user_id] = current_time
    return False

async def check_subscription(user_id: int, bot) -> bool:
    """بررسی عضویت اجباری کاربر در کانال"""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        # وضعیت‌های Left و Kicked یعنی کاربر عضو نیست
        if member.status in ['left', 'kicked']:
            return False
        return True
    except BadRequest:
        # اگر ربات در کانال ادمین نباشد یا آیدی کانال غلط باشد، لاگ می‌اندازد
        # اما برای اینکه ربات از کار نیفتد، موقتا اجازه عبور می‌دهد
        logger.warning(f"⚠️ ربات هنوز در کانال {CHANNEL_ID} ادمین نیست.")
        return True 
    except Exception as e:
        logger.error(f"Error checking subscription: {e}")
        return True

async def get_main_menu():
    """کیبورد منوی اصلی"""
    keyboard = [
        [
            InlineKeyboardButton("🎵 درخواست موزیک", callback_data='req_music'),
            InlineKeyboardButton("📩 انتقاد و پیشنهاد", callback_data='feedback')
        ],
        [
            InlineKeyboardButton("📢 کانال ما", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==========================================
# 🎮 هندلرها (Logic)
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # بررسی آنتی اسپم
    if is_spam(user.id):
        return 

    # بررسی عضویت اجباری
    if not await check_subscription(user.id, context.bot):
        keyboard = [
            [InlineKeyboardButton("عضویت در کانال 🎵", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")]
        ]
        await update.message.reply_text(
            f"سلام {user.first_name} عزیز! 👋\n\n"
            f"🔒 برای استفاده از ربات، ابتدا باید در کانال **{CHANNEL_ID}** عضو شوید.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🎧 **به ربات موزیک خوش آمدید**\n\n"
        "چه کاری می‌توانم برایتان انجام دهم؟",
        reply_markup=await get_main_menu(),
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    # دکمه بررسی عضویت
    if query.data == "check_join":
        if await check_subscription(user.id, context.bot):
            await query.message.delete()
            await start(update, context)
        else:
            await query.answer("❌ هنوز عضو کانال نشده‌اید!", show_alert=True)
        return ConversationHandler.END

    if is_spam(user.id):
        await query.answer("⚠️ لطفاً آرام‌تر!", show_alert=True)
        return ConversationHandler.END

    # مدیریت منوها
    msg_text = ""
    if query.data == 'req_music':
        msg_text = "🎹 **درخواست موزیک**\n\nلطفاً نام آهنگ، خواننده یا بخشی از متن را ارسال کنید:"
        context.user_data['type'] = 'درخواست موزیک 🎵'
    
    elif query.data == 'feedback':
        msg_text = "✍️ **انتقاد یا پیشنهاد**\n\nپیام خود را بنویسید تا به دست ادمین‌ها برسد:"
        context.user_data['type'] = 'فیدبک 📩'

    # دکمه بازگشت
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data='cancel')]])
    
    await query.edit_message_text(text=msg_text, reply_markup=cancel_kb, parse_mode=ParseMode.MARKDOWN)
    return WAITING_INPUT

async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    msg_type = context.user_data.get('type', 'پیام')

    if is_spam(user.id):
        await update.message.reply_text("⛔️ لطفاً پیام‌ها را با فاصله زمانی ارسال کنید.")
        return WAITING_INPUT

    # ساخت متن گزارش برای ادمین
    admin_report = (
        f"🔔 **پیام جدید: {msg_type}**\n"
        f"➖➖➖➖➖➖➖➖\n"
        f"👤 نام: {user.first_name}\n"
        f"🔢 آیدی عددی: `{user.id}`\n"
        f"🆔 یوزرنیم: @{user.username if user.username else 'ندارد'}\n"
        f"➖➖➖➖➖➖➖➖\n\n"
        f"📝 **متن پیام:**\n{text}"
    )

    # ارسال برای همه ادمین‌ها
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_report, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"خطا در ارسال به ادمین {admin_id}: {e}")

    # تاییدیه به کاربر
    await update.message.reply_text(
        "✅ پیام شما با موفقیت دریافت و برای مدیران ارسال شد.",
        reply_markup=await get_main_menu()
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🏠 بازگشت به منوی اصلی:",
        reply_markup=await get_main_menu()
    )
    return ConversationHandler.END

# ==========================================
# 🚀 اجرای ربات
# ==========================================

if __name__ == '__main__':
    if TOKEN == "YOUR_NEW_TOKEN_HERE":
        print("❌ خطا: لطفاً توکن ربات را در خط 16 فایل جایگذاری کنید.")
        exit()

    application = ApplicationBuilder().token(TOKEN).build()

    # مدیریت مراحل گفتگو
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^(req_music|feedback|check_join)$')],
        states={
            WAITING_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input),
                CallbackQueryHandler(cancel, pattern='^cancel$')
            ],
        },
        fallbacks=[CommandHandler('start', start)]
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(conv_handler)
    # هندلر جداگانه برای دکمه "عضو شدم" در صورتی که خارج از استیت باشد
    application.add_handler(CallbackQueryHandler(button_handler, pattern='^check_join$'))

    print("✅ ربات با موفقیت روشن شد...")
    application.run_polling()
