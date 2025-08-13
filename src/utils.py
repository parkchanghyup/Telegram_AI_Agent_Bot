import os
import logging

def load_prompt(file_name: str, base_dir: str = None) -> str:
    """프롬프트 파일 내용을 로드합니다."""
    try:
        if base_dir is None:
            base_dir = os.path.dirname(__file__)
        prompt_path = os.path.join(base_dir, "prompt", file_name)
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"프롬프트 파일({file_name})을 찾을 수 없습니다. 검색 경로: {prompt_path}") from exc

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
