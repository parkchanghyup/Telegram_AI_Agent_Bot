import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# LLM Provider: "openai" or "ollama"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Ollama Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "conandoyle247/jan-nano-4b-gguf")

# Model Names
QA_MODEL_NAME = os.getenv("QA_MODEL_NAME", "gpt-5-nano")
NAVER_MODEL_NAME = os.getenv("NAVER_MODEL_NAME", "gpt-5-mini")
TRIAGE_MODEL_NAME = os.getenv("TRIAGE_MODEL_NAME", "gpt-5-mini")


def validate_config():
    """필수 환경변수가 설정되었는지 확인합니다."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN 환경변수를 .env 파일에 설정해주세요.")

    if LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("LLM_PROVIDER가 'openai'일 경우 OPENAI_API_KEY를 설정해야 합니다.")
    elif LLM_PROVIDER not in ["ollama"]:
        raise ValueError(f"지원하지 않는 LLM_PROVIDER입니다: {LLM_PROVIDER}. 'openai' 또는 'ollama'를 사용하세요.")

validate_config()
