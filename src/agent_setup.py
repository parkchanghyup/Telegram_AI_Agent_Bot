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

async def setup_agent_and_servers(available_servers=None):
    """MCP 서버와 AI 에이전트를 설정합니다.
    
    Args:
        available_servers (List[Dict]): 연결 확인된 서버들의 설정 리스트.
                                       None인 경우 설정 파일에서 모든 서버를 로드합니다.
    """
    mcp_servers = []
    server_names = []  # 서버 이름 저장용
    
    # LLM 설정 로드
    llm_config = load_llm_config()
    if not llm_config:
        return None, [], []

    # LLMFactory 인스턴스 생성
    llm_factory = LLMFactory(llm_config)
    
    # 사용할 서버 설정 결정
    if available_servers is not None:
        # 연결 확인된 서버들만 사용
        server_configs = [s['config'] for s in available_servers]
        print(f"🔍 연결 확인된 {len(server_configs)}개 서버로 초기화합니다.")
    else:
        # 기본 동작: 설정 파일에서 모든 서버를 로드
        config = load_mcp_config()
        server_configs = config.get('mcpServers', [])
        print(f"🔍 설정 파일의 {len(server_configs)}개 서버로 초기화합니다.")

    for server_config in server_configs:
        server_name = server_config.get('name')
        if not server_name:
            logging.warning("MCP 서버 설정에 'name' 필드가 없습니다. 건너뜁니다.")
            continue
            
        if "url" in server_config:
            logging.info(f"MCP 서버 준비: name={server_name}, url={server_config['url']}")
            
            # 헤더 설정 (인증 등)
            params = {
                "url": server_config["url"],
                "timeout": 30.0,  # 연결 타임아웃을 30초로 설정
                "request_timeout": 120.0 # 요청 타임아웃을 120초로 설정
            }
            if "headers" in server_config:
                params["headers"] = server_config["headers"]
            
            server = MCPServerStreamableHttp(
                params=params,
                cache_tools_list=True,
                client_session_timeout_seconds=60.0
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
                    "shell": True, # 셸을 통해 명령 실행
                    "request_timeout": 60.0 # 요청 타임아웃을 120초로 설정
                },
                cache_tools_list=True,
                client_session_timeout_seconds=60.0
            )
        
        try:
            # 서버 연결 시도
            await server.connect()
            if available_servers is not None:
                print(f"✅ MCP 서버 연결 성공 (사전 확인됨): name={server_name}")
            else:
                logging.info(f"MCP 서버 연결 성공: name={server_name}")
            mcp_servers.append(server)
            server_names.append(server_name)  # 서버 이름도 함께 저장
        except Exception as e:
            # 이미 연결 확인된 서버들의 경우 연결 실패를 더 심각하게 처리
            if available_servers is not None:
                print(f"⚠️ 사전 확인된 MCP 서버 연결 실패: name={server_name}, error={str(e)}")
                print(f"   서버 상태가 변경되었을 수 있습니다.")
            else:
                # Streamable HTTP 에러는 warning 레벨로 낮춤
                if "Streamable HTTP" in str(e) or "Transport" in str(e):
                    logging.warning(f"MCP 서버 연결 실패 (일시적): name={server_name}, error={str(e)}")
                else:
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
