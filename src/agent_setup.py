import logging
import json
import os
from agents.mcp import MCPServerStdio
from agents import Agent
from . import llm_factory
from .utils import load_prompt

async def setup_agent_and_servers():
    """MCP 서버와 AI 에이전트를 설정합니다."""
    mcp_servers = []
    mcp_server_map = {}
    
    # mcp_config.json 파일 경로를 프로젝트 루트 기준으로 설정
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    mcp_config_path = os.path.join(project_root, 'mcp_config.json')

    try:
        with open(mcp_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        logging.warning(f"{mcp_config_path} 파일을 찾을 수 없어 MCP 서버 없이 실행합니다.")
        config = {}

    for server_name, server_config in config.get('mcpServers', {}).items():
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
        mcp_server_map[server_name] = server

    # 프롬프트 로딩 시 src/utils.py의 load_prompt 사용
    prompt_base_dir = os.path.dirname(__file__)
    QA_AGENT_INSTRUCTIONS = load_prompt("qa_agent.txt", prompt_base_dir)
    NAVER_AGENT_INSTRUCTIONS = load_prompt("naver_agent.txt", prompt_base_dir)
    TRIAGE_AGENT_INSTRUCTIONS = load_prompt("triage_agent.txt", prompt_base_dir)

    qa_agent = Agent(
        name="QnA Agent",
        instructions=QA_AGENT_INSTRUCTIONS,
        model=llm_factory.get_qa_model()
    )

    naver_server = mcp_server_map.get('naver-search')
    naver_agent = Agent(
        name="Naver Search Agent",
        instructions=NAVER_AGENT_INSTRUCTIONS,
        model=llm_factory.get_naver_model(),
        mcp_servers=[naver_server] if naver_server else []
    )

    triage_agent = Agent(
        name="Triage Agent",
        instructions=TRIAGE_AGENT_INSTRUCTIONS,
        handoffs=[naver_agent, qa_agent],
        model=llm_factory.get_triage_model()
    )
    
    logging.info("AI 에이전트 및 MCP 서버가 성공적으로 설정되었습니다.")
    return triage_agent, mcp_servers
