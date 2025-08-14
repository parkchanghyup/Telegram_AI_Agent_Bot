import os
import logging
import json
from logging.handlers import RotatingFileHandler

def load_prompt(file_name: str, base_dir: str = None) -> str:
    """프롬프트 파일을 로드합니다."""
    if base_dir is None:
        # base_dir가 제공되지 않으면, 이 파일의 위치를 기준으로 'prompt' 디렉토리를 설정
        base_dir = os.path.join(os.path.dirname(__file__), "prompt")
    
    prompt_path = os.path.join(base_dir, file_name)
    
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"프롬프트 파일({file_name})을 찾을 수 없습니다. 검색 경로: {prompt_path}") from exc

def load_config(file_path: str) -> dict:
    """JSON 설정 파일을 로드합니다."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning(f"{file_path} 파일을 찾을 수 없습니다.")
        return {}
    except json.JSONDecodeError:
        logging.error(f"{file_path} 파일의 형식이 올바르지 않습니다.")
        return {}

def truncate_for_log(text: str, length: int = 200) -> str:
    """로그 출력을 위해 텍스트를 자릅니다."""
    if text is None:
        return ''
    text = str(text)
    return text if len(text) <= length else text[:length] + '…'

def setup_file_logger(log_dir: str = 'logs', log_file: str = 'bot.log'):
    """파일 기반 로거를 설정합니다."""
    os.makedirs(log_dir, exist_ok=True)
    root_logger = logging.getLogger()
    if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        log_path = os.path.join(log_dir, log_file)
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
