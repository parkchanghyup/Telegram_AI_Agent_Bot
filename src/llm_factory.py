from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI
from .config import OPENAI_API_KEY

def get_main_model():
    from . import get_llm_factory
    factory = get_llm_factory()
    return factory.get_main_model()

class LLMFactory:
    def __init__(self, config_data: dict):
        # config_data에서 우선 가져오고, 없으면 openai로 설정
        self.provider = config_data.get("llm_provider", "openai").lower()
        
        self.model_name = config_data.get("model_name", "")

        if not self.model_name:
            raise ValueError("model_name is required")

        # Ollama base URL 설정
        ollama_base_url = config_data.get("ollama_base_url", "http://localhost:11434/v1")

        if self.provider == "openai":
            if not OPENAI_API_KEY:
                raise ValueError("LLM_PROVIDER가 'openai'일 경우 OPENAI_API_KEY를 설정해야 합니다.")
            self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        elif self.provider == "ollama":
            self.client = AsyncOpenAI(
                base_url=ollama_base_url,
                api_key="ollama"
            )
        else:
            raise ValueError(f"지원하지 않는 LLM_PROVIDER입니다: {self.provider}")

    def _create_model_instance(self, model_name):
        return OpenAIChatCompletionsModel(model=model_name, openai_client=self.client)

    def get_model(self):
        return self._create_model_instance(self.model_name)
