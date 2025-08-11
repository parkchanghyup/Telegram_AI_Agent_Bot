# Telegram MCP Bot

이 프로젝트는 Naver 뉴스 검색 기능을 갖춘 AI 에이전트를 텔레그램 봇과 연동한 것입니다.

## 🚀 실행 방법

### 1. 환경변수 설정

`.env.example` 파일의 복사본을 만들어 `.env` 라는 이름으로 저장한 후, 파일 안의 값들을 자신의 API 키와 토큰으로 채워주세요.

```bash
cp .env.example .env
```

- `TELEGRAM_BOT_TOKEN`: 텔레그램 BotFather로부터 발급받은 토큰
- `OPENAI_API_KEY`: OpenAI API 키
- `NAVER_CLIENT_ID`: 네이버 개발자 센터에서 발급받은 클라이언트 ID
- `NAVER_CLIENT_SECRET`: 네이버 개발자 센터에서 발급받은 클라이언트 시크릿

### 2. 라이브러리 설치

프로젝트에 필요한 파이썬 라이브러리들을 설치합니다.

```bash
pip install -r requirements.txt
```

### 3. MCP 서버 설정 (필요시)

`mcp_config.json` 파일은 기본적으로 `python` 명령어를 사용하여 MCP 서버를 실행하도록 설정되어 있습니다. 만약 가상환경(venv)의 파이썬을 사용하거나 특정 파이썬 실행 파일 경로를 지정해야 할 경우, `command` 값을 수정해주세요.

**예시 (가상환경 사용시):**
```json
{
    "mcpServers": {
      "naver-search": {
        "command": "./venv/bin/python",
        "args": [
          "naver_mcp_server.py"
        ]
      }
    }
}
```

### 4. 봇 실행

모든 설정이 완료되었으면, 텔레그램 클라이언트 봇을 실행합니다.

```bash
python telegram_bot_client.py
```

봇이 성공적으로 실행되면, 텔레그램에서 봇에게 메시지를 보내 테스트할 수 있습니다.
