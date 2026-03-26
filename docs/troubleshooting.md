
# 🚧 개발 중 시행착오 상세 기록

## 1. Windows PowerShell 실행 정책 오류

**문제**
```
n8n : 이 시스템에서 스크립트를 실행할 수 없으므로 파일을 로드할 수 없습니다.
```

**원인**
Windows PowerShell 기본 보안 정책이 외부 스크립트 실행을 차단

**해결**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## 2. n8n 초기 설정 무한 로딩

**문제**
`http://localhost:5678` 접속 시 Set up owner account 화면에서 무한 로딩

**해결**
```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.n8n"
n8n start
```

---

## 3. Slack Socket Mode → Cloudflare Tunnel 전환

**원래 목표**
Slack 메시지를 n8n이 직접 수신하는 구조

**시도 1 - Slack Socket Mode**
- Bot Token(`xoxb-`) + App Token(`xapp-`) 정상 입력
- `Connection tested successfully` 뜨고 연결은 됐으나 실제 메시지 이벤트 수신 안 됨
- n8n 2.8.4 버전에서 Socket Mode WebSocket 연결 유지 버그로 추정

**시도 2 - 외부 URL 확보 (Webhook 방식)**

Slack이 n8n으로 직접 HTTP 요청을 보내려면 외부에서 접근 가능한 URL이 필요

| 방법 | 결과 | 원인 |
|---|---|---|
| ngrok | 실패 | 회사 방화벽 QUIC 프로토콜 차단 |
| localtunnel | 실패 | 비밀번호 확인 화면으로 Slack URL 검증 실패 + 503 빈번 |
| n8n Cloud | 포기 | 유료 플랜 필요 |

**최종 해결 - Cloudflare Tunnel**
```powershell
cloudflared tunnel --url http://localhost:5678 --protocol http2
```
- `--protocol http2` 옵션으로 회사 방화벽 QUIC 차단 우회
- 비밀번호 없이 바로 접근 가능한 외부 HTTPS URL 생성
- ⚠️ 실행할 때마다 URL이 바뀌므로 Slack App Request URL 매번 업데이트 필요

---

## 4. Slack Challenge 검증 실패

**문제**
Slack Event Subscriptions URL 등록 시:
```
Your URL didn't respond with the value of the `challenge` parameter.
```

**원인**
Slack이 URL 등록 시 `url_verification` 타입의 POST 요청을 보내고 `challenge` 값을 응답으로 기대함. n8n Slack Trigger 노드가 이를 자동 처리하지 못함

**해결**
Webhook 노드 + Code 노드에서 직접 처리:
```javascript
if (body.type === 'url_verification') {
  return [{ json: { isChallenge: true, challenge: body.challenge } }];
}
```

---

## 5. Slack 무한 루프 (중복 응답)

**문제**
메시지 하나를 보내면 수십 개의 응답이 반복 전송

**원인 1 - Slack 재시도**
Claude API 처리 시간이 3초를 초과하면 Slack이 응답 실패로 판단하고 재시도

**해결 1**
Respond to Webhook 노드를 If 분기 직후로 이동해서 즉시 200 OK 반환 후 나머지 처리

**원인 2 - 봇 메시지 루프**
QueryBot이 채널에 보낸 메시지도 `message.channels` 이벤트로 감지되어 무한 루프 발생

**해결 2**
```javascript
const botId = event.bot_id;
if (botId || subtype === 'bot_message' || !text) {
  return [{ json: { isChallenge: true, challenge: '' } }];
}
```

---

## 6. AI API 선택 문제

| 시도 | 결과 | 원인 |
|---|---|---|
| Claude API | 초기 실패 | 크레딧 없음 → $5 충전 후 해결 |
| Gemini API | 실패 | 한국 무료 티어 차단 (`limit: 0`) |
| Ollama llama3.2 | 실패 | CPU 95% (Ryzen 7 4700U + 내장 그래픽 한계) |

**최종 해결**
Claude API $5 크레딧 충전. 요청당 약 $0.01 수준으로 경제적

---

## 7. Confluence 스키마 조회 방식

**문제**
keyword 기반 검색(`?keyword=테이블`)은 실제 테이블명과 무관한 결과 반환

**해결**
최상단 pageId 기준 하위 페이지 전체를 재귀적으로 조회:
```python
def get_all_child_pages(page_id, depth=0, max_depth=3):
    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}/child/page"
    ...
```

---

## 8. n8n에서 localhost 연결 오류

**문제**
```
connect ECONNREFUSED ::1:5000
```

**원인**
n8n이 내부적으로 IPv6(`::1`)로 localhost를 해석하는데 Flask 서버는 IPv4(`127.0.0.1`)에서만 실행 중

**해결**
모든 HTTP Request 노드 URL에서 `localhost` → `127.0.0.1` 변경

---

## 9. Gmail OAuth 실패

**문제**
```
Problem creating credential - Can't connect to n8n
401 오류: invalid_client
```

**원인**
Google OAuth는 localhost 환경에서 콜백 URL을 신뢰하지 않음

**해결**
알람 채널을 Gmail → Slack Send Message로 변경. Slack Bot Token 방식은 OAuth 불필요
```
