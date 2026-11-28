# OpenAI API 서버 설정 가이드

현재는 시뮬레이션 모드로 작동합니다. 실제 AI 내담자와 슈퍼비전을 사용하려면 API 서버를 배포해야 합니다.

## 🎯 준비물

1. **OpenAI API 키**
   - https://platform.openai.com/api-keys 에서 발급
   - 결제 정보 등록 필요 (실습 1회당 약 ₩45)

2. **Cloudflare 계정** (무료)
   - https://cloudflare.com 가입
   - 신용카드 불필요

## 🚀 방법 1: 자동 배포 (권장)

### 1단계: Wrangler CLI 설치

```bash
npm install -g wrangler
```

### 2단계: 프로젝트 폴더로 이동

```bash
cd virtual-counseling-lab/api-proxy
```

### 3단계: 자동 배포 스크립트 실행

```bash
./deploy.sh
```

스크립트가:
- ✅ Cloudflare 로그인
- ✅ OpenAI API 키 입력 받기
- ✅ Workers 배포
- ✅ URL 출력

### 4단계: HTML 파일 설정

배포 후 출력된 Worker URL을 복사하고:

```bash
# 자동 설정
WORKER_URL="https://your-worker.workers.dev"
sed -i "s|API_BASE_URL = null|API_BASE_URL = \"$WORKER_URL\"|" ../EC-01.html
sed -i "s|API_BASE_URL = null|API_BASE_URL = \"$WORKER_URL\"|" ../../docs/index.html

# Git 커밋
git add ../EC-01.html ../../docs/index.html
git commit -m "feat: OpenAI API 서버 연결"
git push
```

완료! 🎉

---

## 🔧 방법 2: 수동 배포

### 1단계: Cloudflare 로그인

```bash
wrangler login
```

### 2단계: OpenAI API 키 설정

```bash
wrangler secret put OPENAI_API_KEY
# 프롬프트가 나오면 API 키 입력
```

### 3단계: Workers 배포

```bash
cd virtual-counseling-lab/api-proxy
wrangler deploy cloudflare-worker.js
```

배포 후 URL 확인:
```
✨  Uploaded virtual-counseling-lab-api
✨  Published virtual-counseling-lab-api
   https://virtual-counseling-lab-api.your-subdomain.workers.dev
```

### 4단계: HTML 파일 수정

**EC-01.html** 파일을 열고 (약 1162번째 줄):

```javascript
// 변경 전
const API_BASE_URL = null; // null이면 시뮬레이션 모드

// 변경 후
const API_BASE_URL = 'https://virtual-counseling-lab-api.your-subdomain.workers.dev';
```

**docs/index.html**도 동일하게 수정

### 5단계: 커밋 및 푸시

```bash
git add virtual-counseling-lab/EC-01.html docs/index.html
git commit -m "feat: OpenAI API 서버 연결"
git push
```

---

## 🖥️ 방법 3: Express 서버 (학교 서버용)

학교에서 자체 서버를 운영하는 경우:

### 1단계: 서버에 Node.js 설치

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nodejs npm
```

### 2단계: 프로젝트 설정

```bash
cd virtual-counseling-lab/api-proxy
npm install

# .env 파일 생성
cp .env.example .env
nano .env
# OPENAI_API_KEY=sk-proj-your-key-here 입력
```

### 3단계: 서버 실행

```bash
# 개발 모드
npm run dev

# 프로덕션 모드
npm start

# 백그라운드 실행 (PM2 사용)
npm install -g pm2
pm2 start express-server.js --name virtual-counseling-api
pm2 save
pm2 startup
```

### 4단계: HTML 설정

```javascript
const API_BASE_URL = 'http://your-server.com:3000';
```

---

## ✅ 테스트

배포 후 브라우저에서 접속:

1. **내담자 응답 테스트**
   ```bash
   curl -X POST https://your-worker.workers.dev \
     -H "Content-Type: application/json" \
     -d '{
       "action": "client-response",
       "messages": [{"role": "user", "content": "안녕하세요"}],
       "systemPrompt": "당신은 김순자입니다..."
     }'
   ```

2. **웹페이지 테스트**
   - EC-01.html 열기
   - 상담 시작
   - 내담자 응답이 실제 AI로 생성되는지 확인

---

## 💰 비용 예상

### OpenAI API 사용료

| 항목 | 모델 | 예상 비용 |
|------|------|-----------|
| 내담자 응답 15회 | GPT-4o-mini | $0.003 |
| 슈퍼비전 1회 | GPT-4o | $0.030 |
| **실습 1회 합계** | | **$0.033 (₩45)** |

### Cloudflare Workers

| 항목 | 무료 플랜 | 유료 플랜 |
|------|-----------|-----------|
| 요청 수 | 100,000/일 | 무제한 |
| 월 비용 | $0 | $5 |

**30명 학생, 각 3회 실습 = 약 ₩4,000/월**

---

## 🔒 보안 확인

- ✅ API 키는 환경 변수로 관리 (절대 HTML에 넣지 않음)
- ✅ CORS 설정으로 허용된 도메인만 접근
- ✅ Rate Limiting으로 과도한 요청 방지
- ✅ 비용 한도 설정 (OpenAI 대시보드에서)

---

## 🐛 트러블슈팅

### "insufficient_quota" 오류
→ OpenAI 계정에 결제 정보 등록 필요

### "401 Unauthorized"
→ API 키 확인: `wrangler secret put OPENAI_API_KEY`

### "CORS 오류"
→ Worker의 corsHeaders 설정 확인

### "JSON parse error"
→ 시스템 프롬프트에 JSON 형식 명시 확인

---

## 📞 도움이 필요하면

1. 이슈 등록: https://github.com/seahog77/test/issues
2. 문서 참조: `DEPLOYMENT.md`
3. API 문서: `api-proxy/README.md`

---

## 🎉 완료 후

실습실이 이제 **실제 AI**로 작동합니다!

- 🤖 더 자연스러운 내담자 응답
- 📊 정확한 슈퍼비전 피드백
- 🎯 실제 상담에 가까운 경험
