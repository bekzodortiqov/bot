import logging
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder,ContextTypes,CommandHandler,ConversationHandler,MessageHandler,filters,CallbackQueryHandler
import dotenv
import os
import httpx
import re

dotenv.load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_API = os.getenv("API")

def format_gpa_message(data: dict) -> str:
    lines = explained = []

    lines.append("📊 *INS GPA Results*\n")

    for i, subject in enumerate(data["table"], start=1):
        name = subject["subject"]
        credit = subject["credit"]
        grade = subject["grade"]

        grade_text = grade if grade.lower() != "none" else "—"

        lines.append(
            f"*{i}. {name}*\n"
            f"   • Credit: `{credit}`\n"
            f"   • Grade: `{grade_text}`\n"
        )

    lines.append("──────────────")
    lines.append(f"🎓 *Total Credits:* `{data['credits']}`")
    lines.append(f"⭐ *GPA:* `{data['gpa_score']}`")

    return "\n".join(lines)



INS_results_btn = InlineKeyboardMarkup(
    [[InlineKeyboardButton("INS results", callback_data="INS results")]]
)
async def get_user_info(telegram_id: str):
    payload = {
        "telegram_id": str(telegram_id)
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{BASE_API}/user-info",
            json=payload
        )

    return response


async def get_gpa_api(telegram_id: str, studentId: str, password: str):
    payload = {
        "telegram_id": str(telegram_id),
        "studentId": studentId,
        "password": password
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{BASE_API}/get-GPA-table",
            json=payload
        )

    return response


STUDENT_ID, PASSWORD = range(2)

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    result = await get_user_info(user_id)
    print(result)
    print(result.text)
    if result.status_code ==403:

        await update.message.reply_text(
    "🔐 *Login required*\n\n"
    "Please enter your *Student ID* (example: `U1801122`).\n\n"
    "This helps us securely retrieve your GPA from the INS system.",
    parse_mode="Markdown"
)

        return STUDENT_ID
        
       
        

    else:
        data = result.json()
        student_id = data.get("student_id")
        password = data.get("password")
        context.user_data["student_id"] = student_id
        context.user_data["password"] = password

        await update.message.reply_text(f"👋 Hello, {student_id}\nTo view your INS GPA results, please click the button below.",
                                        reply_markup=INS_results_btn)


async def get_student_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["student_id"] = id1=update.message.text

    if not re.fullmatch(r"[Uu]\d{7}", id1):
                
        await update.message.reply_text("studentId must start with 'U' or 'u' followed by 7 digits")
        return STUDENT_ID  
            
    await update.message.reply_text(
    "🔑 *INS Password*\n\n"
    "Please enter your INS password so we can securely fetch your GPA from the INS system.\n\n"
    "🔒 We use your password only for this request. "
    "Without it, the system does not allow GPA access.",
    parse_mode="Markdown"
)

    return PASSWORD


async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_id = context.user_data["student_id"]
    password = update.message.text
    if len(password) < 8:
        await update.message.reply_text("Password must be at least 8 characters long")
        return PASSWORD

    if not re.search(r"[A-Z]", password):
        await update.message.reply_text("Password must contain at least one uppercase letter")
        return PASSWORD
    if not re.search(r"\d", password):
        await update.message.reply_text("Password must contain at least one number")
        return PASSWORD
    else:
        await update.message.reply_text("Please wait!... ⏳\nWe are checking your login and password!\nIt might take up to 1 minut!")
        response = await get_gpa_api(update.effective_user.id,student_id,password)
        
        data = response.json()
        if data["status_code"] == 403:
            await update.message.reply_text("Id or password is incorrect please fill it correctly!")
            await update.message.reply_text(
            "Enter your student ID:"
            )
            return STUDENT_ID
        
        if response.status_code == 422:
            await update.message.reply_text(response.text["detail"])
            await update.message.reply_text(
            "Enter your student ID:"
            )
            return STUDENT_ID

        context.user_data["student_id"] = student_id
        context.user_data["password"] = password
        if response.status_code == 200:
            formatted_text = format_gpa_message(data)
            await update.message.reply_text(formatted_text,parse_mode = "Markdown")

            await update.message.reply_text("For getting GPA results click INS results button!",reply_markup=INS_results_btn)
        else:
            await update.message.reply_text("Something gone wrong please try again!\nPlease enter your student Id")
            
    return ConversationHandler.END

    


async def getting_gpa(update:Update,context:ContextTypes.DEFAULT_TYPE,):
    query = update.callback_query
    await query.answer()
 
    studentId = context.user_data.get("student_id")
    password = context.user_data.get("password")

    if not studentId or not password:
        await query.message.reply_text(
            "Session expired. Please click /start again."
        )
        return 

    
    await query.edit_message_text(
    "Please wait… fetching GPA results ⏳ \nIt might take up to 1 minut"
    )

    result = await get_gpa_api(update.effective_user.id,studentId,password)
    if result.status_code ==200:
        data = result.json()
        formatted_text = format_gpa_message(data)
        await query.message.reply_text(formatted_text,parse_mode = "Markdown")

    await query.message.reply_text("For getting GPA results click INS results button!",reply_markup=INS_results_btn)




if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()

   # start_handler = CommandHandler('start',start)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            STUDENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_student_id)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
        },
        fallbacks=[],
)
    #application.add_handler(start_handler)
    application.add_handler(conv_handler)
    application.add_handler(
    CallbackQueryHandler(getting_gpa, pattern="^INS results$")
)

    application.run_polling()

