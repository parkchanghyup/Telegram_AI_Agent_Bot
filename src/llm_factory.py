from agents import OpenAIChatCompletionsModel, AsyncOpenAI
from . import config

def create_llm_model(model_name: str):
    """설정에 따라 LLM 모델 인스턴스를 생성합니다."""
    if config.LLM_PROVIDER == "openai":
        return model_name  # The 'agents' library handles string model names for OpenAI
    
    if config.LLM_PROVIDER == "ollama":
        # Ollama의 경우, model_name을 config에서 직접 가져와 사용하거나,
        # 인자로 받은 model_name을 ollama 모델명으로 간주할 수 있습니다.
        # 여기서는 config에 정의된 OLLAMA_MODEL을 사용하도록 하겠습니다.
        return OpenAIChatCompletionsModel(
            model=config.OLLAMA_MODEL,
            openai_client=AsyncOpenAI(base_url=config.OLLAMA_BASE_URL)
        )
    
    raise ValueError(f"지원하지 않는 LLM_PROVIDER입니다: {config.LLM_PROVIDER}")

def get_qa_model():
    """Q&A 에이전트용 모델을 반환합니다."""
    return create_llm_model(config.QA_MODEL_NAME)

def get_naver_model():
    """네이버 에이전트용 모델을 반환합니다."""
    return create_llm_model(config.NAVER_MODEL_NAME)

def get_triage_model():
    """트리아지 에이전트용 모델을 반환합니다."""
    return create_llm_model(config.TRIAGE_MODEL_NAME)
