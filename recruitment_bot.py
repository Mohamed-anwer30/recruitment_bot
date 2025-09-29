import logging
import os 
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
import gspread 
from typing import Dict, Any
from datetime import datetime

# 1. Configuration: Bot Token and Google Sheets
# Fetch values from Render's Environment Variables (for security and easy deployment)
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
SHEET_NAME = os.environ.get("SHEET_NAME") 
# يجب تعديل المسار هنا ليطابق مسار الملف السري الذي تم وضعه في Render Secret Files
SHEET_CREDENTIALS = '/etc/secrets/google_credentials.json' 

# 2. Setup Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 3. Conversation States (FSM)
GET_NAME, GET_GRADUATION, GET_LANGUAGE, GET_PHONE, CONFIRM_PHONE = range(5)


# 4. Google Sheets Integration Function
def save_to_sheet(data: Dict[str, Any]) -> bool:
    """Saves candidate data to a Google Sheet using gspread."""
    try:
        if not SHEET_NAME:
            logging.error("SHEET_NAME environment variable is not set.")
            return False
            
        # الاتصال الآن سيستخدم الملف السري من المسار الآمن
        gc = gspread.service_account(filename=SHEET_CREDENTIALS)
        spreadsheet = gc.open(SHEET_NAME)
        worksheet = spreadsheet.sheet1 
        
        # Data structure must match your Google Sheet columns
        row_data = [
            data.get('name', 'N/A'),
            data.get('graduation_year', 'N/A'),
            data.get('target_language', 'N/A'),
            data.get('phone', 'N/A'),
            data.get('submission_time', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "Pending HR WhatsApp Contact" 
        ]
        
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        logging.error(f"Error saving data to Google Sheet: {e}")
        return False

# --- Conversation Handler Functions (بدون تغيير) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    intro_message = (
        "👋 Welcome to the **Rapid-Hire Bot**! We specialize in connecting top talent with leading Multinational BPO Companies.\n\n"
        "We are actively recruiting for various Call Center & Customer Service roles across all languages.\n\n"
        "✨ **Featured Partners Include:** Teleperformance, Concentrix, and other reputable BPO firms.\n\n"
        "This quick process will help us assess your profile for job matching.\n\n"
        "To start, please enter your **Full Name**:"
    )
    await update.message.reply_text(intro_message, parse_mode='Markdown')
    context.user_data['application_data'] = {}
    return GET_NAME 

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_name = update.message.text
    context.user_data['application_data']['name'] = user_name
    await update.message.reply_text(
        f"Thank you, {user_name}.\n\nWhat is your **Graduation Year**? (e.g., 2024)"
    )
    return GET_GRADUATION

async def get_graduation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    grad_year = update.message.text
    if not grad_year.isdigit() or len(grad_year) != 4:
        await update.message.reply_text("Invalid year. Please enter a 4-digit number (e.g., 2024).")
        return GET_GRADUATION 
    context.user_data['application_data']['graduation_year'] = grad_year
    keyboard = [
        [InlineKeyboardButton("English", callback_data='lang_English'),
         InlineKeyboardButton("German", callback_data='lang_German')],
        [InlineKeyboardButton("Spanish", callback_data='lang_Spanish'),
         InlineKeyboardButton("French", callback_data='lang_French')],
        [InlineKeyboardButton("Italian", callback_data='lang_Italian')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Which **Target Language** are you applying for?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return GET_LANGUAGE

async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    selected_language = query.data.split('_')[1]
    context.user_data['application_data']['target_language'] = selected_language
    await query.edit_message_text(
        f"You selected: **{selected_language}**.\n\n"
        f"Now, please enter your **WhatsApp Phone Number** for contact (e.g., +2010xxxxxxxx):",
        parse_mode='Markdown'
    )
    return GET_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone_number = update.message.text
    context.user_data['application_data']['phone'] = phone_number
    keyboard = [
        [InlineKeyboardButton("✅ Yes, This is Correct", callback_data='phone_correct')],
        [InlineKeyboardButton("❌ Edit Number", callback_data='phone_edit')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"You entered: **{phone_number}**.\n\n"
        "Please confirm your number. This is crucial as the HR team will contact you via WhatsApp using this number.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return CONFIRM_PHONE

async def handle_phone_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == 'phone_correct':
        data_to_save = context.user_data['application_data']
        if save_to_sheet(data_to_save):
            logging.info(f"Application data saved for {data_to_save.get('name')}")
        else:
            logging.error("Failed to save data to Google Sheet.")
            
        final_message = (
            "🎉 **Application Received!**\n\n"
            "Your profile has been successfully submitted for review.\n\n"
            "➡️ **NEXT STEP (VITAL):** An HR representative will contact you on the WhatsApp number you provided "
            "(**{phone}**) **within 24 hours** to request a **1-minute self-introduction voice note** for final language assessment.\n\n"
            "This step is vital for your application to proceed. Thank you and good luck! 🚀"
        ).format(phone=data_to_save.get('phone'))
        await query.edit_message_text(final_message, parse_mode='Markdown')
        context.user_data.clear()
        return ConversationHandler.END
    elif query.data == 'phone_edit':
        await query.edit_message_text(
            "Please re-enter your **WhatsApp Phone Number** to ensure it is correct:"
        )
        return GET_PHONE 

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text(
        'Application process cancelled. You can restart anytime with /start.'
    )
    context.user_data.clear()
    return ConversationHandler.END

# ----------------------------------------------------------------------
# التعديل الحاسم لتوافق gunicorn: تغيير اسم الدالة الرئيسية وتعديل التشغيل
# ----------------------------------------------------------------------

# الدالة الجديدة التي يتم استدعاؤها في البداية
def build_application() -> Application:
    """Creates and configures the Telegram Application object."""
    
    if not BOT_TOKEN:
        logging.error("FATAL: BOT_TOKEN is not set. Cannot build application.")
        return None

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_GRADUATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_graduation)],
            GET_LANGUAGE: [CallbackQueryHandler(handle_language_selection, pattern='^lang_')],
            GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            CONFIRM_PHONE: [CallbackQueryHandler(handle_phone_confirmation, pattern='^phone_')],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    return application

# الدالة التي سيتم استهدافها بواسطة gunicorn مباشرة (عادة تكون 'application')
# هذا هو Object الرئيسي الذي يحتاجه gunicorn
application = build_application()

# ----------------------------------------------------------------------
# الدالة التي تشغل الـ Webhook عند التشغيل المباشر أو بواسطة gunicorn 
# ----------------------------------------------------------------------

if __name__ == '__main__':
    # هذا الجزء يعمل فقط عند التشغيل المحلي (للتجربة)
    if application:
        PORT = int(os.environ.get('PORT', '8080'))
        print(f"🤖 Bot is starting up locally on port {PORT}. (Use python -m http.server to test local webhooks)")
        
        # NOTE: For local testing, you would typically run polling here:
        # application.run_polling() 
        
        # For production, we assume gunicorn is running the 'application' object

# نهاية الكود. gunicorn سيستخدم المتغير 'application' مباشرة.
