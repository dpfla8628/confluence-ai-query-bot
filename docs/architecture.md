
# 🏗️ 아키텍처 상세 설명

## 전체 흐름 요약

```
[Slack 모바일/PC]
       │ 메시지 전송
       ▼
[Slack API 서버]
       │ HTTP POST (Event)
       ▼
[Cloudflare Tunnel]
       │ 로컬 PC를 외부 HTTPS URL로 노출
       ▼
[n8n :5678]
       │
       ├── Webhook 노드 수신
       ├── Challenge 검증 / 봇 메시지 필터링
       ├── 즉시 200 OK 반환 (Slack 재시도 방지)
       │
       ├── HTTP Request → [Confluence MCP :5000]
       │                        │
       │                        └── Confluence REST API
       │                            최상단 pageId 기준
       │                            하위 페이지 전체 재귀 조회
       │
       ├── Claude API Body 생성 (스키마 + 질문 조합)
       │
       ├── HTTP Request → LLM 처리[Claude API]
       │                  자연어 → SQL 변환
       │
       └── Slack Send Message → [#data-query 채널]
```

---

## n8n 워크플로우 노드 구성

| 순서 | 노드명 | 타입 | 역할 |
|---|---|---|---|
| 1 | Webhook | Webhook | Slack 이벤트 수신 (`POST /webhook/slack-events`) |
| 2 | Code in JavaScript | Code | Challenge 검증 / 봇 메시지 필터링 |
| 3 | If | If | 일반 메시지 여부 분기 |
| 4 | Respond to Webhook (True) | Respond to Webhook | Challenge 값 반환 |
| 5 | Respond to Webhook (False) | Respond to Webhook | 즉시 200 OK 반환 |
| 6 | HTTP Request | HTTP Request | Confluence MCP 서버 호출 |
| 7 | Code in JavaScript | Code | Claude API Body 생성 |
| 8 | HTTP Request | HTTP Request | Claude API 호출 |
| 9 | Send a message | Slack | 결과 전송 |

---

## 컴포넌트별 역할

### Cloudflare Tunnel
- 로컬 PC의 n8n(`localhost:5678`)을 외부 HTTPS URL로 노출
- Slack 서버가 로컬 n8n으로 직접 HTTP 요청을 전달할 수 있게 함
- 실행할 때마다 URL이 바뀌므로 Slack App Request URL 업데이트 필요
- `--protocol http2` 옵션으로 회사 방화벽 QUIC 차단 우회

### Webhook 노드
- Slack 이벤트 수신 엔드포인트
- `POST /webhook/slack-events`

### Code 노드 (Challenge 처리 + 봇 필터링)
- Slack URL 등록 시 `url_verification` challenge 값 응답
- `bot_id` 존재 여부로 봇 메시지 감지 → 무한 루프 방지
- 빈 메시지 필터링

### Respond to Webhook 노드 (즉시 200 OK)
- Slack은 3초 내 응답 없으면 재시도 → 중복 실행 발생
- Claude API 처리 시간이 3초를 초과하므로 즉시 200 반환 후 나머지 처리

### Confluence MCP 서버 (Python Flask)
- Confluence REST API를 래핑한 로컬 서버 (포트 5000)
- 최상단 pageId(`186452952`) 기준 하위 페이지 전체를 재귀적으로 조회
- HTML 태그 제거 후 순수 텍스트로 변환하여 Claude에 전달
- 토큰 제한으로 최대 15,000자로 truncate

### Claude API
- 모델: `claude-opus-4-5`
- Confluence 스키마를 system prompt에 주입
- 출력 형식: `{"db_type": "oracle" | "db2", "sql": "..."}`
- 실제 테이블명/컬럼명만 사용하도록 프롬프트 구성

### Slack Send Message
- Bot Token(`xoxb-`) 방식으로 인증
- 메시지가 온 채널 ID로 직접 답장

---

## 포트 구성

| 서비스 | 포트 | 비고 |
|---|---|---|
| n8n | 5678 | 워크플로우 엔진 |
| Confluence MCP 서버 | 5000 | Python Flask |
| Cloudflare Tunnel | - | 외부 HTTPS URL → localhost:5678 |

---

## 주요 설계 결정

### DB 직접 실행 하지 않는 이유
운영 DB(DB2, Oracle)에 직접 접근하지 않고 SQL만 생성해서 전달합니다.
보안 리스크를 최소화하고 실제 실행은 담당자가 검토 후 진행합니다.

### Confluence 전체 페이지 재귀 조회 이유
keyword 기반 검색은 검색어에 따라 결과가 달라져 부정확합니다.
최상단 페이지 하위 전체를 가져오면 어떤 질문에도 관련 스키마를 찾을 수 있습니다.

### 즉시 200 OK 후 비동기 처리
Slack의 3초 응답 제한을 우회하기 위해 Respond to Webhook으로 먼저 응답하고,
이후 Confluence 조회 → Claude API → Slack 전송을 순차 처리합니다.
```
