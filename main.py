import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler
from telegram.error import BadRequest, NetworkError

# ==========================================
# تنظیمات ربات (CONFIG)
# ==========================================

# توکن ربات شما
TOKEN = "7579481172:AAEf7Xc5tvlcymooqlBTJ0l0p3cLrzevMZo"

# آیدی عددی ادمین‌ها
ADMIN_IDS = [5231734946, 7845217738]

# آیدی کانال (حتما ربات باید در این کانال ادمین باشد تا بتواند عضویت را چک کند)
CHANNEL_USERNAME = "@Bikalammusicworld"

# تنظیمات آنتی اسپم (فاصله زمانی مجاز بین پیام‌ها به ثانیه)
FLOOD_LIMIT = 3 

# ==========================================
# وضعیت‌های گفتگو (STATES)
# ==========================================
WAITING_FOR_FEEDBACK, WAITING_FOR_MUSIC_REQUEST = range(2)

# ذخیره زمان آخرین پیام کاربر برای آنتی اسپم
user_last_message = {}

# تنظیمات لاگینگ برای دیباگ کردن (نمایش خطاها)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================================
# توابع کمکی (HELPERS)
# ==========================================

async def check_membership(user_id: int, bot) -> bool:
    """بررسی می‌کند که آیا کاربر در کانال عضو است یا خیر."""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        # وضعیت‌های مجاز: سازنده، ادمین، عضو
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except BadRequest:
        # اگر ربات در کانال ادمین نباشد یا کانال پیدا نشود
        logger.error(f"Bot is not admin in {CHANNEL_USERNAME} or channel not found.")
        return True # برای اینکه ربات متوقف نشود موقتا True برمی‌گرداند
    except Exception as e:
        logger.error(f"Error checking membership: {e}")
        return False

def is_spam(user_id: int) -> bool:
    """بررسی اسپم و حملات DDOS در سطح اپلیکیشن."""
    if user_id in ADMIN_IDS:
        return False # ادمین‌ها شامل آنتی اسپم نمی‌شوند
    
    current_time = time.time()
    last_time = user_last_message.get(user_id, 0)
    
    if current_time - last_time < FLOOD_LIMIT:
        return True
    
    user_last_message[user_id] = current_time
    return False

async def send_to_admins(update: Update, context: ContextTypes.DEFAULT_TYPE, message_type: str, content: str):
    """پیام را برای تمام ادمین‌ها ارسال می‌کند."""
    user = update.effective_user
    username = f"@{user.username}" if user.username else "ندارد"
    text_to_admin = (
        f"🔔 **پیام جدید!**\n\n"
        f"👤 فرستنده: {user.first_name} (ID: {user.id})\n"
        f"🆔 یوزرنیم: {username}\n"
        f"📂 نوع پیام: **{message_type}**\n\n"
        f"📝 متن:\n{content}"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text_to_admin)
        except Exception as e:
            logger.error(f"Failed to send message to admin {admin_id}: {e}")

# ==========================================
# هندلر خطاها (ERROR HANDLER)
# ==========================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """لاگ کردن خطاهایی که باعث کرش کردن ربات می‌شوند."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if isinstance(context.error, NetworkError):
        logger.error("⚠️ خطای اتصال به شبکه! لطفا پروکسی یا اتصال اینترنت سرور را بررسی کنید.")

# ==========================================
# هندلرها (HANDLERS)
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot.")
    
    if is_spam(user_id):
        await update.message.reply_text("⚠️ لطفا اسپم نکنید. کمی صبر کنید و مجدد تلاش کنید.")
        return ConversationHandler.END

    is_member = await check_membership(user_id, context.bot)
    if not is_member:
        keyboard = [
            [InlineKeyboardButton("عضویت در کانال 📢", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("عضو شدم ✅", callback_data="check_join")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"⛔️ برای استفاده از ربات ابتدا باید در کانال ما عضو شوید:\n{CHANNEL_USERNAME}",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    keyboard = [
        [KeyboardButton("درخواست موزیک"), KeyboardButton("انتقاد و پیشنهاد")],
        [KeyboardButton("راهنما")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 سلام! به ربات کانال موزیک خوش آمدید.\nلطفا یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    is_member = await check_membership(query.from_user.id, context.bot)
    if is_member:
        try:
            await query.message.delete()
        except BadRequest:
            pass
        await query.message.reply_text("✅ عضویت شما تایید شد. مجددا /start را بزنید.")
    else:
        await query.message.reply_text("❌ شما هنوز در کانال عضو نشده‌اید!")

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if is_spam(user_id):
        await update.message.reply_text("⚠️ لطفا آهسته تر پیام دهید.")
        return ConversationHandler.END

    if not await check_membership(user_id, context.bot):
        await update.message.reply_text(f"⛔️ لطفا ابتدا در کانال {CHANNEL_USERNAME} عضو شوید و مجدد /start بزنید.")
        return ConversationHandler.END

    if text == "درخواست موزیک":
        await update.message.reply_text(
            "🎹 نام آهنگ یا قسمتی از متن آن را بنویسید (برای کانال بی کلام):\n"
            "برای انصراف /cancel را بزنید."
        )
        return WAITING_FOR_MUSIC_REQUEST
        
    elif text == "انتقاد و پیشنهاد":
        await update.message.reply_text(
            "📝 لطفاً نظر، انتقاد یا پیشنهاد خود را بنویسید:\n"
            "برای انصراف /cancel را بزنید."
        )
        return WAITING_FOR_FEEDBACK
    
    elif text == "راهنما":
        await update.message.reply_text("این ربات برای ارتباط راحت‌تر شما با ادمین‌های کانال موزیک طراحی شده است.")
        return ConversationHandler.END
    
    # نکته: بخش else حذف شد چون با فیلتر Regex در entry_points دیگر به اینجا نمی‌رسد.
    return ConversationHandler.END

async def receive_music_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    # کنسل کردن عملیات اگر کاربر دکمه منو را زد
    if msg_text in ["درخواست موزیک", "انتقاد و پیشنهاد", "راهنما"]:
        await update.message.reply_text("⚠️ عملیات قبلی لغو شد. لطفا دوباره گزینه مورد نظر را انتخاب کنید.")
        return ConversationHandler.END

    await send_to_admins(update, context, "درخواست موزیک 🎵", msg_text)
    await update.message.reply_text("✅ درخواست شما برای ادمین‌ها ارسال شد.")
    return ConversationHandler.END

async def receive_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    if msg_text in ["درخواست موزیک", "انتقاد و پیشنهاد", "راهنما"]:
        await update.message.reply_text("⚠️ عملیات قبلی لغو شد. لطفا دوباره گزینه مورد نظر را انتخاب کنید.")
        return ConversationHandler.END

    await send_to_admins(update, context, "انتقاد/پیشنهاد 📩", msg_text)
    await update.message.reply_text("✅ پیام شما با موفقیت ثبت شد. ممنون از نظرتان!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد. از منوی پایین استفاده کنید.")
    return ConversationHandler.END

async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای پیام‌های ناشناس که دستور یا دکمه نیستند و در پروسه گفتگو هم نیستند."""
    user_id = update.effective_user.id
    if is_spam(user_id): return
    
    await update.message.reply_text("⛔️ لطفا فقط از دکمه‌های منوی پایین استفاده کنید.")

# ==========================================
# تابع اصلی (MAIN)
# ==========================================

def main():
    print("Bot is initializing...")
    
    try:
        application = Application.builder().token(TOKEN).build()

        # تعریف فیلتر دکمه‌ها برای جلوگیری از تداخل با متن پیام کاربر
        button_filter = filters.Regex('^(درخواست موزیک|انتقاد و پیشنهاد|راهنما)$')

        conv_handler = ConversationHandler(
            # فقط اگر متن دقیقاً یکی از دکمه‌ها بود وارد شو
            entry_points=[MessageHandler(button_filter, handle_choice)],
            states={
                WAITING_FOR_MUSIC_REQUEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_music_request)],
                WAITING_FOR_FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_feedback)],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            allow_reentry=True
        )

        application.add_error_handler(error_handler)
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(join_callback, pattern="^check_join$"))
        application.add_handler(conv_handler)
        
        # این هندلر فقط زمانی اجرا می‌شود که پیام کاربر نه دستور باشد، نه دکمه، و نه در وسط گفتگو باشد
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text))
        
        print("Bot is polling... (Press Ctrl+C to stop)")
        application.run_polling()
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    main()
