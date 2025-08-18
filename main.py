import os
import logging
import asyncio
import time
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from agents.run import Runner

from src.agent_setup import setup_agent_and_servers
from src.utils import truncate_for_log, setup_file_logger

# .env 파일에서 환경 변수 로드
load_dotenv()

# Telegram Bot Token (환경 변수 또는 다른 설정 방식에서 가져와야 함)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN 환경변수를 설정해주세요.")

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
setup_file_logger()

main_agent = None
mcp_servers = []
server_names = []

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

    if not main_agent:
        await update.message.reply_text("죄송합니다. 에이전트가 아직 준비되지 않았습니다.")
        return

    processing_message = await update.message.reply_text("🔄 생각 중...")

    try:
        start_time = time.perf_counter()
        result = await Runner.run(main_agent, input=user_message)
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        response_text = str(result.final_output)

        logging.info(
            "QnA 처리 완료: duration_ms=%.1f, user='%s', response='%s'",
            duration_ms,
            truncate_for_log(user_message),
            truncate_for_log(response_text)
        )

        await processing_message.delete()
        await update.message.reply_text(response_text)

    except Exception as e:
        logging.error(f"메시지 처리 중 오류 발생: {e}", exc_info=True)
        await processing_message.delete()
        await update.message.reply_text(f"❌ 처리 중 오류가 발생했습니다: {str(e)}")

async def shutdown_servers(app):
    """애플리케이션 종료 시 MCP 서버 연결을 종료합니다."""
    logging.info("MCP 서버 연결을 종료합니다.")
    for server in mcp_servers:
        await server.disconnect()
    logging.info("MCP 서버 연결이 모두 종료되었습니다.")

def main() -> None:
    """봇 실행 메인 함수"""
    global main_agent, mcp_servers, server_names
    
    loop = asyncio.get_event_loop()
    
    try:
        main_agent, mcp_servers, server_names = loop.run_until_complete(setup_agent_and_servers())
    except Exception as e:
        logging.error(f"초기 설정 실패: {e}", exc_info=True)
        return

    # ✅ MCP 서버 tools 목록 출력
    try:
        for i, server in enumerate(mcp_servers):
            tools = loop.run_until_complete(server.list_tools())  # List[Tool]
            
            # mcp_config.json에서 정의한 서버 이름 사용
            if i < len(server_names):
                server_name = server_names[i]
            else:
                server_name = f"MCP Server #{i+1}"
                
            print(f"\n🔧 {server_name} Tools:")
            for tool in tools:
                # print(f"  - {tool.name} : {getattr(tool, 'description', '')}")
                print(f" - {tool.name}")
    except Exception as e:
        logging.error(f'tool 호출 실패: {e}', exc_info=True)
                

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_shutdown(shutdown_servers).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info(f"🤖 AI 에이전트 텔레그램 봇이 시작되었습니다...")
    application.run_polling()

if __name__ == '__main__':
    main()
