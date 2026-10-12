#!/usr/bin/env python3
"""
AI Digest Agent v0
==================
RSS 피드에서 Tesla / AI 트렌드 뉴스를 수집해
일일 다이제스트(Markdown)로 만드는 스크립트.

- API 키 불필요 (RSS만 사용, 비용 0원)
- 실행:  python digest.py
- 결과:  digests/YYYY-MM-DD.md
"""

import re

import feedparser
from datetime import datetime, timedelta, timezone
from pathlib import Path

import summarizer  # v1: Gemini 한 줄 요약, v1.5: 중요도 분석 + 심층 개요

# 수집할 RSS 피드 (주제: 피드 URL) — v2: Tesla 제외, AI 트렌드를 영/한/일 3개 언어로
FEEDS = {
    "AI 트렌드 (EN)": "https://news.google.com/rss/search?q=%22artificial+intelligence%22&hl=en-US&gl=US&ceid=US:en",
    "AI 트렌드 (KO)": "https://news.google.com/rss/search?q=%EC%9D%B8%EA%B3%B5%EC%A7%80%EB%8A%A5&hl=ko&gl=KR&ceid=KR:ko",
    "AI 트렌드 (JA)": "https://news.google.com/rss/search?q=%E4%BA%BA%E5%B7%A5%E7%9F%A5%E8%83%BD&hl=ja&gl=JP&ceid=JP:ja",
}


MAX_PER_TOPIC = 10    # 주제별 최대 기사 수
LOOKBACK_HOURS = 24   # 최근 N시간 이내 기사만 수집


def _strip_html(text):
    """RSS 설명문에 섞인 HTML 태그 제거."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def fetch_recent(feed_url, since):
    """피드에서 since 이후 발행된 기사를 수집해 최신순으로 반환."""
    items = []
    feed = feedparser.parse(feed_url)
    for entry in feed.entries:
        published = None
        if getattr(entry, "published_parsed", None):
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if published and published >= since:
            items.append({
                "title": entry.title,
                "link": entry.link,
                "published": published,
                # v1.5: 심층 개요의 근거 자료 (없을 수도 있음)
                "description": _strip_html(
                    getattr(entry, "summary", "") or getattr(entry, "description", "")
                ),
            })
    items.sort(key=lambda x: x["published"], reverse=True)
    return items


def dedupe(items):
    """링크 기준 중복 제거 (순서 유지)."""
    seen, out = set(), []
    for item in items:
        if item["link"] not in seen:
            seen.add(item["link"])
            out.append(item)
    return out


def render_markdown(digest):
    """수집 결과를 Markdown 다이제스트로 변환."""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# AI Digest — {today}", ""]
    for topic, items in digest.items():
        lines.append(f"## {topic} ({len(items)}건)")
        lines.append("")
        for item in items:
            ts = item["published"].strftime("%m-%d %H:%M")
            star = "⭐ " if item.get("overview") else ""
            lines.append(f"- {star}[{item['title']}]({item['link']}) `{ts} UTC`")
            if item.get("summary"):
                lines.append(f"  > {item['summary']}")
            if item.get("overview"):
                lines.append(f"  > {item['overview']}")
        lines.append("")
    return "\n".join(lines)


def main():
    since = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    digest = {}
    for topic, url in FEEDS.items():
        items = dedupe(fetch_recent(url, since))[:MAX_PER_TOPIC]
        digest[topic] = items
        print(f"[{topic}] {len(items)}건 수집")

    # v1.5: 2단 구조 — 전수 한 줄 요약 + 중요도 상위 N건 심층 개요
    # v1.6: 중요도 1점(노이즈)은 다이제스트에서 제외
    TOP_N_PER_TOPIC = 3
    deep_targets = []  # 심층 개요 대상 기사들
    for topic, items in digest.items():
        titles = [it["title"] for it in items]
        print(f"[{topic}] 분석 중...")
        analyzed = []
        for item, result in zip(items, summarizer.analyze_titles(titles)):
            item["summary"] = result["summary"]
            item["importance"] = result["importance"]
            if result["importance"] > 1:
                analyzed.append(item)
        digest[topic] = analyzed
        ranked = sorted(analyzed, key=lambda x: x["importance"], reverse=True)
        deep_targets.extend(ranked[:TOP_N_PER_TOPIC])
        print(f"[{topic}] 분석 완료 ({len(items)}건 중 {len(analyzed)}건 유지)")

    if deep_targets:
        print(f"[심층] {len(deep_targets)}건 개요 작성 중...")
        overviews = summarizer.write_overviews([
            {"title": it["title"], "description": it.get("description", "")}
            for it in deep_targets
        ])
        for item, overview in zip(deep_targets, overviews):
            item["overview"] = overview
        print("[심층] 개요 작성 완료")

    markdown = render_markdown(digest)
    outdir = Path("digests")
    outdir.mkdir(exist_ok=True)
    outpath = outdir / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    outpath.write_text(markdown, encoding="utf-8")
    print(f"저장: {outpath}")


if __name__ == "__main__":
    main()
