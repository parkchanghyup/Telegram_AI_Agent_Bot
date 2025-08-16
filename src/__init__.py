import json
import os
from .llm_factory import LLMFactory

# llm_config.json 파일 경로 설정
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
llm_config_path = os.path.join(project_root, 'llm_config.json')

# 설정 파일 로드
try:
    with open(llm_config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
except FileNotFoundError:
    config_data = {}

# LLMFactory 인스턴스 생성
llm_factory_instance = LLMFactory(config_data)

def get_llm_factory():
    return llm_factory_instance

# 다른 모듈에서 쉽게 임포트할 수 있도록 설정
__all__ = ['get_llm_factory']
