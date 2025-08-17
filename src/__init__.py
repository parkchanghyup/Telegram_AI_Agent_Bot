from .llm_factory import LLMFactory
from .config import load_llm_config

# 설정 파일 로드
config_data = load_llm_config()

# LLMFactory 인스턴스 생성
llm_factory_instance = LLMFactory(config_data) if config_data else None

def get_llm_factory():
    if llm_factory_instance is None:
        raise RuntimeError("LLMFactory를 초기화할 수 없습니다. llm_config.json 파일을 확인해주세요.")
    return llm_factory_instance

# 다른 모듈에서 쉽게 임포트할 수 있도록 설정
__all__ = ['get_llm_factory']
