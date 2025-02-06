# spending_analysis.py
import pandas as pd
from datetime import datetime, timedelta
from database import Database
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, pipeline
from config import HF_TOKEN, GEN_MODEL, GEN_TOKENIZER, GEN_DEVICE

try:
    # Load configuration for the generation model
    config = AutoConfig.from_pretrained(
        GEN_MODEL,
        trust_remote_code=True,
        revision="main",
        token=HF_TOKEN
    )
    # Disable quantization config to avoid fp8-related errors.
    config.quantization_config = None

    model = AutoModelForCausalLM.from_pretrained(
        GEN_MODEL,
        config=config,
        trust_remote_code=True,
        revision="main",
        token=HF_TOKEN
    )
    tokenizer = AutoTokenizer.from_pretrained(
        GEN_TOKENIZER,
        trust_remote_code=True,
        revision="main",
        use_fast=False,
        token=HF_TOKEN
    )

    gen_pipeline = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        device=GEN_DEVICE  # Sử dụng thiết bị từ config: GPU (0) hoặc CPU (-1)
    )
except Exception as e:
    print("Error loading text generation model:", e)
    gen_pipeline = None

def analyze_spending(user_id, period="month"):
    """
    Analyze the user's spending data and generate a natural financial review in Vietnamese.
    """
    db = Database()
    today = datetime.now()

    # Xác định khoảng thời gian phân tích: day, week, month.
    if period == "day":
        start_date = today.strftime('%Y-%m-%d')
        end_date = start_date
    elif period == "week":
        start_week = today - timedelta(days=today.weekday())
        start_date = start_week.strftime('%Y-%m-%d')
        end_date = (start_week + timedelta(days=6)).strftime('%Y-%m-%d')
    else:  # Month hoặc mặc định.
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        if today.month == 12:
            next_month = today.replace(year=today.year+1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month+1, day=1)
        end_date = (next_month - timedelta(days=1)).strftime('%Y-%m-%d')

    # Lấy dữ liệu chi tiêu từ database
    expenses = db.get_expenses_by_period(user_id, start_date, end_date)
    if not expenses:
        return "Không có dữ liệu chi tiêu trong khoảng thời gian đã chọn."

    # Nếu dữ liệu không có cột 'currency', thêm mặc định là "VND".
    if len(expenses[0]) == 5:
        expenses = [row + ("VND",) for row in expenses]

    df = pd.DataFrame(expenses, columns=["id", "user_id", "date", "amount", "category", "currency"])
    total = df["amount"].sum()
    category_sum = df.groupby("category")["amount"].sum()

    # Xây dựng báo cáo chi tiết
    analysis_details = f"Từ {start_date} đến {end_date}, tổng chi tiêu của bạn là {total:,.0f} đồng.\n"
    if not category_sum.empty:
        analysis_details += "Chi tiêu theo từng danh mục:\n"
        for cat, amt in category_sum.items():
            percentage = (amt / total * 100) if total > 0 else 0
            analysis_details += f" - {cat}: {amt:,.0f} đồng ({percentage:.1f}%)\n"

    # Lấy thông tin profile của người dùng từ database
    profile = db.get_profile(user_id)
    if profile:
        name, income, budget, savings_goal, spending_targets = profile
        analysis_details += f"\nThông tin cá nhân:\n"
        analysis_details += f" - Ngân sách định sẵn: {budget:,.0f} đồng\n"
        analysis_details += f" - Thu nhập: {income:,.0f} đồng\n"
        analysis_details += f" - Mục tiêu tiết kiệm: {savings_goal:,.0f} đồng\n"
        analysis_details += f" - Mục tiêu sử dụng: {spending_targets}\n"
        if total > budget:
            analysis_details += "⚠️ Bạn đã vượt ngân sách định sẵn!\n"
        else:
            analysis_details += "✅ Chi tiêu của bạn nằm trong ngân sách định sẵn.\n"
    else:
        analysis_details += "\nChưa có thông tin cá nhân để so sánh.\n"

    # Tạo prompt cho mô hình sinh text
    prompt = (
        f"{analysis_details}\n"
        "Dựa trên các số liệu và thông tin cá nhân trên, hãy đưa ra nhận xét và lời khuyên cải thiện cách chi tiêu của bạn một cách tự nhiên, "
        "có cảm xúc và phù hợp với hoàn cảnh. Ví dụ:\n"
        "- Nếu chi tiêu vượt ngân sách, cảnh báo nhẹ nhàng và đề xuất giảm các khoản chi không cần thiết.\n"
        "- Nếu một danh mục chi tiêu quá cao, gợi ý tối ưu hóa hoặc cắt giảm.\n"
        "- Nếu chi tiêu ổn định, khen ngợi và động viên tiếp tục duy trì.\n"
    )
    
    print("Prompt:", prompt)
    
    if gen_pipeline:
        try:
            generated = gen_pipeline(prompt, max_new_tokens=100, num_return_sequences=1, truncation=True)
            commentary = generated[0]['generated_text']
            print("Generated commentary:", commentary)
        except Exception as e:
            commentary = "Có lỗi xảy ra khi tạo nhận xét tự động."
            print("Error during generation:", e)
    else:
        commentary = "Không thể tạo nhận xét tự động vì mô hình ngôn ngữ không sẵn sàng."
    
    return commentary

if __name__ == "__main__":
    result = analyze_spending("12345", period="month")
    print(result)
