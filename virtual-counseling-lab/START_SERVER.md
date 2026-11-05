# 🚀 서버 실행 가이드

OpenAI API를 사용하는 가상내담자 상담실습실 서버를 실행하는 방법입니다.

## ✅ 이미 완료된 것

- ✅ Express 서버 코드 준비
- ✅ OpenAI API 키 설정 (.env 파일)
- ✅ HTML 파일 연결 완료
- ✅ 의존성 설치 완료

## 🎯 사용 방법

### 1단계: 저장소 클론

```bash
git clone https://github.com/seahog77/test.git
cd test
git checkout cursor/virtual-counseling-lab-8d5b
```

### 2단계: 서버 실행 (매우 간단!)

```bash
cd virtual-counseling-lab/api-proxy
npm start
```

서버가 실행되면 다음과 같이 표시됩니다:
```
✅ 가상내담자 상담실습실 서버 실행 중
📍 주소: http://localhost:3000
🔑 OpenAI API 설정: ✅

학생들에게 제공할 주소:
   - EC-01: http://localhost:3000/EC-01.html
   - EC-02: http://localhost:3000/EC-02.html (예정)

헬스 체크: http://localhost:3000/api/health
```

### 3단계: 실습실 열기

**새 터미널**을 열고:

```bash
cd test/virtual-counseling-lab
open EC-01.html  # Mac
# 또는
xdg-open EC-01.html  # Linux
# 또는
start EC-01.html  # Windows
```

또는 브라우저에서 직접:
- **파일 경로**: `file:///path/to/test/virtual-counseling-lab/EC-01.html`

**완료!** 🎉 이제 실제 AI 내담자와 상담할 수 있습니다.

---

## 📱 학생들에게 제공하기

### 옵션 1: 파일 공유 (간단)

1. `EC-01.html` 파일을 LMS에 업로드
2. 학생들에게 다운로드 후 더블클릭하도록 안내
3. 각자 컴퓨터에서 서버 실행:
   ```bash
   cd api-proxy
   npm install
   npm start
   ```

### 옵션 2: 학교 서버 운영 (권장)

학교 서버에서 실행:

```bash
# 서버에 설치
cd /var/www/virtual-counseling-lab/api-proxy
npm install
npm start

# 또는 백그라운드 실행 (PM2)
npm install -g pm2
pm2 start express-server.js --name counseling-api
pm2 save
pm2 startup
```

학생들 접속:
- **http://your-server.edu:3000/EC-01.html**

### 옵션 3: Cloudflare Workers (무료, 추천)

가장 경제적이고 확장 가능:

```bash
cd api-proxy
wrangler login
wrangler secret put OPENAI_API_KEY  # API 키 입력
wrangler deploy cloudflare-worker.js
```

배포 후 학생들에게 링크만 제공하면 됩니다!

---

## 🔧 서버 관리

### 서버 상태 확인

```bash
curl http://localhost:3000/api/health
```

응답 예시:
```json
{
  "status": "ok",
  "timestamp": "2026-11-05T05:39:33.856Z",
  "openaiConfigured": true
}
```

### 로그 확인

서버를 실행한 터미널에서 실시간 로그를 볼 수 있습니다:
```
[2026-11-05T05:39:33.856Z] POST /api/client-response
[2026-11-05T05:40:12.123Z] POST /api/supervision
```

### 서버 중지

터미널에서 `Ctrl + C`

### 백그라운드 실행 (PM2)

```bash
# 설치
npm install -g pm2

# 시작
pm2 start express-server.js --name counseling-api

# 상태 확인
pm2 status

# 로그 보기
pm2 logs counseling-api

# 재시작
pm2 restart counseling-api

# 중지
pm2 stop counseling-api
```

---

## 💰 비용 모니터링

### OpenAI 사용량 확인

https://platform.openai.com/usage

### 비용 한도 설정

https://platform.openai.com/account/billing/limits

예시:
- 월 $10 한도 설정 → 약 300회 실습 가능
- 월 $30 한도 설정 → 약 900회 실습 가능

---

## 🔒 보안 체크리스트

- [ ] `.env` 파일이 `.gitignore`에 포함되어 있는지 확인
- [ ] 학교 서버에서 실행 시 방화벽 설정
- [ ] OpenAI 비용 한도 설정
- [ ] 정기적으로 API 키 교체

---

## 🐛 문제 해결

### "EADDRINUSE: address already in use"
→ 다른 프로그램이 포트 3000을 사용 중
```bash
# 포트 변경
PORT=3001 npm start
```

### "insufficient_quota"
→ OpenAI 계정에 결제 정보 등록 필요

### "Cannot find module"
→ 의존성 재설치
```bash
rm -rf node_modules package-lock.json
npm install
```

### API 응답이 느림
→ OpenAI 모델 확인 (GPT-4o-mini가 빠름)

---

## 📞 도움

- GitHub Issues: https://github.com/seahog77/test/issues
- API 문서: `api-proxy/README.md`
- 배포 가이드: `DEPLOYMENT.md`

---

## 🎉 테스트

모든 것이 제대로 작동하는지 테스트:

```bash
# 1. 서버 실행
npm start

# 2. 새 터미널에서 테스트
curl -X POST http://localhost:3000/api/client-response \
  -H "Content-Type: application/json" \
  -d '{
    "action": "client-response",
    "messages": [{"role": "user", "content": "안녕하세요"}],
    "systemPrompt": "당신은 김순자입니다. 짧게 대답하세요."
  }'

# 3. 응답 확인
# {"reply":"(가방을 만지작거리며) ...딸이 가보라 캐서..."}
```

성공! 🎊 이제 학생들과 함께 사용할 수 있습니다.
