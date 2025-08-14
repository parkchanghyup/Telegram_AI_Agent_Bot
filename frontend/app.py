import os
import sys
import asyncio
import json
from flask import Flask, render_template, request, jsonify
from agents.agent import Agent
from agents.run import Runner

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.llm_factory import LLMFactory
from src.utils import load_prompt, load_config

# Load configuration
config_path = os.path.join(os.path.dirname(__file__), '..', 'mcp_config.json')
config = load_config(config_path)

# Initialize LLM Factory
llm_factory = LLMFactory(config)

# Load prompts
prompt_base_dir = os.path.join(os.path.dirname(__file__), '..', 'src', 'prompt')
QA_AGENT_INSTRUCTIONS = load_prompt("qa_agent.txt", prompt_base_dir)
NAVER_AGENT_INSTRUCTIONS = load_prompt("naver_agent.txt", prompt_base_dir)
TRIAGE_AGENT_INSTRUCTIONS = load_prompt("triage_agent.txt", prompt_base_dir)

# Define Agent classes for the web UI
class QAAgent(Agent):
    def __init__(self, llm_factory):
        super().__init__(
            name="QnA Agent",
            instructions=QA_AGENT_INSTRUCTIONS,
            model=llm_factory.get_qa_model()
        )

class NaverAgent(Agent):
    def __init__(self, llm_factory):
        # Note: MCP server for Naver search is not connected in this web UI context.
        super().__init__(
            name="Naver Search Agent",
            instructions=NAVER_AGENT_INSTRUCTIONS,
            model=llm_factory.get_naver_model(),
            mcp_servers=[]
        )

class TriageAgent(Agent):
    def __init__(self, llm_factory, naver_agent, qa_agent):
        super().__init__(
            name="Triage Agent",
            instructions=TRIAGE_AGENT_INSTRUCTIONS,
            handoffs=[naver_agent, qa_agent],
            model=llm_factory.get_triage_model()
        )

# Instantiate agents
qa_agent_instance = QAAgent(llm_factory)
naver_agent_instance = NaverAgent(llm_factory)
triage_agent_instance = TriageAgent(llm_factory, naver_agent_instance, qa_agent_instance)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
async def chat():
    data = request.json
    user_message = data['message']

    try:
        # Run the triage agent asynchronously
        result = await Runner.run(triage_agent_instance, input=user_message)
        response_text = str(result.final_output)

    except Exception as e:
        print(f"Error during agent execution: {e}")
        response_text = "Sorry, an error occurred while processing your request."

    return jsonify({'response': response_text})

@app.route('/api/config', methods=['GET'])
def get_config():
    """MCP 설정을 반환합니다."""
    try:
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['POST'])
def save_config():
    """MCP 설정을 저장합니다."""
    try:
        new_config = request.json
        
        # 설정 파일에 저장
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(new_config, f, indent=4, ensure_ascii=False)
        
        # 전역 config 변수 업데이트
        global config
        config = new_config
        
        return jsonify({'success': True, 'message': 'Configuration saved successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
