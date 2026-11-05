# 🚀 빠른 배포 가이드

OpenAI API 키로 즉시 배포하는 방법입니다.

## ⚡ 1단계: Wrangler CLI 설치 (최초 1회만)

```bash
npm install -g wrangler
```

권한 오류가 나면:
```bash
sudo npm install -g wrangler
```

## ⚡ 2단계: .env 파일 확인

`.env` 파일이 이미 준비되어 있습니다! (API 키 포함)

```bash
cd virtual-counseling-lab/api-proxy
cat .env  # 확인
```

## ⚡ 3단계: 자동 배포 실행

```bash
./setup-env.sh
```

또는 직접:
```bash
source .env
./deploy-with-key.sh
```

이 스크립트가 자동으로:
1. ✅ Cloudflare 로그인
2. ✅ OpenAI API 키 설정
3. ✅ Workers 배포
4. ✅ HTML 파일 업데이트
5. ✅ Git 커밋 및 푸시

**완료!** 🎉

## 📱 접속 링크

배포 후 이 링크에서 실제 AI를 사용할 수 있습니다:

https://raw.githack.com/seahog77/test/cursor/virtual-counseling-lab-8d5b/docs/index.html

(또는 GitHub Pages 활성화 후: https://seahog77.github.io/test/)

## ⚠️ 중요: 보안

API 키가 채팅에 노출되었으므로 **반드시 재발급**하세요:

1. https://platform.openai.com/api-keys 접속
2. 기존 키 삭제
3. 새 키 발급
4. 새 키로 재설정:
   ```bash
   wrangler secret put OPENAI_API_KEY
   # 새 키 입력
   ```

## 🔧 대안: Express 서버 (로컬)

Cloudflare 대신 로컬에서 실행:

```bash
cd virtual-counseling-lab/api-proxy
npm install
npm start
```

서버가 `http://localhost:3000`에서 실행됩니다.

HTML 파일에서:
```javascript
const API_BASE_URL = 'http://localhost:3000';
```

## 💡 팁

### 비용 한도 설정
OpenAI 대시보드에서 월 사용 한도 설정:
https://platform.openai.com/account/billing/limits

### 사용량 모니터링
https://platform.openai.com/usage

### Workers 로그 확인
```bash
wrangler tail
```

## 🐛 문제 해결

### "insufficient_quota"
→ OpenAI 계정에 결제 정보 등록 필요

### "401 Unauthorized"
→ API 키 재설정: `wrangler secret put OPENAI_API_KEY`

### Workers 배포 실패
→ Cloudflare 로그인 확인: `wrangler whoami`

## 📞 도움

- GitHub Issues: https://github.com/seahog77/test/issues
- 상세 가이드: `SETUP_API.md`
