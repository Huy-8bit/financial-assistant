# telegram_handler.py
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from datetime import datetime, timedelta
import logging

from nlp_processor import extract_expense_info, detect_intent, parse_profile_info
from spending_analysis import analyze_spending
from database import Database

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
db = Database()

def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat_id = update.message.chat_id
    user_id = str(user.id)
    db.add_user(user_id, chat_id)
    update.message.reply_text(
        "Chào bạn! Tôi là bot quản lý chi tiêu cá nhân thông minh.\n"
        "Hãy cập nhật thông tin cá nhân của bạn bằng lệnh /profile.\n"
        "Ví dụ: /profile Tên: Huy, Thu nhập: 15,000,000 đồng, Ngân sách: 10,000,000 đồng, Mục tiêu tiết kiệm: 5,000,000 đồng, Mục tiêu sử dụng: Tiêu dùng, Đầu tư, Giải trí, Chi phí cố định, Tiết kiệm.\n"
        "Sau đó, bạn có thể nhập giao dịch chi tiêu như: 'Hôm nay tôi đã chi 150,000 đồng cho ăn trưa'."
    )

def help_command(update: Update, context: CallbackContext):
    help_text = (
        "Hướng dẫn sử dụng bot:\n"
        "- /profile: Cập nhật thông tin cá nhân.\n"
        "- Nhập giao dịch chi tiêu bằng câu lệnh tự nhiên.\n"
        "- Bot sẽ tự động review và đưa ra lời khuyên sau mỗi giao dịch.\n"
        "- Các lệnh báo cáo: /report, /report_week, /report_month."
    )
    update.message.reply_text(help_text)

def profile(update: Update, context: CallbackContext):
    user = update.message.from_user
    user_id = str(user.id)
    text = update.message.text
    profile_data = parse_profile_info(text)
    if not profile_data.get("name"):
        update.message.reply_text("Không nhận diện được tên. Vui lòng nhập lại theo định dạng mẫu.")
        return
    db.add_profile(
        user_id,
        profile_data["name"],
        profile_data["income"],
        profile_data["budget"],
        profile_data["savings_goal"],
        profile_data["spending_targets"]
    )
    update.message.reply_text("Thông tin cá nhân của bạn đã được cập nhật.")

def handle_message(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat_id = update.message.chat_id
    user_id = str(user.id)
    text = update.message.text
    info = extract_expense_info(text)
    intent = info.get("intent", "unknown")
    
    if intent == "expense_entry":
        amount = info["amount_info"]["amount_vnd"]
        if amount > 50000000:
            update.message.reply_text("❗ Khoản chi này khá lớn! Bạn có chắc chắn rằng đây là khoản chi cần thiết không?")
        
        amount_info = info["amount_info"]
        amount_vnd = amount_info["amount_vnd"]
        original_amount = amount_info["original_amount"]
        currency = amount_info["currency"]
        category = info["category"]
        date_info = info["date"]
        db.add_expense(user_id, date_info, amount_vnd, category, currency)
        if currency != "VND":
            update.message.reply_text(
                f"Đã lưu chi tiêu: {amount_vnd:,.0f} đồng (tương đương {original_amount:,.0f} {currency}), loại: {category}, vào ngày {date_info}."
            )
        else:
            update.message.reply_text(
                f"Đã lưu chi tiêu: {amount_vnd:,.0f} đồng, loại: {category}, vào ngày {date_info}."
            )
        review_message = analyze_spending(user_id, period="month")
        update.message.reply_text(review_message)
    elif intent == "report":
        update.message.reply_text("Để xem báo cáo, hãy sử dụng các lệnh: /report, /report_week, /report_month.")
    elif intent == "reminder":
        update.message.reply_text("Lệnh nhắc nhở đã được nhận. Tôi sẽ nhắc bạn mỗi ngày tổng chi tiêu.")
    elif intent == "profile":
        profile(update, context)
    else:
        update.message.reply_text("Xin lỗi, tôi không hiểu yêu cầu của bạn. Vui lòng nhập lại hoặc dùng /help để được hỗ trợ.")

def review(update: Update, context: CallbackContext):
    user = update.message.from_user
    user_id = str(user.id)
    analysis_message = analyze_spending(user_id, period="month")
    update.message.reply_text("Nhận xét cách chi tiêu của bạn:\n" + analysis_message)

def report(update: Update, context: CallbackContext):
    user = update.message.from_user
    user_id = str(user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    total = db.get_total_expense_by_date(user_id, today)
    expenses = db.get_expenses_by_date(user_id, today)
    report_text = f"Báo cáo chi tiêu ngày {today}:\n"
    for expense in expenses:
        if len(expense) == 5:
            expense = expense + ("VND",)
        if expense[5] != "VND":
            report_text += f"- {expense[4]}: {expense[3]:,.0f} đồng ({expense[5]})\n"
        else:
            report_text += f"- {expense[4]}: {expense[3]:,.0f} đồng\n"
    report_text += f"Tổng cộng: {total:,.0f} đồng"
    update.message.reply_text(report_text)

def report_week(update: Update, context: CallbackContext):
    user = update.message.from_user
    user_id = str(user.id)
    today = datetime.now()
    start_week = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    end_week = (today + timedelta(days=6 - today.weekday())).strftime("%Y-%m-%d")
    expenses = db.get_expenses_by_period(user_id, start_week, end_week)
    total = sum(expense[3] for expense in expenses)
    report_text = f"Báo cáo chi tiêu tuần ({start_week} đến {end_week}):\n"
    for expense in expenses:
        report_text += f"- {expense[2]} - {expense[4]}: {expense[3]:,.0f} đồng\n"
    report_text += f"Tổng cộng: {total:,.0f} đồng"
    update.message.reply_text(report_text)

def report_month(update: Update, context: CallbackContext):
    user = update.message.from_user
    user_id = str(user.id)
    today = datetime.now()
    start_month = today.replace(day=1).strftime("%Y-%m-%d")
    if today.month == 12:
        next_month = today.replace(year=today.year+1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month+1, day=1)
    end_month = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
    expenses = db.get_expenses_by_period(user_id, start_month, end_month)
    total = sum(expense[3] for expense in expenses)
    report_text = f"Báo cáo chi tiêu tháng {today.month}/{today.year}:\n"
    for expense in expenses:
        report_text += f"- {expense[2]} - {expense[4]}: {expense[3]:,.0f} đồng\n"
    report_text += f"Tổng cộng: {total:,.0f} đồng"
    update.message.reply_text(report_text)

def daily_reminder(context: CallbackContext):
    bot = context.bot
    today = datetime.now().strftime("%Y-%m-%d")
    users = db.get_all_users()
    for user in users:
        user_id, chat_id = user
        total = db.get_total_expense_by_date(user_id, today)
        message = (
            f"Nhắc nhở: Hôm nay ({today}), bạn đã chi tiêu tổng cộng {total:,.0f} đồng.\n"
            "Hãy cân nhắc trước khi mua sắm thêm nhé!"
        )
        try:
            bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            logger.error(f"Lỗi khi gửi tin nhắc nhở đến chat_id {chat_id}: {e}")

def setup_dispatcher(dispatcher):
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("profile", profile))
    dispatcher.add_handler(CommandHandler("review", review))
    dispatcher.add_handler(CommandHandler("report", report))
    dispatcher.add_handler(CommandHandler("report_week", report_week))
    dispatcher.add_handler(CommandHandler("report_month", report_month))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
