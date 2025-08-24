import logging
import os
import asyncio
import signal
import sys
from typing import List, Dict, Optional, Any, Tuple
from functools import partial

try:
    from agents.mcp import MCPServerStreamableHttp, MCPServerStdio
except ImportError:
    from mcp.server import MCPServerStreamableHttp, MCPServerStdio
from .config import PROJECT_ROOT, load_mcp_config

# 종료 핸들러 설정
def _cleanup_resources():
    """프로그램 종료 시 리소스 정리"""
    # 여기서는 특별히 할 일이 없음 - 이미 비동기 컨텍스트가 종료됨
    pass

# 시그널 핸들러
def _signal_handler(sig, frame):
    """시그널 핸들러"""
    _cleanup_resources()
    sys.exit(0)

# 시그널 핸들러 등록
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

async def check_server_connection(server_config: Dict) -> Dict[str, Any]:
    """
    단일 MCP 서버의 연결을 확인하고 도구 목록을 가져옵니다.
    
    이 함수는 서버 설정에 따라 HTTP 또는 STDIO 기반 MCP 서버에 연결하고
    해당 서버에서 제공하는 도구 목록을 가져옵니다. 타임아웃 처리가 포함되어 있어
    응답이 없는 서버에 대한 대기 시간이 제한됩니다.
    
    Args:
        server_config: 서버 설정 딕셔너리 (name, url 또는 command/args 필요)
        
    Returns:
        Dict: 서버의 연결 상태와 도구 목록을 포함한 딕셔너리
        {
            'name': '서버 이름',
            'config': {...},  # 원본 설정
            'connected': True/False,
            'error': '에러 메시지',  # 실패 시
            'tools': [...]  # 성공 시 도구 목록
        }
    """
    server_name = server_config.get('name')
    if not server_name:
        logging.warning("MCP 서버 설정에 'name' 필드가 없습니다. 건너뜁니다.")
        return {
            'name': 'unknown',
            'config': server_config,
            'connected': False,
            'error': "서버 이름이 없습니다."
        }
    
    result = {
        'name': server_name,
        'config': server_config,
        'connected': False
    }
    
    server = None
    try:
        # 서버 유형에 따라 인스턴스 생성
        if "url" in server_config:
            logging.info(f"MCP HTTP 서버 연결 시도: name={server_name}, url={server_config['url']}")
            
            params = {
                "url": server_config["url"],
                "timeout": 10.0,  # 타임아웃 시간 감소
                "request_timeout": 30.0  # 요청 타임아웃 시간 감소
            }
            if "headers" in server_config:
                params["headers"] = server_config["headers"]
            
            server = MCPServerStreamableHttp(
                params=params,
                cache_tools_list=True,
                client_session_timeout_seconds=30.0
            )
        else:
            logging.info(f"MCP CLI 서버 연결 시도: name={server_name}, command={server_config.get('command')}")
            
            # args에 포함된 스크립트 경로를 프로젝트 루트 기준으로 변환
            args = server_config.get("args", [])
            for i, arg in enumerate(args):
                if arg.startswith('src/'):
                    args[i] = os.path.join(PROJECT_ROOT, arg)
            
            server = MCPServerStdio(
                params={
                    "command": server_config.get("command"),
                    "args": args,
                    "cwd": PROJECT_ROOT,
                    "env": os.environ,
                    "shell": True,
                    "request_timeout": 30.0  # 타임아웃 시간 감소
                },
                cache_tools_list=True,
                client_session_timeout_seconds=30.0
            )
        
        # 타임아웃과 함께 서버 연결 시도
        try:
            # 30초 타임아웃으로 연결 시도
            await asyncio.wait_for(server.connect(), timeout=30.0)
            result['connected'] = True
            
            # 도구 목록 가져오기 (10초 타임아웃)
            try:
                tools = await asyncio.wait_for(server.list_tools(), timeout=10.0)
                # 도구 객체를 사전으로 변환
                tools_list = []
                for tool in tools:
                    # 객체 속성에 안전하게 접근
                    tool_dict = {
                        "name": getattr(tool, 'name', 'Unknown'),
                        "description": getattr(tool, 'description', ''),
                        "parameters": getattr(tool, 'parameters', {})
                    }
                    tools_list.append(tool_dict)
                
                result['tools'] = tools_list
                logging.info(f"✅ MCP 서버 '{server_name}'의 도구 목록 불러오기 성공 ({len(tools_list)} 도구)")
            except asyncio.TimeoutError:
                logging.error(f"⏱️ MCP 서버 '{server_name}'의 도구 목록 불러오기 타임아웃 (10초)")
                result['connected'] = False
                result['error'] = "도구 목록 불러오기 타임아웃"
            except Exception as e:
                logging.error(f"❌ MCP 서버 '{server_name}'의 도구 목록 불러오기 실패: {str(e)}")
                result['connected'] = False
                result['error'] = f"도구 목록 불러오기 오류: {str(e)}"
                
        except asyncio.TimeoutError:
            logging.error(f"⏱️ MCP 서버 '{server_name}' 연결 타임아웃 (30초)")
            result['error'] = "연결 타임아웃"
            
    except Exception as e:
        error_msg = str(e)
        logging.error(f"❌ MCP 서버 '{server_name}' 연결 실패: {error_msg}")
        result['error'] = error_msg
    
    return result

async def check_server_connections() -> List[Dict[str, Any]]:
    """
    모든 MCP 서버들의 연결을 병렬로 확인하고 각 서버의 도구 목록을 가져옵니다.
    
    이 함수는 mcp_config.json에서 정의된 모든 서버 설정을 로드하고,
    각 서버에 대해 병렬로 연결을 시도합니다. 모든 서버 연결 시도는 
    동시에 처리되어 전체 대기 시간이 크게 줄어듭니다.
    
    Returns:
        List[Dict]: 각 서버의 연결 상태와 도구 목록을 포함한 딕셔너리 리스트
        [
            {
                'name': 'server-name',
                'config': {...},  # 서버 원본 설정
                'connected': True/False,
                'error': '에러 메시지' (연결 실패 시),
                'tools': [...] (연결 성공 시 도구 목록)
            },
            ...
        ]
    
    Example:
        ```python
        server_results = await check_server_connections()
        
        # 연결된 서버와 실패한 서버 확인
        connected = [r['name'] for r in server_results if r.get('connected')]
        failed = [r['name'] for r in server_results if not r.get('connected')]
        
        print(f"연결됨: {connected}")
        print(f"실패: {failed}")
        ```
    """
    config = load_mcp_config()
    server_configs = config.get('mcpServers', [])
    
    # 모든 서버를 병렬로 처리
    tasks = [check_server_connection(server_config) for server_config in server_configs]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 예외 처리
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # 예외가 발생한 경우, 기본 결과 생성
            server_name = server_configs[i].get('name', f"server-{i}")
            processed_results.append({
                'name': server_name,
                'config': server_configs[i],
                'connected': False,
                'error': f"처리 중 오류 발생: {str(result)}"
            })
            logging.error(f"❌ MCP 서버 '{server_name}' 처리 중 오류: {str(result)}")
        else:
            processed_results.append(result)
    
    # 연결된 서버와 실패한 서버 요약
    connected_servers = [r['name'] for r in processed_results if r.get('connected')]
    failed_servers = [r['name'] for r in processed_results if not r.get('connected')]
    
    if connected_servers:
        logging.info(f"연결된 서버 ({len(connected_servers)}): {', '.join(connected_servers)}")
    if failed_servers:
        logging.warning(f"연결 실패한 서버 ({len(failed_servers)}): {', '.join(failed_servers)}")
    
    return processed_results

async def get_available_tools() -> Dict[str, List]:
    """
    모든 연결된 서버의 사용 가능한 도구 목록을 가져옵니다.
    
    이 함수는 먼저 모든 서버의 연결 상태를 확인한 후,
    성공적으로 연결된 서버에서 사용할 수 있는 도구 목록만 반환합니다.
    연결에 실패한 서버의 도구는 포함되지 않습니다.
    
    Returns:
        Dict[str, List]: 서버 이름을 키로, 도구 목록을 값으로 하는 딕셔너리
        {
            '서버이름1': [
                {'name': '도구이름', 'description': '도구설명', 'parameters': {...}},
                ...
            ],
            '서버이름2': [...]
        }
    
    Example:
        ```python
        tools_by_server = await get_available_tools()
        
        # 각 서버별 도구 목록 출력
        for server_name, tools in tools_by_server.items():
            print(f"{server_name}: {len(tools)}개 도구 사용 가능")
            for tool in tools:
                print(f"  - {tool['name']}")
        ```
    """
    server_results = await check_server_connections()
    available_tools = {}
    
    for result in server_results:
        if result.get('connected') and 'tools' in result:
            available_tools[result['name']] = result['tools']
    
    return available_tools

async def check_and_get_servers() -> Tuple[List[Dict[str, Any]], Dict[str, List]]:
    """
    서버 연결을 확인하고 사용 가능한 도구 목록을 동시에 반환합니다.
    check_server_connections()와 get_available_tools()를 효율적으로 결합한 버전입니다.
    
    Returns:
        Tuple[List[Dict], Dict[str, List]]: 
            - 서버 연결 결과 목록
            - 사용 가능한 도구 목록 (서버 이름 -> 도구 목록)
    
    Example:
        ```python
        server_results, available_tools = await check_and_get_servers()
        
        # 연결 결과 확인
        for result in server_results:
            status = "✅ 성공" if result.get('connected') else "❌ 실패"
            print(f"{status} | 서버: {result['name']}")
            
        # 도구 목록 활용
        for server_name, tools in available_tools.items():
            print(f"서버: {server_name} ({len(tools)} 도구)")
            for tool in tools[:5]:  # 처음 5개만 표시
                print(f"  - {tool.get('name')}: {tool.get('description')[:50]}")
        ```
    """
    try:
        # 모든 서버 연결 확인
        server_results = await check_server_connections()
        available_tools = {}
        
        # 사용 가능한 도구 추출
        for result in server_results:
            if result.get('connected') and 'tools' in result:
                available_tools[result['name']] = result['tools']
        
        return server_results, available_tools
    
    except Exception as e:
        logging.error(f"서버 연결 확인 중 오류 발생: {str(e)}")
        return [], {}