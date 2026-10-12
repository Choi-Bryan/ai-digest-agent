"""
summarizer.py — Gemini API로 영어 헤드라인을 한국어 한 줄로 요약.

사용법:
    export GEMINI_API_KEY='발급받은_키'
    from summarizer import summarize_titles
    summaries = summarize_titles(["Tesla cuts prices...", "..."])

설계 노트:
- 20건을 한 번에 묶어 1회 호출로 처리 (API 호출 최소화 = 비용·속도·할당량 절약)
- 키는 코드에 직접 적지 않고 환경변수에서 읽음 (보안 기본기)
"""

import json
import os
import re
import time
import http.client
import urllib.request
import urllib.error

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


def _call_gemini(prompt, retries=3):
    """
    Gemini API에 프롬프트를 보내고 텍스트 응답을 반환.
    일시적 오류(503, 타임아웃 등)에는 백오프로 재시도한다.
    매일 자동 실행되는 에이전트이므로, 일시 장애에 바로 죽지 않게 하는 것이 중요.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY 환경변수가 없습니다. "
            "export GEMINI_API_KEY='키' 로 설정해주세요."
        )
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    req = urllib.request.Request(
        API_URL + "?key=" + api_key,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            # 400번대(429 제외)는 요청 자체의 문제라 재시도해도 소용없음.
            # 단, 응답 본문을 남겨 원인을 파악할 수 있게 함.
            detail = e.read().decode("utf-8", errors="replace")[:300]
            last_err = f"HTTP {e.code}: {detail}"
            if e.code != 429 and 400 <= e.code < 500:
                raise RuntimeError(f"Gemini API 요청 오류 (재시도 안 함): {last_err}")
            wait = 30 * (attempt + 1)
            print(f"  API 일시 오류 ({last_err}). {wait}초 후 재시도 ({attempt + 1}/{retries})")
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError,
                ConnectionError, http.client.HTTPException) as e:
            last_err = e
            wait = 30 * (attempt + 1)
            print(f"  API 일시 오류 ({e}). {wait}초 후 재시도 ({attempt + 1}/{retries})")
            time.sleep(wait)
    raise RuntimeError(f"Gemini API 호출 실패 (재시도 {retries}회): {last_err}")


def summarize_titles(titles):
    """
    [v1 함수 — v1.5에서 analyze_titles로 대체됨. 호환용으로 유지]
    헤드라인 리스트를 받아 한국어 한 줄 요약 리스트로 반환.
    """
    return [r["summary"] for r in analyze_titles(titles)]


def analyze_titles(titles):
    """
    헤드라인별 (한국어 한 줄 요약, 중요도 1~5)를 반환.
    중요도 기준은 이 에이전트의 '판단 기준' — 필요하면 이 프롬프트를 고치면 된다.
    """
    if not titles:
        return []

    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
    prompt = (
        "다음 뉴스 헤드라인들(영어·한국어·일본어)을 분석해줘. 각 항목에 한국어 한 줄 요약과 중요도 점수를 매겨줘.\n"
        "중요도 기준 (독자: AI 엔지니어 / AX 리더 — AI 시스템을 설계·운영하고 조직의 AI 전환을 이끄는 사람):\n"
        "- 5: 실무에 직접 영향 (새 모델·프레임워크 릴리스, 에이전트 기술, 평가/운영 방법론)\n"
        "- 4: 기술·업계 흐름을 보여주는 굵직한 소식 (대형 인수, 플랫폼 전략, 정책 변화)\n"
        "- 3: 알아두면 좋은 기술 소식\n"
        "- 2: 화제성 위주, 실무 관련 낮음\n"
        "- 1: 광고성·낚시성·관련도 낮음\n"
        "출력 형식 (반드시 엄수, 한 줄에 하나씩):\n"
        "1. 요약문 | 5\n"
        "2. 요약문 | 3\n"
        "요약 규칙: 40자 이내, 객관적 서술, 헤드라인에 없는 내용 지어내지 말기.\n\n"
        + numbered
    )
    raw = _call_gemini(prompt)

    results = [{"summary": "", "importance": 3} for _ in titles]
    for line in raw.strip().split("\n"):
        m = re.match(r"\s*(\d+)[.\)]\s*(.+?)\s*\|\s*([1-5])\s*$", line)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(titles):
                results[idx] = {"summary": m.group(2).strip(),
                                "importance": int(m.group(3))}
    return results


def write_overviews(items):
    """
    선별된 기사의 3문장 개요를 작성.
    items: [{"title": ..., "description": ...}] — 설명문은 RSS에서 가져온 원문 보조 정보.
    규칙상 주어진 정보 밖은 지어내지 않으므로, 정보가 없으면 개요도 짧아진다.
    """
    if not items:
        return []

    blocks = []
    for i, item in enumerate(items):
        desc = item.get("description") or "(설명문 없음)"
        blocks.append(f"[{i + 1}]\n헤드라인: {item['title']}\n설명문: {desc}")
    prompt = (
        "다음 뉴스들에 대해 각각 한국어 3문장 개요를 써줘.\n"
        "규칙:\n"
        "- 주어진 헤드라인·설명문의 정보만 사용. 추측하거나 지어내지 말기\n"
        "- 1문장: 무슨 일인지 / 2문장: 배경·맥락 / 3문장: 왜 주목할 만한지\n"
        "- 항목당 200자 이내\n"
        "출력 형식 (반드시 엄수, 항목당 3문장을 한 줄로):\n"
        "[1] 개요문장1 개요문장2 개요문장3\n"
        "[2] 개요문장1 개요문장2 개요문장3\n\n"
        + "\n\n".join(blocks)
    )
    raw = _call_gemini(prompt)

    overviews = [""] * len(items)
    for line in raw.strip().split("\n"):
        m = re.match(r"\s*\[(\d+)\]\s*(.+)", line)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(items):
                overviews[idx] = m.group(2).strip()
    return overviews
