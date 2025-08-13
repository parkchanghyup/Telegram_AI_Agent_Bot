import os
import logging
import asyncio
import sys
import json
import time
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
# from agents import Agent, Runner
from agents.mcp import MCPServerStdio
from agents import Agent, Runner, OpenAIChatCompletionsModel, AsyncOpenAI, OpenAIChatCompletionsModel, function_tool



load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Ensure file-based logging
os.makedirs('logs', exist_ok=True)
_root_logger = logging.getLogger()
if not any(isinstance(h, logging.FileHandler) for h in _root_logger.handlers):
    _file_handler = logging.FileHandler('logs/bot.log', encoding='utf-8')
    _file_handler.setLevel(logging.INFO)
    _file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    _root_logger.addHandler(_file_handler)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Instruction prompt 설정 파일 경로 및 상수 로딩
PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompt.txt")
try:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        INSTRUCTIONS = f.read().strip()
except FileNotFoundError as exc:
    raise FileNotFoundError("prompt.txt 파일이 telegram_mcp_bot 디렉터리에 없습니다.") from exc

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN 환경변수를 .env 파일에 설정해주세요.")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY 환경변수를 .env 파일에 설정해주세요.")


mcp_agent = None
mcp_servers = []
mcp_server_map = {}

def _truncate_for_log(text: str, length: int = 200) -> str:
    if text is None:
        return ''
    text = str(text)
    return text if len(text) <= length else text[:length] + '…'

async def setup_agent_and_servers():
    """MCP 서버와 AI 에이전트를 설정합니다."""
    global mcp_agent, mcp_servers
    
    with open('mcp_config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    for server_name, server_config in config.get('mcpServers', {}).items():
        logging.info(f"MCP 서버 준비: name={server_name}, command={server_config.get('command')}, args={server_config.get('args', [])}")
        server = MCPServerStdio(
            params={
                "command": server_config.get("command"),
                "args": server_config.get("args", [])
            },
            cache_tools_list=True
        )
        await server.connect()
        logging.info(f"MCP 서버 연결 성공: name={server_name}")
        mcp_servers.append(server)
        mcp_server_map[server_name] = server

    model = OpenAIChatCompletionsModel(
        model="conandoyle247/jan-nano-4b-gguf",
        openai_client=AsyncOpenAI(base_url="http://localhost:11434/v1")
    )


    # 에이전트 분리: 단순 Q&A 에이전트와 네이버 검색 에이전트
    qa_agent = Agent(
        name="QnA Agent",
        instructions=INSTRUCTIONS+'/no_think',
        model=model
    )

    naver_instructions = (
        "You are a news search specialist. Use the MCP tool to search latest Naver news.\n"
        "- Prefer concise bullet summaries with title, brief gist, and link.\n"
        "- If the query is not about news or search, do not answer; rely on triage."
        "- answer in Korean"
    )
    # 특정 MCP 서버(예: 'naver-search')만 검색 에이전트에 연결
    naver_server = mcp_server_map.get('naver-search')
    naver_agent = Agent(
        name="Naver Search Agent",
        instructions=naver_instructions,
        model=model,
        mcp_servers=[naver_server] if naver_server else []
    )

    # 트리아지 에이전트: 뉴스/검색 관련 요청은 네이버 검색 에이전트로, 그 외는 QnA로 전달
    mcp_agent = Agent(
        name="Triage Agent",
        instructions=(
            "If the user asks for news, headlines, today's updates, or mentions 검색/뉴스/네이버/기사/실시간, "
            "hand it off to the Naver Search Agent. Otherwise, hand it off to the QnA Agent. "
            "If unclear, prefer QnA Agent."
        ),
        handoffs=[naver_agent, qa_agent]
    )
    logging.info("AI 에이전트 및 MCP 서버가 성공적으로 설정되었습니다.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """봇 시작 명령어 핸들러"""
    welcome_message = """
🤖 안녕하세요! AI 에이전트 봇입니다.
무엇이든 물어보세요. 최신 뉴스가 궁금하면 검색을 요청할 수도 있습니다.
예: "오늘의 주요 뉴스 알려줘"
"""
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """사용자 메시지를 AI 에이전트로 처리하는 핸들러"""
    user_message = update.message.text
    logging.info(f"사용자로부터 메시지 받음: {user_message}")

    if not mcp_agent:
        await update.message.reply_text("죄송합니다. 에이전트가 아직 준비되지 않았습니다.")
        return

    processing_message = await update.message.reply_text("🔄 생각 중...")

    try:
        start_time = time.perf_counter()
        result = await Runner.run(mcp_agent, input=user_message)
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        response_text = str(result.final_output)

        # Log concise Q&A record
        logging.info(
            "QnA 처리 완료: duration_ms=%.1f, user='%s', response='%s'",
            duration_ms,
            _truncate_for_log(user_message),
            _truncate_for_log(response_text)
        )

        await processing_message.delete()
        await update.message.reply_text(response_text)

    except Exception as e:
        logging.error(f"메시지 처리 중 오류 발생: {e}")
        await processing_message.delete()
        await update.message.reply_text(f"❌ 처리 중 오류가 발생했습니다: {str(e)}")

async def shutdown_servers(app):
    """애플리케이션 종료 시 MCP 서버 연결을 종료합니다."""
    global mcp_servers
    logging.info("MCP 서버 연결을 종료합니다.")
    for server in mcp_servers:
        await server.disconnect()
    logging.info("MCP 서버 연결이 모두 종료되었습니다.")

def main() -> None:
    """봇 실행 메인 함수"""
    loop = asyncio.get_event_loop()
    
    try:
        loop.run_until_complete(setup_agent_and_servers())
    except Exception as e:
        logging.error(f"초기 설정 실패: {e}")
        return

    application = Application.builder().token(BOT_TOKEN).post_shutdown(shutdown_servers).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("🤖 AI 에이전트 텔레그램 봇이 시작되었습니다...")
    application.run_polling()

if __name__ == '__main__':
    main()
