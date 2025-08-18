import logging
import os
from agents.mcp import MCPServerStreamableHttp, MCPServerStdio
from agents.agent import Agent
from .llm_factory import LLMFactory
from .utils import load_prompt
from .config import (
    PROJECT_ROOT,
    PROMPT_DIR,
    load_llm_config,
    load_mcp_config
)

async def setup_agent_and_servers():
    """MCP 서버와 AI 에이전트를 설정합니다."""
    mcp_servers = []
    server_names = []  # 서버 이름 저장용
    
    # LLM 설정 로드
    llm_config = load_llm_config()
    if not llm_config:
        return None, [], []
    
    # LLMFactory 인스턴스 생성
    llm_factory = LLMFactory(llm_config)
    
    # MCP 설정 로드
    config = load_mcp_config()

    for server_config in config.get('mcpServers', []):
        server_name = server_config.get('name')
        if not server_name:
            logging.warning("MCP 서버 설정에 'name' 필드가 없습니다. 건너뜁니다.")
            continue
            
        if "url" in server_config:
            logging.info(f"MCP 서버 준비: name={server_name}, url={server_config['url']}")
            
            # 헤더 설정 (인증 등)
            params = {"url": server_config["url"]}
            if "headers" in server_config:
                params["headers"] = server_config["headers"]
            
            server = MCPServerStreamableHttp(
                params=params,
                cache_tools_list=True
            )
        else:
            logging.info(f"MCP 서버 준비: name={server_name}, command={server_config.get('command')}, args={server_config.get('args', [])}")
            
            # args에 포함된 스크립트 경로를 프로젝트 루트 기준으로 변환
            args = server_config.get("args", [])
            for i, arg in enumerate(args):
                # 'src/'로 시작하는 경로를 프로젝트 루트 기준으로 변경
                if arg.startswith('src/'):
                    args[i] = os.path.join(PROJECT_ROOT, arg)

            server = MCPServerStdio(
                params={
                    "command": server_config.get("command"),
                    "args": args,
                    "cwd": PROJECT_ROOT, # 작업 디렉토리를 프로젝트 루트로 설정
                    "env": os.environ, # 현재 환경 변수를 자식 프로세스에 전달
                    "shell": True # 셸을 통해 명령 실행
                },
                cache_tools_list=True
            )
        
        try:
            await server.connect()
            logging.info(f"MCP 서버 연결 성공: name={server_name}")
            mcp_servers.append(server)
            server_names.append(server_name)  # 서버 이름도 함께 저장
        except Exception as e:
            logging.error(f"MCP 서버 연결 실패: name={server_name}, error={str(e)}")
            logging.info(f"MCP 서버 '{server_name}' 없이 계속 진행합니다.")

    # Load the universal prompt from file
    INSTRUCTIONS = load_prompt("prompt.txt", PROMPT_DIR)

    # Create single main agent with all MCP servers and a versatile model
    main_agent = Agent(
        name="Main Agent",
        instructions=INSTRUCTIONS,
        model=llm_factory.get_model(),  # LLMFactory를 통해 모델 인스턴스 가져오기
        mcp_servers=mcp_servers  # Attach all MCP servers to this single agent
    )

    logging.info("AI 에이전트 및 MCP 서버가 성공적으로 설정되었습니다.")

    return main_agent, mcp_servers, server_names
