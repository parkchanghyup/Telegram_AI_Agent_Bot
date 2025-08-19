import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# 프로젝트 경로 설정
# =============================================================================
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC_DIR = os.path.dirname(__file__)
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')
PROMPT_DIR = os.path.join(SRC_DIR, 'prompt')

# 설정 파일 경로
LLM_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'llm_config.json')
MCP_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'mcp_config.json')

# =============================================================================
# 필수 환경 변수
# =============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# =============================================================================
# 추가 환경 변수
# =============================================================================
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
NAVER_NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"
NAVER_NEWS_DEFAULT_COUNT = 5




# =============================================================================
# Naver API 설정
# =============================================================================


# =============================================================================
# 네트워크 설정
# =============================================================================
DEFAULT_TIMEOUT = 15
ARTICLE_FETCH_TIMEOUT = 10
DEFAULT_USER_AGENT = 'Mozilla/5.0'

# =============================================================================
# 로깅 설정
# =============================================================================
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_ENCODING = 'utf-8'
DEFAULT_LOG_LEVEL = logging.INFO

# 뉴스 본문 추출용 CSS 선택자
ARTICLE_SELECTORS = [
    'article#dic_area',                 # 네이버 뉴스
    'div#newsct_article',               # 네이버 뉴스
    'div.article_body',                 # 일반적인 클래스
    'div#article_body',                 # ID 형식
    'div#articleBodyContents',          # 연합뉴스 등
    'div.article_view',                 # 여러 언론사
    'div.article-view-content-wrapper', # ITWorld
    'div#content',                      # 일반적인 ID
    'div.entry-content',                # 블로그/워드프레스 기반 사이트
    'div.post-content',                 # 블로그/워드프레스 기반 사이트
    'div#main-content',                 # 일반적인 ID
    'article',                          # 시맨틱 태그
    'main'                              # 시맨틱 태그
]

# 제거할 HTML 태그 목록
UNWANTED_HTML_TAGS = ['script', 'style', 'iframe', 'aside', 'footer', 'header', 'nav']

# =============================================================================
# 설정 로더 함수들
# =============================================================================
def load_llm_config():
    """LLM 설정을 로드합니다."""
    try:
        with open(LLM_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"{LLM_CONFIG_PATH} 파일을 찾을 수 없습니다.")
        return {}
    except json.JSONDecodeError:
        logging.error(f"{LLM_CONFIG_PATH} 파일 형식이 올바르지 않습니다.")
        return {}

def load_mcp_config():
    """MCP 설정을 로드합니다."""
    try:
        with open(MCP_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning(f"{MCP_CONFIG_PATH} 파일을 찾을 수 없어 MCP 서버 없이 실행합니다.")
        return {}
    except json.JSONDecodeError:
        logging.error(f"{MCP_CONFIG_PATH} 파일 형식이 올바르지 않습니다.")
        return {}

# LLM 설정 로드
llm_config = load_llm_config()
LLM_PROVIDER = llm_config.get("llm_provider", "openai")  # 기본값으로 openai 사용

# =============================================================================
# 설정 검증 함수
# =============================================================================
def validate_config():
    """필수 환경변수가 설정되었는지 확인합니다."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN 환경변수를 .env 파일에 설정해주세요.")

    if LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("LLM_PROVIDER가 'openai'일 경우 OPENAI_API_KEY를 설정해야 합니다.")
    elif LLM_PROVIDER not in ["ollama"]:
        raise ValueError(f"지원하지 않는 LLM_PROVIDER입니다: {LLM_PROVIDER}. 'openai' 또는 'ollama'를 사용하세요.")

def validate_naver_config():
    """Naver API 설정을 검증합니다."""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise ValueError("환경변수 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET가 설정되지 않았습니다.")

# =============================================================================
# 초기화
# =============================================================================
# 로그 디렉토리 생성
os.makedirs(LOGS_DIR, exist_ok=True)

# 기본 설정 검증
validate_config()
