# API Proxy Server

가상내담자 상담실습실의 API 프록시 서버입니다.

## 파일 설명

- `cloudflare-worker.js`: Cloudflare Workers 버전 (권장)
- `express-server.js`: Node.js + Express 버전
- `package.json`: Node.js 의존성 정보
- `.env.example`: 환경 변수 예시

## 🚀 빠른 시작 (Express 서버)

### 1. 의존성 설치

```bash
npm install
```

### 2. 환경 변수 설정

```bash
# .env.example을 .env로 복사
cp .env.example .env

# .env 파일을 열어 OpenAI API 키 입력
# OPENAI_API_KEY=sk-proj-your-key-here
```

### 3. HTML 파일 준비

```bash
# public 폴더 생성
mkdir public

# 프로젝트 루트의 HTML 파일들을 public 폴더로 복사
cp ../EC-*.html public/
```

### 4. 서버 실행

```bash
npm start
```

서버가 `http://localhost:3000`에서 실행됩니다.

### 5. 테스트

브라우저에서 접속:
- http://localhost:3000/EC-01.html

## 🌐 Cloudflare Workers 배포

### 1. Wrangler CLI 설치

```bash
npm install -g wrangler
```

### 2. Cloudflare 로그인

```bash
wrangler login
```

### 3. 환경 변수 설정

```bash
# OpenAI API 키를 Workers Secret으로 설정
wrangler secret put OPENAI_API_KEY
# 프롬프트가 나오면 API 키 입력
```

### 4. Worker 배포

```bash
wrangler deploy cloudflare-worker.js
```

배포 후 Worker URL이 표시됩니다:
```
https://your-worker-name.your-subdomain.workers.dev
```

### 5. HTML 파일에서 사용

EC-01.html 파일을 열어서 API URL을 Worker URL로 수정:

```javascript
// HTML 파일 내에서 이 부분을 찾아 수정
const API_BASE_URL = 'https://your-worker-name.your-subdomain.workers.dev';
```

## 📊 API 엔드포인트

### POST /api/client-response (Express) 또는 POST / (Workers)

내담자 응답 생성

**요청 본문:**
```json
{
  "action": "client-response",
  "messages": [
    { "role": "user", "content": "안녕하세요" }
  ],
  "systemPrompt": "당신은 김순자입니다..."
}
```

**응답:**
```json
{
  "reply": "(가방을 만지작거리며) ...딸이 가보라 캐서 오긴 왔는데요."
}
```

### POST /api/supervision (Express) 또는 POST / (Workers)

슈퍼비전 피드백 생성

**요청 본문:**
```json
{
  "action": "supervision",
  "messages": [
    { "role": "user", "content": "축어록:\n상담자 1: ...\n\n학생 사례개념화:\n..." }
  ],
  "systemPrompt": "당신은 슈퍼바이저입니다..."
}
```

**응답:**
```json
{
  "feedback": {
    "summary": "...",
    "ratings": [...],
    "crisis": {...},
    ...
  }
}
```

## 🔧 개발 모드 (Express)

코드 변경 시 자동 재시작:

```bash
npm run dev
```

## 🐛 트러블슈팅

### "insufficient_quota" 오류
- OpenAI 계정에 결제 정보 등록 필요
- https://platform.openai.com/account/billing

### "CORS 오류"
- Express: `cors` 미들웨어 확인
- Workers: `corsHeaders` 설정 확인

### "JSON parse error"
- `response_format: { type: 'json_object' }` 옵션 확인
- 시스템 프롬프트에 JSON 형식 출력 명시

### 서버가 시작되지 않음
- `.env` 파일에 `OPENAI_API_KEY` 설정 확인
- 포트 3000이 이미 사용 중이면 `.env`에서 `PORT` 변경

## 📝 참고

자세한 배포 가이드는 프로젝트 루트의 `DEPLOYMENT.md`를 참조하세요.
