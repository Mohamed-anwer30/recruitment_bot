import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
import gspread 
from typing import Dict, Any
from datetime import datetime

# 1. Configuration: Bot Token and Google Sheets
BOT_TOKEN = "8312499716:AAEm3Kv-kAsXfEVKylSP4qL7YU1S8u9P8aY" 
SHEET_NAME = "Recruitment_Applications_Sheet"  # Your Google Sheet Name
SHEET_CREDENTIALS = 'google_credentials.json' # Your Service Account JSON file name

# 2. Setup Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 3. Conversation States (FSM) - The New Flow
GET_NAME, GET_GRADUATION, GET_LANGUAGE, GET_PHONE, CONFIRM_PHONE = range(5)

# 4. Google Sheets Integration Function
def save_to_sheet(data: Dict[str, Any]) -> bool:
    """Saves candidate data to a Google Sheet using gspread."""
    try:
        gc = gspread.service_account(filename=SHEET_CREDENTIALS)
        spreadsheet = gc.open(SHEET_NAME)
        worksheet = spreadsheet.sheet1 
        
        # Prepare the row data in the desired order
        row_data = [
            data.get('name', 'N/A'),
            data.get('graduation_year', 'N/A'),
            data.get('target_language', 'N/A'),
            data.get('phone', 'N/A'),
            data.get('submission_time', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "Pending HR WhatsApp Contact" # Voice Note Status (as it's collected off-platform)
        ]
        
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        logging.error(f"Error saving data to Google Sheet: {e}")
        return False

# --- Conversation Handler Functions ---

# 5. /start Command: The New Introduction
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the application process with a professional introduction."""
    
    intro_message = (
        "👋 Welcome to the **Rapid-Hire Bot**! We specialize in connecting top talent with leading Multinational BPO Companies.\n\n"
        "We are actively recruiting for various Call Center & Customer Service roles across all languages.\n\n"
        "✨ **Featured Partners Include:** Teleperformance, Concentrix, and other reputable BPO firms.\n\n"
        "This quick process will help us assess your profile for immediate job matching.\n\n"
        "To start, please enter your **Full Name**:"
    )
    
    await update.message.reply_text(intro_message, parse_mode='Markdown')
    context.user_data['application_data'] = {}
    return GET_NAME # Go to the next state: Get Name

# 6. GET_NAME state: Receives the name and asks for graduation year.
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the name and asks for the graduation year."""
    user_name = update.message.text
    context.user_data['application_data']['name'] = user_name
    
    await update.message.reply_text(
        f"Thank you, {user_name}.\n\nWhat is your **Graduation Year**? (e.g., 2024)"
    )
    return GET_GRADUATION

# 7. GET_GRADUATION state: Receives graduation year and asks for language selection.
async def get_graduation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves graduation year and asks for the target language."""
    grad_year = update.message.text
    if not grad_year.isdigit() or len(grad_year) != 4:
        await update.message.reply_text("Invalid year. Please enter a 4-digit number (e.g., 2024).")
        return GET_GRADUATION # Stay in the same state

    context.user_data['application_data']['graduation_year'] = grad_year

    # Language selection using Inline Keyboard
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

# 8. GET_LANGUAGE state: Handles language button click and asks for phone. (Callback Handler)
async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the language selection, saves it, and asks for the phone number."""
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

# 9. GET_PHONE state: Receives the phone and asks for confirmation.
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the phone number and asks for confirmation."""
    phone_number = update.message.text
    context.user_data['application_data']['phone'] = phone_number

    # Phone confirmation using Inline Keyboard
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

# 10. CONFIRM_PHONE state: Handles phone confirmation. (Callback Handler)
async def handle_phone_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the phone number confirmation or prompts for re-entry, and sends the final message."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'phone_correct':
        # 1. Save data to Google Sheet
        data_to_save = context.user_data['application_data']
        
        if save_to_sheet(data_to_save):
            logging.info(f"Application data saved for {data_to_save.get('name')}")
        else:
            logging.error("Failed to save data to Google Sheet.")
            
        # 2. Final HR message (The final requested step)
        final_message = (
            "🎉 **Application Received!**\n\n"
            "Your profile has been successfully submitted for review.\n\n"
            "➡️ **NEXT STEP (VITAL):** An HR representative will contact you on the WhatsApp number you provided "
            "(**{phone}**) **within 24 hours** to request a **1-minute self-introduction voice note** for final language assessment.\n\n"
            "This step is vital for your application to proceed. Thank you and good luck! 🚀"
        ).format(phone=data_to_save.get('phone'))
        
        await query.edit_message_text(final_message, parse_mode='Markdown')
        
        # 3. End the conversation
        context.user_data.clear()
        return ConversationHandler.END
    
    elif query.data == 'phone_edit':
        # Go back to GET_PHONE state logic (ask for number again)
        await query.edit_message_text(
            "Please re-enter your **WhatsApp Phone Number** to ensure it is correct:"
        )
        return GET_PHONE # Go back to the GET_PHONE state

# 11. Fallback function for cancellation or error
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text(
        'Application process cancelled. You can restart anytime with /start.'
    )
    context.user_data.clear()
    return ConversationHandler.END


# 12. Main Function to Run the Bot
def main() -> None:
    """Starts the bot and sets up the conversation handlers."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Define the Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_GRADUATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_graduation)],
            # Handles clicks for language selection buttons
            GET_LANGUAGE: [CallbackQueryHandler(handle_language_selection, pattern='^lang_')], 
            GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            # Handles clicks for phone confirmation buttons
            CONFIRM_PHONE: [CallbackQueryHandler(handle_phone_confirmation, pattern='^phone_')],
        },
        
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    
    print("🤖 Recruitment Bot is running...")
    application.run_polling(poll_interval=3.0)

if __name__ == '__main__':
    main()