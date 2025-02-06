import os
from dotenv import load_dotenv

# Load các biến môi trường từ file .env
load_dotenv()

# Hugging Face Token
HF_TOKEN = os.getenv("HF_TOKEN")

# Cấu hình cho NER pipeline
NER_MODEL = os.getenv("NER_MODEL")
NER_TOKENIZER = os.getenv("NER_TOKENIZER")

# Cấu hình cho expense category classifier
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL")
CLASSIFIER_TOKENIZER = os.getenv("CLASSIFIER_TOKENIZER")

# Cấu hình cho text-generation model (spending analysis)
GEN_MODEL = os.getenv("GEN_MODEL")
GEN_TOKENIZER = os.getenv("GEN_TOKENIZER")
GEN_DEVICE = int(os.getenv("GEN_DEVICE", -1))
