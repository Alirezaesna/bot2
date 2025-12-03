import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.error import BadRequest

# --- تنظیمات پیکربندی ---
# توکن جدید خود را اینجا قرار دهید
TOKEN = "7579481172:AAH3TPAeUJQizs5LAcNee0Bb1pq5UUnqFlI" 

# آیدی کانال (حتما باید ربات در این کانال ادمین باشد تا بتواند عضویت را چک کند)
CHANNEL_USERNAME = "@Bikalammusicworld"

# لیست آیدی ادمین‌ها
ADMIN_IDS = [5231734946, 7845217738]

# تنظیمات آنتی اسپم (حداکثر 1 پیام در هر 2 ثانیه)
SPAM_LIMIT_SECONDS = 10
user_last_message_time = {}

# لاگینگ برای دیباگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- توابع کمکی ---

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بررسی عضویت کاربر در کانال"""
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        # وضعیت‌های مورد قبول: سازنده، ادمین، عضو
        if member.status in ['creator', 'administrator', 'member']:
            return True
    except BadRequest:
        logging.warning(f"ربات هنوز در کانال {CHANNEL_USERNAME} ادمین نیست یا کانال اشتباه است.")
        return False # فرض بر عدم عضویت در صورت خطا
    except Exception as e:
        logging.error(f"Error checking subscription: {e}")
    return False

def is_spam(user_id: int) -> bool:
    """بررسی نرخ ارسال پیام برای جلوگیری از اسپم"""
    current_time = time.time()
    last_time = user_last_message_time.get(user_id, 0)
    
    if current_time - last_time < SPAM_LIMIT_SECONDS:
        return True
    
    user_last_message_time[user_id] = current_time
    return False

# --- هندلرها ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if is_spam(user.id):
        await update.message.reply_text("⛔️ لطفاً پیام‌ها را آرام‌تر ارسال کنید.")
        return

    # بررسی عضویت اجباری
    is_member = await check_subscription(user.id, context)
    if not is_member:
        keyboard = [[InlineKeyboardButton("عضویت در کانال 🎵", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
                    [InlineKeyboardButton("عضو شدم ✅", callback_data="check_join")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"سلام {user.first_name} عزیز! 👋\n\n"
            f"برای استفاده از ربات، ابتدا باید در کانال موسیقی ما عضو شوید.",
            reply_markup=reply_markup
        )
        return

    # نمایش منوی اصلی
    keyboard = [
        [InlineKeyboardButton("🎹 درخواست موزیک", callback_data='req_music')],
        [InlineKeyboardButton("📩 انتقادات و پیشنهادات", callback_data='feedback')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "به ربات موزیک خوش آمدید! 🎧\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # دکمه بررسی عضویت
    if query.data == "check_join":
        is_member = await check_subscription(user_id, context)
        if is_member:
            await query.message.delete() # حذف پیام قفل عضویت
            await start(update, context) # نمایش منوی اصلی
        else:
            await query.answer("❌ شما هنوز عضو کانال نشده‌اید!", show_alert=True)
        return

    # سایر دکمه‌ها
    if query.data == 'req_music':
        context.user_data['state'] = 'WAITING_MUSIC'
        await query.edit_message_text("🎵 لطفاً نام آهنگ، خواننده یا بخشی از متن موزیک درخواستی خود را بنویسید:")
    
    elif query.data == 'feedback':
        context.user_data['state'] = 'WAITING_FEEDBACK'
        await query.edit_message_text("✍️ لطفاً انتقاد یا پیشنهاد خود را ارسال کنید:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    state = context.user_data.get('state')

    if is_spam(user.id):
        return # نادیده گرفتن پیام‌های رگباری

    # اگر کاربر وضعیتی ندارد (روی دکمه‌ها کلیک نکرده)
    if not state:
        await start(update, context)
        return

    # بررسی مجدد عضویت قبل از انجام عملیات
    if not await check_subscription(user.id, context):
        await start(update, context)
        return

    # آماده‌سازی گزارش برای ادمین‌ها
    msg_type = "نامشخص"
    if state == 'WAITING_MUSIC':
        msg_type = "🎵 درخواست موزیک"
        response_text = "✅ درخواست موزیک شما ثبت شد و به ادمین‌ها ارسال گردید."
    elif state == 'WAITING_FEEDBACK':
        msg_type = "📩 پیشنهاد/انتقاد"
        response_text = "✅ پیام شما دریافت شد. ممنون از نظرات شما!"

    admin_report = (
        f"⚠️ **پیام جدید** ({msg_type})\n\n"
        f"👤 کاربر: {user.first_name} (ID: `{user.id}`)\n"
        f"🆔 یوزرنیم: @{user.username if user.username else 'ندارد'}\n\n"
        f"📝 متن پیام:\n{text}"
    )

    # ارسال برای ادمین‌ها
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_report, parse_mode='Markdown')
        except Exception as e:
            logging.error(f"نمیتوان پیام را به ادمین {admin_id} فرستاد. خطا: {e}")

    # پاک کردن وضعیت کاربر و پاسخ به او
    context.user_data['state'] = None
    await update.message.reply_text(response_text)
    
    # بازگشت به منوی اصلی
    time.sleep(1)
    await start(update, context)

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot is running...")
    application.run_polling()
