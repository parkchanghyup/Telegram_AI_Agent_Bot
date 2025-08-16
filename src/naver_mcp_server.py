import os
import re
import time
import logging
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
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

def _fetch_article_content(url: str) -> str:
    """뉴스 URL에 접속하여 본문 내용을 가져옵니다."""
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 다양한 뉴스 플랫폼에 대응하기 위한 선택자 리스트
        selectors = [
            'article#dic_area',                 # 네이버 뉴스
            'div#newsct_article',               # 네이버 뉴스
            'div.article_body',                 # 일반적인 클래스
            'div#article_body',                 # ID 형식
            'div#articleBodyContents',          # 연합뉴스 등
            'div.article_view',                 # 여러 언론사
            'div.article-view-content-wrapper', # ITWorld
            'div#content',                      # 일반적인 ID
            'div.entry-content',                # 블로그/워드프레스 기반 사이트
            'div.post-content',                 # 블로그/워드프레스 기반 사이트
            'div#main-content',                 # 일반적인 ID
            'article',                          # 시맨틱 태그
            'main'                              # 시맨틱 태그
        ]

        article_body = None
        for selector in selectors:
            article_body = soup.select_one(selector)
            if article_body:
                break

        if article_body:
            # 본문 내용에서 불필요한 태그(스크립트, 스타일, 광고 등) 제거
            for tag in article_body.find_all(['script', 'style', 'iframe', 'aside', 'footer', 'header', 'nav']):
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
    display_count = 5  # 가져올 뉴스 기사 수를 5개로 고정
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise ValueError("환경변수 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET가 설정되지 않았습니다.")

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": query, "display": display_count, "sort": "date"}

    # --- 1. Naver API 호출 시간 측정 ---
    api_start_time = time.perf_counter()
    logger.info("Naver API 호출 시작: query='%s', display=%d", query, display_count)
    try:
        response = requests.get(BASE_URL, headers=headers, params=params, timeout=15)
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
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("환경변수 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET를 .env 파일에 설정해주세요.")
    else:
        print("Naver 뉴스 검색 MCP 서버를 시작합니다...")
        mcp.run()
