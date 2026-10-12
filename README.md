# AI Digest Agent

관심 분야(Tesla, AI 트렌드)의 뉴스를 매일 자동으로 수집해
읽기 좋은 다이제스트로 만드는 개인 에이전트 프로젝트.

## v0 — RSS 수집기 (현재)

- Google News RSS에서 최근 24시간 기사를 수집
- 주제별 최대 10건, 중복 제거, Markdown 저장
- API 키 불필요, 비용 0원

### 실행 방법

```bash
pip install -r requirements.txt
python digest.py
# → digests/YYYY-MM-DD.md 생성
```

## 로드맵

- **v1**: LLM 한 줄 요약 추가 (각 기사에 한국어 요약 1줄)
- **v2**: 매일 아침 자동 실행 (cron) + 결과를 메신저/이메일로 전달
- **v3**: GitHub 공개, 관심 주제 추가, 주간 트렌드 리포트

## 배우는 것

- RSS/피드 파싱, 데이터 수집 파이프라인의 기본 구조
- 입력 → 처리 → 출력으로 문제를 나누는 에이전트 설계 감각
- "어디까지 자동화할지" 판단 경계 정하기 (v1의 요약 품질 기준 등)
