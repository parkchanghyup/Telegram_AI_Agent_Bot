import logging
import json
import os
from agents.mcp import MCPServerStreamableHttp, MCPServerStdio
from agents.agent import Agent
from .llm_factory import LLMFactory
from .utils import load_prompt

async def setup_agent_and_servers():
    """MCP 서버와 AI 에이전트를 설정합니다."""
    mcp_servers = []

    # 프로젝트 루트 경로 설정
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # LLM 설정 로드
    llm_config_path = os.path.join(project_root, 'llm_config.json')
    try:
        with open(llm_config_path, 'r', encoding='utf-8') as f:
            llm_config = json.load(f)
    except FileNotFoundError:
        logging.error(f"{llm_config_path} 파일을 찾을 수 없습니다.")
        return None, []
    
    # LLMFactory 인스턴스 생성
    llm_factory = LLMFactory(llm_config)
    
    # mcp_config.json 파일 경로를 프로젝트 루트 기준으로 설정
    mcp_config_path = os.path.join(project_root, 'mcp_config.json')

    try:
        with open(mcp_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        logging.warning(f"{mcp_config_path} 파일을 찾을 수 없어 MCP 서버 없이 실행합니다.")
        config = {}

    for server_name, server_config in config.get('mcpServers', {}).items():
        if "url" in server_config:
            logging.info(f"MCP 서버 준비: name={server_name}, url={server_config['url']}")
            server = MCPServerStreamableHttp(
                params={"url": server_config["url"]},
                cache_tools_list=True
            )
        else:
            logging.info(f"MCP 서버 준비: name={server_name}, command={server_config.get('command')}, args={server_config.get('args', [])}")
            
            # args에 포함된 스크립트 경로를 프로젝트 루트 기준으로 변환
            args = server_config.get("args", [])
            for i, arg in enumerate(args):
                # 'src/'로 시작하는 경로를 프로젝트 루트 기준으로 변경
                if arg.startswith('src/'):
                    args[i] = os.path.join(project_root, arg)

            server = MCPServerStdio(
                params={
                    "command": server_config.get("command"),
                    "args": args,
                    "cwd": project_root # 작업 디렉토리를 프로젝트 루트로 설정
                },
                cache_tools_list=True
            )
        
        await server.connect()
        logging.info(f"MCP 서버 연결 성공: name={server_name}")
        mcp_servers.append(server)

    # Load the universal prompt from file
    prompt_base_dir = os.path.join(os.path.dirname(__file__), "prompt")
    INSTRUCTIONS = load_prompt("prompt.txt", prompt_base_dir)

    # Create single main agent with all MCP servers and a versatile model
    main_agent = Agent(
        name="Main Agent",
        instructions=INSTRUCTIONS,
        model=llm_factory.get_model(),  # LLMFactory를 통해 모델 인스턴스 가져오기
        mcp_servers=mcp_servers  # Attach all MCP servers to this single agent
    )

    logging.info("AI 에이전트 및 MCP 서버가 성공적으로 설정되었습니다.")

    return main_agent, mcp_servers
