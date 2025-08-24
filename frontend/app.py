import os
import sys
import asyncio
import json
import logging
import threading
import subprocess
import time
from typing import List, Dict, Any, Optional, Tuple
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Add parent directory to path for imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# MCP 유틸리티 함수 임포트 (경로 수정)
from src.mcp_utils import check_and_get_servers

class MCPErrorFilter(logging.Filter):
    """MCP 관련 무해한 에러들을 필터링하는 클래스"""
    
    def filter(self, record):
        # 억제할 에러 메시지 패턴들
        suppress_patterns = [
            "SSE stream disconnected",
            "Failed to open SSE stream", 
            "Transport is closed",
            "Failed to send heartbeat",
            "Streamable HTTP error",
            "Maximum reconnection attempts",
            "Session termination failed",
            "Error POSTing to endpoint",
            "Failed to reconnect SSE stream",
            "Bad Request",
            "HTTP 400",
            "Sending heartbeat ping",
            "terminated",
            "TypeError: terminated",
            "Failed to open SSE stream: Bad Request",
            "Failed to reconnect SSE stream: Streamable HTTP error"
        ]
        
        # 중요한 설정 로그는 억제하지 않음
        important_patterns = [
            "MCP 클라이언트 타임아웃 설정",
            "MCP 서버 연결 성공", 
            "MCP 서버 연결 실패",
            "Agent run successful",
            "Received chat message"
        ]
        
        # 중요한 메시지는 통과시킴
        for pattern in important_patterns:
            if pattern in record.getMessage():
                return True
        
        # 메시지에 억제 패턴이 포함되어 있으면 False 반환 (로그 출력 안함)
        message = record.getMessage()
        for pattern in suppress_patterns:
            if pattern in message:
                return False
        
        return True

# Load .env from parent directory (telegram_mcp_bot/)
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
env_path = os.path.join(parent_dir, '.env')

# 디버깅: .env 파일 경로 및 존재 여부 확인
print(f"🔍 Looking for .env file at: {env_path}")
print(f"🔍 .env file exists: {os.path.exists(env_path)}")

# .env 파일 로드
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"✅ .env file loaded successfully")
else:
    print(f"❌ .env file not found at {env_path}")

# Set environment variables for OpenAI (if not already set)
if not os.getenv("OPENAI_API_KEY"):
    print("⚠️ Warning: OPENAI_API_KEY not found in environment variables")
    # You can set a default or prompt user to set it

# Disable tracing and logging to avoid permission issues
os.environ.setdefault("OPENAI_AGENTS_TRACING", "false")
os.environ.setdefault("OPENAI_AGENTS_LOGGING", "false")
os.environ.setdefault("AGENTS_LOGGING_LEVEL", "ERROR")
os.environ.setdefault("MCP_LOGGING_LEVEL", "ERROR")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Add parent directory to path for imports and change working directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

# CRITICAL: Change working directory to project root for MCP servers to work
os.chdir(project_root)
print(f"🔄 Changed working directory to: {os.getcwd()}")

from src.agent_setup import setup_agent_and_servers
from src.utils import load_config
from src.config import load_mcp_config, load_llm_config
from agents.run import Runner

# Configuration - Use the same loading method as main.py
config = load_mcp_config()
config_path = os.path.join(os.path.dirname(__file__), '..', 'mcp_config.json')
llm_config_path = os.path.join(os.path.dirname(__file__), '..', 'llm_config.json')

# Flask app
app = Flask(__name__)

# Global variables
main_agent = None
mcp_servers = []
agent_ready = False
#  dedicated asyncio event loop running in a background thread
background_loop = None
background_thread = None
# Server status tracking
all_server_status = []  # 모든 서버들의 연결 상태 정보 저장
last_server_status_check = 0  # 마지막 서버 상태 확인 시간 (timestamp)
# Cache for MCP tools to avoid loading delay
cached_mcp_tools = {}


def start_background_loop(loop):
    """Starts the asyncio event loop in a background thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


# 이 함수들은 src.mcp_utils 모듈의 함수들로 대체되었습니다:
# - check_server_connection
# - check_server_connections 
# - check_and_get_servers
# 
# 필요한 경우 위 함수들을 import해서 사용하세요.

# 서버 연결 상태 결과를 app.py 형식으로 변환하는 헬퍼 함수
async def convert_server_results_to_app_format(server_results) -> List[Dict[str, Any]]:
    """mcp_utils.py의 서버 결과를 app.py에서 사용하는 형식으로 변환합니다."""
    app_format_results = []
    for result in server_results:
        server_type = 'HTTP' if 'url' in result.get('config', {}) else 'STDIO'
        status = 'SUCCESS' if result.get('connected') else 'FAILED'
        if result.get('connected') and not result.get('tools'):
            status = 'WARN'

        app_result = {
            'name': result.get('name', 'Unknown'),
            'type': server_type,
            'status': status,
            'tools': [t.get('name', '') for t in result.get('tools', [])] if 'tools' in result else [],
            'error': result.get('error'),
            'config': result.get('config', {})
        }
        app_format_results.append(app_result)
        
        # 상태 아이콘에 따른 로그 출력
        if app_result['status'] == 'SUCCESS':
            status_icon = "✅"
            status_text = "SUCCESS"
        elif app_result['status'] == 'WARN':
            status_icon = "⚠️"
            status_text = "WARN"
        else:
            status_icon = "❌"
            status_text = "FAILED"
            
        tool_count = len(app_result['tools'])
        error_msg = f" - {app_result['error']}" if app_result['error'] else ""
        print(f"  {status_icon} {app_result['name']} ({app_result['type']}) - 상태: {status_text} - {tool_count}개 도구{error_msg}")
    
    return app_format_results

async def initialize_agent():
    """Initialize the MCP agent and servers."""
    global main_agent, mcp_servers, agent_ready, all_server_status, last_server_status_check, cached_mcp_tools
    
    # Gracefully shut down existing servers before re-initializing
    if mcp_servers:
        print(f"🔄 Shutting down {len(mcp_servers)} existing MCP server(s)...")
        try:
            # Concurrently shut down all servers that have a 'close' method
            await asyncio.gather(
                *(server.close() for server in mcp_servers if hasattr(server, 'close'))
            )
            print("✅ Existing servers shut down successfully.")
        except Exception as e:
            print(f"⚠️ Warning: Error while shutting down existing servers: {e}")
            # Continue with initialization anyway
    
    # Reset previous state
    main_agent = None
    mcp_servers = []
    agent_ready = False
    
    try:
        print("🔄 Initializing MCP agent...")
        
        # Apply logging filters again before agent initialization
        mcp_filter = MCPErrorFilter()
        all_possible_loggers = [
            "", "agents", "openai", "openai.agents", "openai.agents.run", 
            "openai.agents.runner", "agents.run", "agents.runner", "Runner",
            "run", "runner", "mcp", "mcp.client", "mcp.server", "streamable",
            "sse", "openai.agents.streamable", "agents.streamable", "httpx",
            "httpcore", "anyio", "asyncio"
        ]
        
        for logger_name in all_possible_loggers:
            logger = logging.getLogger(logger_name)
            logger.addFilter(mcp_filter)
            logger.setLevel(logging.ERROR)

        # Debug: Print current working directory and paths
        import os
        from src.config import PROJECT_ROOT
        print(f"🔍 Current working directory: {os.getcwd()}")
        print(f"🔍 PROJECT_ROOT: {PROJECT_ROOT}")
        print(f"🔍 PROJECT_ROOT exists: {os.path.exists(PROJECT_ROOT)}")
        print(f"🔍 src directory exists: {os.path.exists(os.path.join(PROJECT_ROOT, 'src'))}")
        
        # 🔍 먼저 MCP 서버들의 연결 상태와 도구 목록을 동시에 가져오기
        print("🔍 MCP 서버 연결 상태 및 도구 목록 확인 중...")
        server_results, available_tools = await check_and_get_servers()
        
        # 서버 상태 변환 및 저장
        all_server_status = await convert_server_results_to_app_format(server_results)
        last_server_status_check = time.time()  # 상태 확인 시간 기록
        
        # 연결 성공한 서버들만 필터링
        available_servers = [r for r in server_results if r.get('connected')]
        
        if not available_servers:
            print("⚠️ 연결 가능한 MCP 서버가 없습니다. 서버 없이 에이전트를 초기화합니다.")
            # 빈 서버 설정으로 에이전트 초기화
            main_agent, mcp_servers, server_names = await setup_agent_and_servers([])
        else:
            print(f"✅ {len(available_servers)}개의 MCP 서버 연결 확인됨. 에이전트를 초기화합니다.")
            # 연결 가능한 서버들만으로 에이전트 초기화
            main_agent, mcp_servers, server_names = await setup_agent_and_servers(available_servers)
        
        if main_agent and mcp_servers:
            agent_ready = True
            print(f"✅ MCP agent initialized successfully with {len(mcp_servers)} servers!")
            print(f"   Servers: {[getattr(s, 'name', f'Server-{i+1}') for i, s in enumerate(mcp_servers)]}")
            
            # 이미 가져온 도구 목록을 바로 캐시에 저장
            cached_mcp_tools = {}
            for server_name, tools in available_tools.items():
                tool_list = [
                    {"name": tool.get("name", "Unknown"), 
                     "description": tool.get("description", "No description available")}
                    for tool in tools
                ]
                cached_mcp_tools[server_name] = tool_list
            
            print(f"📦 Cached MCP tools updated with {len(cached_mcp_tools)} servers")
            
            return True
        elif main_agent:
            agent_ready = True
            print("✅ MCP agent initialized successfully (no servers configured)!")
            return True

            
    except Exception as e:
        print(f"❌ Complete initialization failure: {e}")
        import traceback
        traceback.print_exc()
        agent_ready = False
        return False

# run_agent 함수는 더 이상 사용하지 않음 - create_fresh_agent로 대체됨

@app.route('/')
def index():
    """Serve the main chat interface."""
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages from the frontend."""
    try:
        if not request.json:
            return jsonify({'response': "❌ Invalid request format. Please send JSON data."}), 400
            
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'response': "❌ Please enter a message."}), 400
        
        if not agent_ready or not main_agent or not background_loop:
            return jsonify({
                'response': "⚠️ Agent is not ready. Please wait or reinitialize."
            }), 503
        
        print(f"📨 Received chat message: {user_message[:100]}...")

        # 런타임에 새로 생성된 로거들에도 필터 적용
        setup_comprehensive_logging_suppression()

        async def run_agent_async(agent, message):
            """Coroutine to run the agent."""
            # 에이전트 실행 직전에 한번 더 로깅 억제
            setup_comprehensive_logging_suppression()
            return await Runner.run(agent, input=message)

        try:
            # Submit the agent run to the background event loop and wait for the result
            future = asyncio.run_coroutine_threadsafe(
                run_agent_async(main_agent, user_message), 
                background_loop
            )
            
            # Set a timeout for the agent's response
            result = future.result(timeout=180) # 3-minute timeout
            response_text = str(result.final_output)

            print(f"✅ Agent run successful! response: {response_text[:100]}...")
            return jsonify({'response': response_text})
            
        except Exception as run_error:
            print(f"❌ Agent run error: {run_error}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'response': f"🔧 Agent execution failed: {str(run_error)}"
            }), 500
        
    except Exception as e:
        print(f"❌ Chat endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'response': f"❌ Server error: {str(e)}"
        }), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get MCP configuration."""
    try:
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['POST'])
def save_config():
    """Save MCP configuration."""
    try:
        new_config = request.json
        
        # Save to file
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(new_config, f, indent=4, ensure_ascii=False)
        
        # Update global config using the same method as initialization
        global config
        config = load_mcp_config()
        
        # Reset agent ready status since config changed
        global agent_ready
        agent_ready = False
        
        # Clear the tools cache since server config changed
        global cached_mcp_tools
        cached_mcp_tools = {}
        
        return jsonify({'success': True, 'message': 'Configuration saved successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/llm_config', methods=['GET'])
def get_llm_config():
    """Get LLM configuration."""
    try:
        llm_config = load_llm_config()
        return jsonify(llm_config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/llm_config', methods=['POST'])
def save_llm_config():
    """Save LLM configuration."""
    try:
        new_config = request.json
        
        # Save to file
        with open(llm_config_path, 'w', encoding='utf-8') as f:
            json.dump(new_config, f, indent=4, ensure_ascii=False)
        
        # Reset agent ready status since config changed
        global agent_ready
        agent_ready = False
        
        return jsonify({'success': True, 'message': 'LLM configuration saved successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/env', methods=['GET'])
def get_env():
    """Get .env file contents."""
    try:
        env_file_path = os.path.join(project_root, '.env')
        
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({'content': content, 'exists': True})
        else:
            return jsonify({'content': '', 'exists': False})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/env', methods=['POST'])
def save_env():
    """Save .env file."""
    try:
        data = request.json
        content = data.get('content', '')
        
        env_file_path = os.path.join(project_root, '.env')
        
        # Create .env file with the provided content
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Reload environment variables
        load_dotenv(env_file_path, override=True)
        
        return jsonify({'success': True, 'message': '.env file saved successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500




def _suppress_async_shutdown_error_handler(loop, context):
    """
    Custom exception handler to suppress known, benign errors that occur
    during the shutdown of the asyncio event loop in a threaded environment.
    """
    exception = context.get("exception")
    message = context.get("message", "")
    
    # Check for the specific RuntimeError from anyio/mcp-sdk
    is_cancel_scope_error = (
        isinstance(exception, RuntimeError)
        and "Attempted to exit cancel scope" in str(exception)
    )
    
    # Check for other common, harmless shutdown-related exceptions
    is_generator_exit = isinstance(exception, GeneratorExit)
    is_cancelled_error = isinstance(exception, asyncio.CancelledError)

    # Check for additional MCP-related errors to suppress
    is_transport_closed = (
        isinstance(exception, Exception)
        and ("Transport is closed" in str(exception) or "Session termination failed" in str(exception))
    )
    
    # Check for task group errors safely (BaseExceptionGroup is Python 3.11+)
    is_task_group_error = False
    try:
        # BaseExceptionGroup is a builtin in Python 3.11+
        import builtins
        BaseExceptionGroup = getattr(builtins, 'BaseExceptionGroup', None)
        if BaseExceptionGroup and isinstance(exception, BaseExceptionGroup):
            is_task_group_error = "unhandled errors in a TaskGroup" in str(exception)
        else:
            is_task_group_error = "unhandled errors in a TaskGroup" in str(exception)
    except Exception:
        # Fallback: check string representation
        is_task_group_error = "unhandled errors in a TaskGroup" in str(exception)
    
    # Check for MCP/anyio related errors by exception type and message patterns
    is_anyio_error = (
        isinstance(exception, RuntimeError)
        and any(pattern in str(exception) for pattern in [
            "anyio", "cancel scope", "task group", "GeneratorExit"
        ])
    )
    
    # Check for task-related shutdown errors
    is_task_shutdown_error = (
        "Task exception was never retrieved" in message
        or "Task was destroyed but it is pending" in message
        or isinstance(exception, (asyncio.CancelledError, GeneratorExit))
    )
    
    # Check for Streamable HTTP/MCP connection errors
    is_streamable_http_error = (
        "SSE stream disconnected" in message
        or "Failed to open SSE stream" in message
        or "Transport is closed" in message
        or "Failed to send heartbeat" in message
        or "Streamable HTTP error" in message
        or "Maximum reconnection attempts" in message
        or "Session termination failed" in message
        or "Bad Request" in message
        or "HTTP 400" in message
        or "Sending heartbeat ping" in message
        or "terminated" in str(exception)
        or "TypeError: terminated" in str(exception)
    )
    
    # Suppress all known benign errors
    if (is_cancel_scope_error or is_generator_exit or is_cancelled_error or 
        is_transport_closed or is_task_group_error or is_anyio_error or 
        is_task_shutdown_error or is_streamable_http_error):
        # Suppress the error by doing nothing
        pass
    else:
        # For all other errors, use the default handler to log them
        loop.default_exception_handler(context)

async def update_mcp_tools_cache():
    """Update the cached MCP tools from all servers."""
    global cached_mcp_tools
    
    if not agent_ready or not mcp_servers:
        return

    tools_by_server = {}
    server_names = [s.get('name') for s in config.get('mcpServers', [])]
    
    for i, server in enumerate(mcp_servers):
        server_name = server_names[i] if i < len(server_names) else f"Server-{i+1}"
        try:
            tools = await server.list_tools()

            if tools:
                tool_list = [
                    {"name": tool.name, "description": getattr(tool, 'description', 'No description available')}
                    for tool in tools
                ]
                tools_by_server[server_name] = tool_list
            else:
                tools_by_server[server_name] = [{"name": "No tools", "description": "No tools available"}]
        
        except Exception as e:
            print(f"❌ Error getting tools from {server_name}: {e}")
            tools_by_server[server_name] = [{"name": "Error", "description": str(e)}]
    
    cached_mcp_tools = tools_by_server
    print(f"📦 Cached MCP tools updated with {len(cached_mcp_tools)} servers")

@app.route('/api/tools', methods=['GET'])
def get_tools():
    """Get list of available MCP tools from the cached variable."""
    if not agent_ready or not mcp_servers or not background_loop:
        return jsonify({'error': 'Agent or event loop not ready.'}), 503
    
    # If cache is empty or forced refresh requested, update it
    if not cached_mcp_tools or request.args.get('refresh') == 'true':
        try:
            future = asyncio.run_coroutine_threadsafe(update_mcp_tools_cache(), background_loop)
            future.result(timeout=30)  # 30-second timeout
        except Exception as e:
            print(f"❌ Error updating MCP tools cache: {e}")
            # Still return the existing cache even if update fails
    
    return jsonify(cached_mcp_tools)


@app.route('/api/server-status', methods=['GET'])
def get_server_status():
    """Get status of all MCP servers (active and inactive)."""
    global all_server_status, last_server_status_check, background_loop, cached_mcp_tools
    
    # 새로 고침 요청이 있거나 서버 상태가 없는 경우에만 상태 업데이트
    current_time = time.time()
    force_refresh = request.args.get('refresh') == 'true'
    
    if force_refresh or not all_server_status:
        if background_loop and background_loop.is_running():
            try:
                # 비동기적으로 서버 상태 업데이트 요청
                print("🔄 서버 상태 새로 고침 중...")
                
                try:
                    # 서버 연결 상태와 도구 목록 동시 확인
                    future = asyncio.run_coroutine_threadsafe(
                        check_and_get_servers(), 
                        background_loop
                    )
                    # 최대 20초 대기
                    server_results, available_tools = future.result(timeout=20)
                    
                    # 결과 변환 및 캐시 업데이트
                    format_future = asyncio.run_coroutine_threadsafe(
                        convert_server_results_to_app_format(server_results),
                        background_loop
                    )
                    all_server_status = format_future.result(timeout=5)
                    last_server_status_check = current_time
                    
                    # 이미 가져온 도구 목록을 바로 캐시에 저장
                    cached_mcp_tools = {}
                    for server_name, tools in available_tools.items():
                        tool_list = [
                            {"name": tool.get("name", "Unknown"), 
                             "description": tool.get("description", "No description available")}
                            for tool in tools
                        ]
                        cached_mcp_tools[server_name] = tool_list
                    
                    print(f"✅ 서버 상태 및 도구 업데이트 완료: {len(all_server_status)}개 서버, {len(cached_mcp_tools)}개 도구 집합")
                    
                except Exception as inner_e:
                    print(f"❌ 서버 상태 및 도구 업데이트 오류: {inner_e}")
                    # 오류 발생 시 더 이상 추가 시도하지 않음
                    import traceback
                    traceback.print_exc()
                    
            except Exception as e:
                import traceback
                print(f"❌ 서버 상태 업데이트 실패: {e}")
                traceback.print_exc()
                # 업데이트 실패 시 기존 상태 유지
    
    if not all_server_status:
        return jsonify({
            'active_servers': [],
            'inactive_servers': [],
            'message': 'Server status not available. Try initializing the agent first.',
            'last_check': last_server_status_check
        })
    
    # 서버들을 active와 inactive로 분류
    active_servers = []
    inactive_servers = []
    
    for server_status in all_server_status:
        server_info = {
            'name': server_status.get('name', 'Unknown'),
            'type': server_status.get('type', 'Unknown'),
            'tools_count': len(server_status.get('tools', [])),
            'error': server_status.get('error'),
            'status': server_status.get('status')
        }
        
        # 상태가 명확하게 'SUCCESS'인 경우에만 활성화 상태로 간주
        if server_status.get('status') == 'SUCCESS':
            active_servers.append(server_info)
        else:
            inactive_servers.append(server_info)
    
    return jsonify({
        'active_servers': active_servers,
        'inactive_servers': inactive_servers,
        'total_servers': len(all_server_status),
        'active_count': len(active_servers),
        'inactive_count': len(inactive_servers),
        'last_check': last_server_status_check
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get agent status."""
    return jsonify({
        'agent_ready': agent_ready,
        'message': 'Agent is ready' if agent_ready else 'Agent is initializing...'
    })

@app.route('/api/init', methods=['POST'])
def init_agent():
    """Initialize or reinitialize the agent."""
    global background_loop
    if not background_loop or not background_loop.is_running():
        return jsonify({'error': 'Background event loop is not running.'}), 503

    try:
        # Submit the initialization to the background event loop
        future = asyncio.run_coroutine_threadsafe(initialize_agent(), background_loop)
        
        # Wait for the result with a timeout
        success = future.result(timeout=180) # 60-second timeout for initialization
        
        return jsonify({'success': success})
    except Exception as e:
        print(f"❌ Error during re-initialization: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def setup_comprehensive_logging_suppression():
    """포괄적인 로깅 억제 설정"""
    mcp_filter = MCPErrorFilter()
    
    # 로깅 레벨을 WARNING으로 설정해서 INFO 레벨의 무해한 메시지들 억제
    logging.getLogger().setLevel(logging.WARNING)
    
    # 모든 기존 로거에 필터 적용
    for name in logging.Logger.manager.loggerDict:
        logger = logging.getLogger(name)
        logger.addFilter(mcp_filter)
        if 'werkzeug' not in name.lower():
            logger.setLevel(logging.ERROR)
    
    # 특정 로거들에 강제로 필터 적용
    critical_loggers = [
        "", "agents", "openai", "openai.agents", "run", "runner", "Runner",
        "mcp", "streamable", "sse", "httpx", "anyio", "asyncio"
    ]
    
    for logger_name in critical_loggers:
        logger = logging.getLogger(logger_name)
        logger.addFilter(mcp_filter)
        logger.setLevel(logging.ERROR)
        logger.propagate = False  # 부모 로거로 전파 방지

if __name__ == '__main__':
    print("🤖 Starting MCP Agent Web Interface...")

    # MCP 설정은 기본값 사용

    # 포괄적인 로깅 억제 설정 적용
    setup_comprehensive_logging_suppression()

    # Set up and start the background event loop
    background_loop = asyncio.new_event_loop()
    
    # Set custom exception handler to suppress benign MCP shutdown errors
    background_loop.set_exception_handler(_suppress_async_shutdown_error_handler)
    
    background_thread = threading.Thread(target=start_background_loop, args=(background_loop,), daemon=True)
    background_thread.start()
    
    # Initialize agent on startup within the background loop
    init_future = asyncio.run_coroutine_threadsafe(initialize_agent(), background_loop)
    try:
        # Wait for initialization to complete
        init_future.result(timeout=60)
    except Exception as e:
        print(f"❌ Agent initialization failed: {e}")

    print("🌐 Starting web server...")
    print("📱 Open http://127.0.0.1:5001 in your browser")

    try:
        # Note: We are now importing threading
        app.run(
            host='127.0.0.1',
            port=5001,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    finally:
        if background_loop:
            background_loop.call_soon_threadsafe(background_loop.stop)
            # background_thread.join() # This can hang, stopping is enough for daemon