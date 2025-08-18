import os
import sys
import asyncio
import json
import logging
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

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
global_loop = None  # 글로벌 이벤트 루프 저장

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
        # Validate request
        if not request.json:
            return jsonify({'response': "❌ Invalid request format. Please send JSON data."}), 400
            
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'response': "❌ Please enter a message."}), 400
        
        if not agent_ready:
            return jsonify({
                'response': "⚠️ Agent is not ready yet. Please wait for initialization to complete or try reinitializing."
            }), 503
        
        if not main_agent:
            return jsonify({
                'response': "❌ Agent instance is not available. Please try reinitializing the agent."
            }), 503
        
        print(f"📨 Received chat message: {user_message[:100]}...")
        
        # 🔧 MCP 서버를 포함한 완전한 Agent를 chat에서 새로 생성
        print(f"🔍 MCP 서버 포함 완전한 Agent 생성...")
        
        try:
            print(f"🔍 MCP Agent 생성 시작...")
            
            # chat endpoint에서 MCP 서버를 새로 연결하여 이벤트 루프 문제 해결
            async def create_fresh_agent():
                from agents.agent import Agent
                from src.llm_factory import LLMFactory
                from src.config import load_llm_config, load_mcp_config
                from src.utils import load_prompt
                from src.config import PROMPT_DIR
                from agents.mcp import MCPServerStdio, MCPServerStreamableHttp
                import os
                
                # LLM 설정
                llm_config = load_llm_config()
                llm_factory = LLMFactory(llm_config)
                
                # MCP 서버 새로 연결
                fresh_mcp_servers = []
                config = load_mcp_config()
                
                for server_config in config.get('mcpServers', []):
                    server_name = server_config.get('name')
                    if not server_name:
                        print("⚠️ MCP 서버 설정에 'name' 필드가 없습니다. 건너뜁니다.")
                        continue
                    
                    print(f"🔍 MCP 서버 연결 중: {server_name}")
                    
                    if "url" in server_config:
                        # 헤더 설정 (인증 등)
                        params = {"url": server_config["url"]}
                        if "headers" in server_config:
                            params["headers"] = server_config["headers"]
                        
                        server = MCPServerStreamableHttp(
                            params=params,
                            cache_tools_list=True
                        )
                    else:
                        from src.config import PROJECT_ROOT
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
                                "shell": True
                            },
                            cache_tools_list=True
                        )
                    
                    try:
                        await server.connect()
                        fresh_mcp_servers.append(server)
                        print(f"✅ MCP 서버 연결 완료: {server_name}")
                    except Exception as e:
                        print(f"❌ MCP 서버 연결 실패: {server_name}, error={str(e)}")
                        print(f"   MCP 서버 '{server_name}' 없이 계속 진행합니다.")
                
                # 프롬프트 로드
                instructions = load_prompt("prompt.txt", PROMPT_DIR)
                
                # 완전한 Agent 생성
                fresh_agent = Agent(
                    name="Fresh MCP Agent",
                    instructions=instructions,
                    model=llm_factory.get_model(),
                    mcp_servers=fresh_mcp_servers
                )
                
                print(f"✅ 완전한 MCP Agent 생성 완료!")
                
                # Runner.run 실행
                print(f"🔍 Runner.run 실행 시작...")
                result = await Runner.run(fresh_agent, input=user_message)
                print(f"✅ Runner.run 완료!")
                
                # MCP 서버 연결 정리
                for server in fresh_mcp_servers:
                    try:
                        await server.disconnect()
                    except:
                        pass
                
                return str(result.final_output)
            
            # 새로운 이벤트 루프에서 실행
            response_text = asyncio.run(create_fresh_agent())
            
            print(f"✅ 완전한 MCP Agent 성공! response: {response_text[:100]}...")
            print(f"📤 Sending response: {response_text[:100]}...")
            return jsonify({'response': response_text})
            
        except Exception as run_error:
            print(f"❌ MCP Agent 실패: {run_error}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'response': f"🔧 MCP Agent 실행 실패: {str(run_error)}"
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
    
    # Check for the specific RuntimeError from anyio/mcp-sdk
    is_cancel_scope_error = (
        isinstance(exception, RuntimeError)
        and "Attempted to exit cancel scope" in str(exception)
    )
    
    # Check for other common, harmless shutdown-related exceptions
    is_generator_exit = isinstance(exception, GeneratorExit)
    is_cancelled_error = isinstance(exception, asyncio.CancelledError)

    if is_cancel_scope_error or is_generator_exit or is_cancelled_error:
        # Suppress the error by doing nothing
        pass
    else:
        # For all other errors, use the default handler to log them
        loop.default_exception_handler(context)

@app.route('/api/tools', methods=['GET'])
def get_tools():
    """Get list of available MCP tools."""
    from src.config import load_mcp_config
    
    async def get_tools_from_server(server_config):
        """Helper to connect to a single server and fetch tools."""
        from agents.mcp import MCPServerStdio, MCPServerStreamableHttp
        from src.config import PROJECT_ROOT
        import os

        server_name = server_config.get('name')
        if not server_name:
            return None

        server = None
        tool_list = []
        try:
            print(f"🔍 Concurrently connecting to MCP server: {server_name}")
            if "url" in server_config:
                params = {"url": server_config["url"]}
                if "headers" in server_config:
                    params["headers"] = server_config["headers"]
                server = MCPServerStreamableHttp(params=params, cache_tools_list=True)
            else:
                args = server_config.get("args", [])
                for i, arg in enumerate(args):
                    if arg.startswith('src/'):
                        args[i] = os.path.join(PROJECT_ROOT, arg)
                server = MCPServerStdio(
                    params={
                        "command": server_config.get("command"), "args": args, "cwd": PROJECT_ROOT,
                        "env": os.environ, "shell": True
                    },
                    cache_tools_list=True
                )
            
            await server.connect()
            tools = await server.list_tools()
            
            if tools:
                tool_list = [
                    {"name": tool.name, "description": getattr(tool, 'description', 'No description available')}
                    for tool in tools
                ]
                print(f"✅ Found {len(tool_list)} tools in {server_name}")
            else:
                 tool_list = [{"name": "No tools", "description": "Server connected but no tools available"}]
            
            return (server_name, tool_list)

        except Exception as e:
            print(f"❌ Error getting tools from {server_name}: {e}")
            logging.error(f'Tool fetch failed for {server_name}: {e}', exc_info=True)
            error_info = [{"name": "Error", "description": f"Failed to get tools: {str(e)}"}]
            return (server_name, error_info)

    async def fetch_all_tools_concurrently():
        """Gathers tools from all configured servers concurrently."""
        config = load_mcp_config()
        mcp_servers_config = config.get('mcpServers', [])
        
        tasks = [get_tools_from_server(conf) for conf in mcp_servers_config]
        results = await asyncio.gather(*tasks)
        
        final_tools = {}
        for result in results:
            if result:
                server_name, tool_list = result
                final_tools[server_name] = tool_list
        return final_tools

    loop = None
    try:
        # Manually create and manage the event loop to set a custom exception handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Set the custom handler to suppress specific shutdown errors
        loop.set_exception_handler(_suppress_async_shutdown_error_handler)
        
        # Run the entire concurrent operation
        tools_data = loop.run_until_complete(fetch_all_tools_concurrently())
        
        return jsonify(tools_data)
        
    except Exception as e:
        print(f"Error in get_tools endpoint: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if loop:
            # Ensure the loop is closed to prevent resource leaks
            loop.close()


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
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(initialize_agent())
            return jsonify({'success': success})
        finally:
            loop.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🤖 Starting MCP Agent Web Interface...")
    
    # Initialize agent on startup
    loop = asyncio.get_event_loop()
    loop.run_until_complete(initialize_agent())
    
    print("🌐 Starting web server...")
    print("📱 Open http://127.0.0.1:5001 in your browser")
    
    try:
        app.run(
            host='127.0.0.1',
            port=5001,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
        # Cleanup
        if mcp_servers:
            async def cleanup():
                for server in mcp_servers:
                    try:
                        await server.disconnect()
                    except:
                        pass
            loop = asyncio.get_event_loop()
            loop.run_until_complete(cleanup())
    except Exception as e:
        print(f"❌ Server error: {e}")