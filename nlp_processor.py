# nlp_processor.py
import re
from datetime import datetime
from transformers import pipeline
import dateparser
from config import HF_TOKEN, NER_MODEL, NER_TOKENIZER, CLASSIFIER_MODEL, CLASSIFIER_TOKENIZER

# --- Pipeline NER --- 
try:
    ner_pipeline = pipeline(
        "ner",
        model=NER_MODEL,
        tokenizer=NER_TOKENIZER,
        aggregation_strategy="simple",
        token=HF_TOKEN
    )
except Exception as e:
    print("Error loading NER model:", e)
    ner_pipeline = None

# --- Pipeline for expense category classification ---
try:
    pipeline_category = pipeline(
        "text-classification",
        model=CLASSIFIER_MODEL,
        tokenizer=CLASSIFIER_TOKENIZER,
        token=HF_TOKEN
    )
except Exception as e:
    print("Error loading expense category classifier:", e)
    pipeline_category = None

# Fallback static mapping for expense categories
expense_categories_static = {
    "nhà": "Chi phí cố định",
    "điện": "Chi phí cố định",
    "ăn": "Tiêu dùng",
    "uống": "Tiêu dùng",
    "mua": "Tiêu dùng",
    "xem": "Giải trí",
    "chơi": "Giải trí",
    "đi": "Đi lại",
    "xe": "Đi lại",
    "tiêu": "Tiêu dùng"
}

def detect_intent(text: str) -> str:
    text_lower = text.lower()
    if text_lower.startswith("/profile"):
        return "profile"
    if "báo cáo" in text_lower:
        return "report"
    if "nhắc" in text_lower:
        return "reminder"
    if re.search(r'\d', text_lower) or any(kw in text_lower for kw in ["chi", "tiêu", "mua", "trả"]):
        return "expense_entry"
    return "unknown"

def convert_money_string_to_amount(money_str: str) -> dict:
    money_str = money_str.lower().strip()
    exchange_rates = {
        "usd": 23000,
        "eur": 27000,
        "gbp": 32000,
        "vnd": 1,
    }
    detected_currency = "vnd"
    for cur in exchange_rates.keys():
        if cur in money_str:
            detected_currency = cur
            money_str = money_str.replace(cur, "")
            break
    money_str = money_str.replace("đồng", "").strip()
    multiplier = 1
    if detected_currency == "vnd":
        if "triệu" in money_str:
            multiplier = 1_000_000
            money_str = money_str.replace("triệu", "").strip()
        elif "tỷ" in money_str:
            multiplier = 1_000_000_000
            money_str = money_str.replace("tỷ", "").strip()
        elif "nghìn" in money_str:
            multiplier = 1_000
            money_str = money_str.replace("nghìn", "").strip()
        elif "k" in money_str:
            multiplier = 1_000
            money_str = money_str.replace("k", "").strip()
    money_str = money_str.replace(".", "").replace(",", "")
    try:
        original_amount = float(money_str)
    except ValueError:
        original_amount = 0.0
    factor = exchange_rates.get(detected_currency, 1)
    amount_vnd = original_amount * multiplier * factor
    return {
        "original_amount": original_amount * multiplier,
        "amount_vnd": amount_vnd,
        "currency": detected_currency.upper()
    }

def extract_amount(text: str) -> dict:
    result = {"original_amount": 0, "amount_vnd": 0, "currency": "VND"}
    if ner_pipeline:
        entities = ner_pipeline(text)
        money_entities = [ent for ent in entities if "MONEY" in ent['entity'].upper()]
        if money_entities:
            money_str = " ".join(ent['word'] for ent in money_entities)
            conv = convert_money_string_to_amount(money_str)
            if conv["amount_vnd"] > 0:
                return conv
    # Fallback using regex
    amount_regex = re.compile(r'(\d+(?:[.,]\d+)*\s*(?:triệu|tỷ|nghìn|k|đồng|usd|eur|gbp|vnd)?)', re.IGNORECASE)
    match = amount_regex.search(text)
    if match:
        money_str = match.group(1)
        conv = convert_money_string_to_amount(money_str)
        return conv
    return result

def extract_date(text: str) -> str:
    date_obj = dateparser.parse(text, languages=['vi'])
    if date_obj:
        return date_obj.strftime('%Y-%m-%d')
    return datetime.now().strftime('%Y-%m-%d')

def extract_category(text: str) -> str:
    """
    If the category classification pipeline is available, use it; otherwise, fallback to static mapping.
    """
    if pipeline_category:
        try:
            prompt = (f"Giao dịch chi tiêu: \"{text}\".\n"
                      "Hãy xếp giao dịch này vào một trong các danh mục sau: Tiêu dùng, Đầu tư, Giải trí, Tiết kiệm, Đi lại, Chi phí cố định. "
                      "Chỉ trả về tên danh mục.")
            result = pipeline_category(prompt, max_new_tokens=10, truncation=True)
            predicted_category = result[0]['generated_text'].strip()
            return predicted_category
        except Exception as e:
            print("Error during category classification:", e)
    # Fallback static mapping
    text_lower = text.lower()
    for key, category in expense_categories_static.items():
        if key in text_lower:
            return category
    return "Khác"

def extract_expense_info(text: str) -> dict:
    intent = detect_intent(text)
    result = {"intent": intent, "original_text": text}
    if intent != "expense_entry":
        return result
    amount_info = extract_amount(text)
    category = extract_category(text)
    date_info = extract_date(text)
    missing_fields = []
    if amount_info["amount_vnd"] == 0:
        missing_fields.append("amount")
    complete = (len(missing_fields) == 0)
    result.update({
        "amount_info": amount_info,
        "category": category,
        "date": date_info,
        "complete": complete,
        "missing_fields": missing_fields
    })
    return result

def parse_profile_info(text: str) -> dict:
    """
    Parse the user's profile information from the /profile command.
    Expected format:
    /profile Tên: Huy, Thu nhập: 15,000,000 đồng, Ngân sách: 10,000,000 đồng, Mục tiêu tiết kiệm: 5,000,000 đồng, Mục tiêu sử dụng: Tiêu dùng, Đầu tư, Giải trí, Chi phí cố định, Tiết kiệm
    Uses a regex with named groups to extract values.
    """
    text = text.replace("/profile", "").strip()
    pattern = r"(?i)Tên:\s*(?P<name>.+?),\s*Thu\s+nhập:\s*(?P<income>.+?),\s*Ngân\s+sách:\s*(?P<budget>.+?),\s*Mục\s+tiêu\s+tiết\s+kiệm:\s*(?P<savings_goal>.+?)(?:,\s*Mục\s+tiêu\s+sử\s+dụng:\s*(?P<spending_targets>.+))?$"
    match = re.search(pattern, text)
    profile = {"name": None, "income": 0, "budget": 0, "savings_goal": 0, "spending_targets": ""}
    if match:
        profile["name"] = match.group("name").strip()
        income_str = match.group("income").strip()
        budget_str = match.group("budget").strip()
        savings_str = match.group("savings_goal").strip()
        spending_targets = match.group("spending_targets").strip() if match.group("spending_targets") else ""
        
        def parse_money(s):
            s = s.lower().replace("đồng", "").strip().replace(" ", "")
            try:
                return float(s.replace(",", ""))
            except Exception as e:
                print(f"Lỗi khi chuyển đổi '{s}':", e)
                return 0
        
        profile["income"] = parse_money(income_str)
        profile["budget"] = parse_money(budget_str)
        profile["savings_goal"] = parse_money(savings_str)
        profile["spending_targets"] = spending_targets
    else:
        print("Không thể phân tích thông tin cá nhân. Định dạng không hợp lệ.")
    return profile

if __name__ == "__main__":
    # Test expense extraction
    test_texts = [
        "ăn cá viên 200k",
        "đi chơi 100k",
        "đóng tiền nhà 3trieuej",
        "tiền nhà 3 triệu"
    ]
    for text in test_texts:
        info = extract_expense_info(text)
        print("Input:", text)
        print("Extracted info:", info)
        print("-" * 40)
    
    # Test profile extraction
    profile_input = "/profile Tên: Huy, Thu nhập: 15,000,000 đồng, Ngân sách: 10,000,000 đồng, Mục tiêu tiết kiệm: 5,000,000 đồng, Mục tiêu sử dụng: Tiêu dùng, Đầu tư, Giải trí, Chi phí cố định, Tiết kiệm"
    profile_info = parse_profile_info(profile_input)
    print("Profile info:", profile_info)
