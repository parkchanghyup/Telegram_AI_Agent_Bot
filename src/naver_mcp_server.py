import os
import re
import time
import logging
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (
    NAVER_CLIENT_ID,
    NAVER_CLIENT_SECRET,
    NAVER_NEWS_API_URL,
    NAVER_NEWS_DEFAULT_COUNT,
    ARTICLE_FETCH_TIMEOUT,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    LOGS_DIR,
    LOG_FORMAT,
    LOG_ENCODING,
    DEFAULT_LOG_LEVEL,
    ARTICLE_SELECTORS,
    UNWANTED_HTML_TAGS,
    validate_naver_config
)

# Configure file-based logging for the MCP server
logger = logging.getLogger("naver_mcp_server")
if not logger.handlers:
    logger.setLevel(DEFAULT_LOG_LEVEL)
    fh = logging.FileHandler(
        os.path.join(LOGS_DIR, 'naver_mcp_server.log'), 
        encoding=LOG_ENCODING
    )
    fh.setLevel(DEFAULT_LOG_LEVEL)
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(fh)

mcp = FastMCP("naver_search_server")

def _fetch_article_content(url: str) -> str:
    """뉴스 URL에 접속하여 본문 내용을 가져옵니다."""
    try:
        response = requests.get(
            url, 
            timeout=ARTICLE_FETCH_TIMEOUT, 
            headers={'User-Agent': DEFAULT_USER_AGENT}
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        article_body = None
        for selector in ARTICLE_SELECTORS:
            article_body = soup.select_one(selector)
            if article_body:
                break

        if article_body:
            # 본문 내용에서 불필요한 태그 제거
            for tag in article_body.find_all(UNWANTED_HTML_TAGS):
                tag.decompose()
            
            # 텍스트 추출
            return article_body.get_text(separator='\n', strip=True)

        return "본문 내용을 찾을 수 없습니다."
    except requests.exceptions.RequestException as e:
        logger.warning("뉴스 본문(%s)을 가져오는 중 오류 발생: %s", url, e)
        return "본문을 가져오는 데 실패했습니다."

@mcp.tool()
def search_naver_news(query: str) -> List[Dict]:
    """네이버에서 특정 키워드로 뉴스를 검색하고, 각 기사의 본문을 추출합니다."""
    # Naver API 설정 검증
    validate_naver_config()

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": query, 
        "display": NAVER_NEWS_DEFAULT_COUNT, 
        "sort": "date"
    }

    # --- 1. Naver API 호출 시간 측정 ---
    api_start_time = time.perf_counter()
    logger.info("Naver API 호출 시작: query='%s', display=%d", query, NAVER_NEWS_DEFAULT_COUNT)
    try:
        response = requests.get(
            NAVER_NEWS_API_URL, 
            headers=headers, 
            params=params, 
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        news_items = response.json().get("items", [])
        logger.info("Naver API 응답 (처음 3개): %s", news_items[:3])  # 응답 로깅
    except requests.exceptions.RequestException as e:
        logger.error("Naver API 요청 오류: %s", str(e))
        return []
    finally:
        api_duration_ms = (time.perf_counter() - api_start_time) * 1000.0
        logger.info("Naver API 호출 완료: duration_ms=%.1f", api_duration_ms)

    # --- 2. 뉴스 본문 파싱 시간 측정 ---
    parsing_start_time = time.perf_counter()
    
    results = []
    for item in news_items:
        link = item.get("link", "")
        logger.info(f"뉴스 기사 처리 중: {item.get('title')}, link: {link}") # 각 기사 링크 로깅

        title = item.get("title", "")
        content = _fetch_article_content(link)
        
        results.append({
            "title": title,
            "link": link,
            "content": content
        })

    parsing_duration_ms = (time.perf_counter() - parsing_start_time) * 1000.0
    logger.info("뉴스 본문 파싱 완료: duration_ms=%.1f, 성공=%d/%d", 
                parsing_duration_ms, 
                sum(1 for r in results if "본문 내용을 찾을 수 없습니다" not in r['content'] and "실패했습니다" not in r['content']),
                len(results))

    return results

if __name__ == "__main__":
    import sys
    try:
        validate_naver_config()
        print("Naver 뉴스 검색 MCP 서버를 시작합니다...")
        
        # Check if we should run as HTTP server
        if len(sys.argv) > 1 and sys.argv[1] == "--http":
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001
            print(f"HTTP 모드로 서버 시작 (포트: {port})")
            mcp.run(transport="http", port=port)
        else:
            print("stdio 모드로 서버 시작")
            mcp.run()
    except ValueError as e:
        print(f"설정 오류: {e}")
        print("환경변수 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET를 .env 파일에 설정해주세요.")
