import os
import sys
import asyncio
import json
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
        
        main_agent, mcp_servers = await setup_agent_and_servers()
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

@app.route('/api/tools', methods=['GET'])
def get_tools():
    """Get list of available MCP tools."""
    try:
        if not mcp_servers:
            # Return configured servers if no active connections
            mcp_config = config.get("mcpServers", [])
            tools_by_server = {
                server.get('name', f'Server-{i+1}'): [{"name": "Server not connected", "description": "Please initialize the agent first"}] 
                for i, server in enumerate(mcp_config)
            }
            return jsonify(tools_by_server)
        
        tools_by_server = {}
        
        # Try to get tools from connected servers
        print(f"🔍 Debugging: Found {len(mcp_servers)} MCP servers")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def get_server_tools():
                for i, server in enumerate(mcp_servers):
                    try:
                        # Different ways to get server name
                        server_name = f"Server-{i+1}"
                        if hasattr(server, 'name'):
                            server_name = server.name
                        elif hasattr(server, 'params') and isinstance(server.params, dict):
                            if 'command' in server.params:
                                server_name = f"{server.params['command']}"
                                if 'args' in server.params and server.params['args']:
                                    server_name += f" {' '.join(server.params['args'][:2])}"
                        
                        print(f"🔍 Debugging server {i}: {server_name}")
                        print(f"   Server type: {type(server)}")
                        print(f"   Has list_tools: {hasattr(server, 'list_tools')}")
                        print(f"   Has get_tools: {hasattr(server, 'get_tools')}")
                        
                        # Try multiple methods to get tools with timeout
                        tools_result = None
                        if hasattr(server, 'list_tools'):
                            print(f"   Calling list_tools()...")
                            try:
                                # Add 10 second timeout to prevent hanging
                                tools_result = await asyncio.wait_for(
                                    server.list_tools(), 
                                    timeout=10.0
                                )
                                print(f"   Tools result: {tools_result}")
                                print(f"   Tools result type: {type(tools_result)}")
                                if tools_result:
                                    print(f"   Has tools attr: {hasattr(tools_result, 'tools')}")
                                    if hasattr(tools_result, 'tools'):
                                        print(f"   Tools count: {len(tools_result.tools) if tools_result.tools else 0}")
                            except asyncio.TimeoutError:
                                print(f"   ⏰ list_tools() timed out after 10 seconds")
                                tools_result = None
                            except Exception as list_error:
                                print(f"   ❌ list_tools() failed: {list_error}")
                                tools_result = None
                        elif hasattr(server, 'get_tools'):
                            print(f"   Calling get_tools()...")
                            try:
                                tools_result = await asyncio.wait_for(
                                    server.get_tools(), 
                                    timeout=10.0
                                )
                            except asyncio.TimeoutError:
                                print(f"   ⏰ get_tools() timed out after 10 seconds")
                                tools_result = None
                        
                        if tools_result and hasattr(tools_result, 'tools') and tools_result.tools:
                            tool_list = []
                            for tool in tools_result.tools:
                                tool_info = {
                                    "name": tool.name,
                                    "description": getattr(tool, 'description', 'No description available')
                                }
                                tool_list.append(tool_info)
                                print(f"   Found tool: {tool.name}")
                            
                            tools_by_server[server_name] = tool_list
                        else:
                            # Fallback: just show that server is connected
                            print(f"   No tools found, showing connection status")
                            tools_by_server[server_name] = [
                                {"name": "Connected", "description": "MCP server is connected but no tools found"}
                            ]
                            
                    except Exception as e:
                        print(f"❌ Error getting tools from server {i}: {e}")
                        import traceback
                        traceback.print_exc()
                        server_name = f"Server-{i+1}-Error"
                        tools_by_server[server_name] = [
                            {"name": "Error", "description": f"Failed to get tools: {str(e)}"}
                        ]
            
            loop.run_until_complete(get_server_tools())
        finally:
            loop.close()
        
        print(f"🔍 Final tools_by_server: {tools_by_server}")
        
        # If still no tools, show configuration
        if not tools_by_server:
            mcp_config = config.get("mcpServers", [])
            tools_by_server = {
                server.get('name', f'Server-{i+1}'): [{"name": "No tools found", "description": "Server connected but no tools available"}] 
                for i, server in enumerate(mcp_config)
            }
        
        return jsonify(tools_by_server)
        
    except Exception as e:
        print(f"Error in get_tools: {e}")
        return jsonify({'error': str(e)}), 500

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