import os
import sys
import asyncio
import json
import logging
import threading
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

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
            "Failed to reconnect SSE stream"
        ]
        
        # 중요한 설정 로그는 억제하지 않음
        important_patterns = [
            "MCP 클라이언트 타임아웃 설정",
            "MCP 서버 연결 성공", 
            "MCP 서버 연결 실패"
        ]
        
        # 중요한 메시지는 통과시킴
        for pattern in important_patterns:
            if pattern in record.getMessage():
                return True
        
        # 메시지에 억제 패턴이 포함되어 있으면 False 반환 (로그 출력 안함)
        for pattern in suppress_patterns:
            if pattern in record.getMessage():
                return False
        
        return True

# Load .env from parent directory (telegram_mcp_bot/)
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
env_path = os.path.join(parent_dir, '.env')
load_dotenv(env_path)

# Set environment variables for OpenAI (if not already set)
if not os.getenv("OPENAI_API_KEY"):
    print("⚠️ Warning: OPENAI_API_KEY not found in environment variables")
    # You can set a default or prompt user to set it

# Disable tracing to avoid permission issues
os.environ.setdefault("OPENAI_AGENTS_TRACING", "false")

# Add parent directory to path for imports and change working directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

# CRITICAL: Change working directory to project root for MCP servers to work
os.chdir(project_root)
print(f"🔄 Changed working directory to: {os.getcwd()}")

from src.agent_setup import setup_agent_and_servers
from src.utils import load_config
from src.config import load_mcp_config
from agents.run import Runner

# Configuration - Use the same loading method as main.py
config = load_mcp_config()
config_path = os.path.join(os.path.dirname(__file__), '..', 'mcp_config.json')

# Flask app
app = Flask(__name__)

# Global variables
main_agent = None
mcp_servers = []
agent_ready = False
#  dedicated asyncio event loop running in a background thread
background_loop = None
background_thread = None


def start_background_loop(loop):
    """Starts the asyncio event loop in a background thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


async def initialize_agent():
    """Initialize the MCP agent and servers."""
    global main_agent, mcp_servers, agent_ready
    
    # Reset previous state
    main_agent = None
    mcp_servers = []
    agent_ready = False
    
    try:
        print("🔄 Initializing MCP agent...")
        

        # Debug: Print current working directory and paths
        import os
        from src.config import PROJECT_ROOT
        print(f"🔍 Current working directory: {os.getcwd()}")
        print(f"🔍 PROJECT_ROOT: {PROJECT_ROOT}")
        print(f"🔍 PROJECT_ROOT exists: {os.path.exists(PROJECT_ROOT)}")
        print(f"🔍 src directory exists: {os.path.exists(os.path.join(PROJECT_ROOT, 'src'))}")
        
        main_agent, mcp_servers, server_names = await setup_agent_and_servers()
        if main_agent and mcp_servers:
            agent_ready = True
            print(f"✅ MCP agent initialized successfully with {len(mcp_servers)} servers!")
            print(f"   Servers: {[getattr(s, 'name', f'Server-{i+1}') for i, s in enumerate(mcp_servers)]}")
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

        async def run_agent_async(agent, message):
            """Coroutine to run the agent."""
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
        
        return jsonify({'success': True, 'message': 'Configuration saved successfully'})
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

@app.route('/api/tools', methods=['GET'])
def get_tools():
    """Get list of available MCP tools from the globally managed servers."""
    if not agent_ready or not mcp_servers or not background_loop:
        return jsonify({'error': 'Agent or event loop not ready.'}), 503

    tools_by_server = {}
    server_names = [s.get('name') for s in config.get('mcpServers', [])]
    
    for i, server in enumerate(mcp_servers):
        server_name = server_names[i] if i < len(server_names) else f"Server-{i+1}"
        try:
            # Submit the async list_tools call to the running background loop
            future = asyncio.run_coroutine_threadsafe(server.list_tools(), background_loop)
            
            # Wait for the result with a timeout
            tools = future.result(timeout=30) # 30-second timeout

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
            
    return jsonify(tools_by_server)


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
        success = future.result(timeout=60) # 60-second timeout for initialization
        
        return jsonify({'success': success})
    except Exception as e:
        print(f"❌ Error during re-initialization: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("🤖 Starting MCP Agent Web Interface...")

    # MCP 설정은 기본값 사용

    # MCP 에러 필터 적용 - 루트 로거와 관련 로거들에 필터 추가
    mcp_filter = MCPErrorFilter()
    logging.getLogger().addFilter(mcp_filter)
    logging.getLogger("agents").addFilter(mcp_filter)
    logging.getLogger("openai.agents").addFilter(mcp_filter)
    logging.getLogger("mcp").addFilter(mcp_filter)

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
    print("📱 Open http://1227.0.0.1:5001 in your browser")

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