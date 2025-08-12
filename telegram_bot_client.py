import os
import logging
import asyncio
import sys
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from agents import Agent, Runner
from agents.mcp import MCPServerStdio

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN 환경변수를 .env 파일에 설정해주세요.")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY 환경변수를 .env 파일에 설정해주세요.")

mcp_agent = None
mcp_servers = []

async def setup_agent_and_servers():
    """MCP 서버와 AI 에이전트를 설정합니다."""
    global mcp_agent, mcp_servers
    
    with open('mcp_config.json', 'r') as f:
        config = json.load(f)
    
    for server_config in config.get('mcpServers', {}).values():
        server = MCPServerStdio(
            params={
                "command": server_config.get("command"),
                "args": server_config.get("args", [])
            },
            cache_tools_list=True
        )
        await server.connect()
        mcp_servers.append(server)

    mcp_agent = Agent(
        name="Assistant",
        instructions="당신은 유용한 AI 어시스턴트입니다. 사용자의 질문에 답변하고, 필요시 뉴스 검색 기능을 사용해 최신 정보를 찾아줄 수 있습니다.",
        model="gpt-4o-mini",
        mcp_servers=mcp_servers
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
        result = await Runner.run(mcp_agent, input=user_message)
        response_text = str(result.final_output)

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
