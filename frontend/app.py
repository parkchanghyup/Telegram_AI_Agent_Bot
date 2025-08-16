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

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agent_setup import setup_agent_and_servers
from src.utils import load_config
from agents.run import Runner

# Configuration
config_path = os.path.join(os.path.dirname(__file__), '..', 'mcp_config.json')
config = load_config(config_path)

# Flask app
app = Flask(__name__)

# Global variables
main_agent = None
mcp_servers = []
agent_ready = False

async def initialize_agent():
    """Initialize the MCP agent and servers."""
    global main_agent, mcp_servers, agent_ready
    try:
        print("🔄 Initializing MCP agent...")
        
        # Try to initialize with MCP servers first
        try:
            main_agent, mcp_servers = await setup_agent_and_servers()
            if main_agent:
                agent_ready = True
                print("✅ MCP agent initialized successfully with servers!")
                return True
        except Exception as mcp_error:
            print(f"⚠️ MCP server connection failed: {mcp_error}")
            print("🔄 Trying to initialize agent without MCP servers...")
            
            # Fallback: create agent without MCP servers
            from src.llm_factory import LLMFactory
            from src.utils import load_prompt
            
            # Load LLM config
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            llm_config_path = os.path.join(project_root, 'llm_config.json')
            
            with open(llm_config_path, 'r', encoding='utf-8') as f:
                llm_config = json.load(f)
            
            llm_factory = LLMFactory(llm_config)
            
            # Load prompt
            prompt_base_dir = os.path.join(project_root, 'src', 'prompt')
            instructions = load_prompt("prompt.txt", prompt_base_dir)
            
            # Create agent without MCP servers
            from agents.agent import Agent
            main_agent = Agent(
                name="Main Agent (No MCP)",
                instructions=instructions,
                model=llm_factory.get_model(),
                mcp_servers=[]  # No MCP servers
            )
            
            mcp_servers = []
            agent_ready = True
            print("✅ Agent initialized without MCP servers (fallback mode)")
            return True
            
    except Exception as e:
        print(f"❌ Complete initialization failure: {e}")
        agent_ready = False
        return False

async def run_agent(user_message):
    """Run the agent with user input."""
    try:
        if not main_agent:
            return "Agent is not ready yet."
        
        result = await Runner.run(main_agent, input=user_message)
        
        if result and result.final_output is not None:
            return str(result.final_output)
        else:
            return "Sorry, I couldn't generate a response."
            
    except Exception as e:
        print(f"Error running agent: {e}")
        return f"Error: {str(e)}"

@app.route('/')
def index():
    """Serve the main chat interface."""
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages from the frontend."""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'response': "Please enter a message."}), 400
        
        if not agent_ready:
            return jsonify({'response': "MCP agent is not ready yet. Please wait a moment and try again."}), 503
        
        # Run the agent
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response_text = loop.run_until_complete(run_agent(user_message))
        finally:
            loop.close()
        
        return jsonify({'response': response_text})
        
    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({'response': f"An error occurred: {str(e)}"}), 500

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
        
        # Update global config
        global config
        config = new_config
        
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
            return jsonify({})
        
        tools_by_server = {}
        
        # Try to get tools from connected servers
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def get_server_tools():
                for server in mcp_servers:
                    try:
                        if hasattr(server, 'list_tools'):
                            tools_result = await server.list_tools()
                            if hasattr(tools_result, 'tools'):
                                server_name = getattr(server, 'name', 'Unknown Server')
                                tools_by_server[server_name] = [
                                    {
                                        "name": tool.name,
                                        "description": getattr(tool, 'description', 'No description')
                                    }
                                    for tool in tools_result.tools
                                ]
                    except Exception as e:
                        print(f"Error getting tools from server: {e}")
                        pass
            
            loop.run_until_complete(get_server_tools())
        finally:
            loop.close()
        
        # Fallback to server names if no tools found
        if not tools_by_server:
            mcp_config = config.get("mcpServers", {})
            tools_by_server = {
                name: [{"name": "Tools will be available when connected", "description": ""}] 
                for name in mcp_config.keys()
            }
        
        return jsonify(tools_by_server)
        
    except Exception as e:
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