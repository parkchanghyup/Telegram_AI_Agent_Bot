import os
import re
import time
import logging
from typing import List, Dict
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# Configure file-based logging for the MCP server
os.makedirs('logs', exist_ok=True)
logger = logging.getLogger("naver_mcp_server")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler('logs/naver_mcp_server.log', encoding='utf-8')
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

mcp = FastMCP("naver_search_server")

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
BASE_URL = "https://openapi.naver.com/v1/search/news.json"

def _remove_html_tags(text: str) -> str:
    """HTML 태그를 제거합니다."""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def _clean_news_data(items: List[Dict]) -> List[Dict]:
    """뉴스 데이터에서 HTML 태그를 제거하고 필요한 정보만 추출합니다."""
    cleaned_items = []
    for item in items:
        cleaned_item = {
            "title": _remove_html_tags(item.get("title", "")),
            "link": item.get("link", ""),
            "description": _remove_html_tags(item.get("description", "")),
            "pubDate": item.get("pubDate", "")
        }
        cleaned_items.append(cleaned_item)
    return cleaned_items

@mcp.tool()
def search_naver_news(query: str, display: int = 5) -> List[Dict]:
    """네이버에서 특정 키워드로 뉴스를 검색합니다."""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise ValueError("환경변수 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET가 설정되지 않았습니다.")

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    params = {
        "query": query,
        "display": display,
        "sort": "date"
    }
    
    try:
        start_time = time.perf_counter()
        logger.info("Naver API 호출 시작: query='%s', display=%s", query, display)
        response = requests.get(BASE_URL, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        cleaned = _clean_news_data(data.get("items", []))
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info("Naver API 호출 성공: duration_ms=%.1f, result_count=%d", duration_ms, len(cleaned))
        return cleaned
    except requests.exceptions.RequestException as e:
        logger.error("Naver API 요청 오류: %s", str(e))
        return []

if __name__ == "__main__":
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("환경변수 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET를 .env 파일에 설정해주세요.")
    else:
        print("Naver 뉴스 검색 MCP 서버를 시작합니다...")
        mcp.run()
