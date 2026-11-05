# 배포 가이드

가상내담자 상담실습실을 실제 AI와 연결하여 배포하는 방법을 안내합니다.

## 🎯 배포 옵션 비교

| 방식 | 학생 요구사항 | 비용 | 설계서 보안 | 권장도 |
|------|--------------|------|-------------|--------|
| **학교/교수 서버** | 링크만 | 교수 API 계정 | ✅ 안전 | ⭐⭐⭐⭐⭐ |
| 학생 본인 API 키 | API 키 발급 | 학생 부담 | ✅ 안전 | ⭐⭐ (비현실적) |
| 프롬프트 복사 | AI 채팅 계정 | 없음 | ❌ 노출 | ⭐ (권장하지 않음) |

**권장**: 학교 또는 교수가 서버를 운영하고 학생에게 링크만 제공하는 방식

## 🚀 방법 1: Cloudflare Workers (권장)

### 장점
- 무료 티어로 시작 가능 (월 10만 요청)
- 설정이 간단함
- 글로벌 CDN으로 빠른 응답
- API 키 안전하게 보호

### 비용 (2024년 11월 기준)
- Free 플랜: 월 10만 요청 (소규모 수업 충분)
- Paid 플랜: $5/월 + 초과 요청당 $0.50/백만

### 1단계: Cloudflare 계정 생성

1. [Cloudflare](https://cloudflare.com) 가입
2. Workers 대시보드로 이동

### 2단계: Worker 생성 및 배포

#### 파일: `api-proxy/cloudflare-worker.js`

```javascript
// Cloudflare Workers - AI API 프록시
// 학생 브라우저 -> Cloudflare Worker -> OpenAI API

const OPENAI_API_KEY = '여기에-OpenAI-API-키-입력';

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  // CORS 헤더
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };

  // Preflight 요청 처리
  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  // POST 요청만 허용
  if (request.method !== 'POST') {
    return new Response('Method not allowed', { 
      status: 405,
      headers: corsHeaders 
    });
  }

  try {
    const { action, messages, systemPrompt } = await request.json();
    
    if (action === 'client-response') {
      // 내담자 응답 생성 (빠른 모델)
      return await generateClientResponse(messages, systemPrompt, corsHeaders);
    } 
    else if (action === 'supervision') {
      // 슈퍼비전 피드백 (더 능력 있는 모델)
      return await generateSupervision(messages, systemPrompt, corsHeaders);
    }
    else {
      return new Response('Invalid action', { 
        status: 400,
        headers: corsHeaders 
      });
    }
  } catch (error) {
    console.error('Error:', error);
    return new Response(JSON.stringify({ 
      error: '요청 처리 중 오류가 발생했습니다.',
      code: 'INTERNAL_ERROR'
    }), { 
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
}

async function generateClientResponse(messages, systemPrompt, corsHeaders) {
  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${OPENAI_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: 'gpt-4o-mini', // 빠르고 저렴한 모델
      messages: [
        { role: 'system', content: systemPrompt },
        ...messages
      ],
      temperature: 0.8,
      max_tokens: 150,
    })
  });

  if (!response.ok) {
    const error = await response.json();
    return handleAPIError(error, corsHeaders);
  }

  const data = await response.json();
  const reply = data.choices[0].message.content;

  return new Response(JSON.stringify({ reply }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

async function generateSupervision(messages, systemPrompt, corsHeaders) {
  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${OPENAI_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: 'gpt-4o', // 더 능력 있는 모델
      messages: [
        { role: 'system', content: systemPrompt },
        ...messages
      ],
      temperature: 0.3,
      max_tokens: 2000,
      response_format: { type: 'json_object' }
    })
  });

  if (!response.ok) {
    const error = await response.json();
    return handleAPIError(error, corsHeaders);
  }

  const data = await response.json();
  const feedback = JSON.parse(data.choices[0].message.content);

  return new Response(JSON.stringify({ feedback }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

function handleAPIError(error, corsHeaders) {
  let userMessage = '요청 처리 중 오류가 발생했습니다.';
  let errorCode = 'API_ERROR';

  if (error.error?.type === 'insufficient_quota') {
    userMessage = 'API 할당량이 초과되었습니다. 관리자에게 문의하세요.';
    errorCode = 'QUOTA_EXCEEDED';
  } else if (error.error?.code === 'rate_limit_exceeded') {
    userMessage = '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.';
    errorCode = 'RATE_LIMIT';
  }

  return new Response(JSON.stringify({ 
    error: userMessage,
    code: errorCode 
  }), {
    status: 500,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}
```

### 3단계: 환경 변수 설정

Workers 대시보드에서:
1. Settings → Variables 이동
2. Environment Variables 추가:
   - `OPENAI_API_KEY`: OpenAI API 키 (암호화됨)

코드 수정:
```javascript
const OPENAI_API_KEY = env.OPENAI_API_KEY; // 환경 변수에서 가져오기
```

### 4단계: HTML 파일 수정

EC-01.html의 `getClientResponse()` 함수를 수정:

```javascript
async function getClientResponse() {
    const conversation = state.messages.map(m => ({
        role: m.role === 'counselor' ? 'user' : 'assistant',
        content: m.text
    }));
    
    try {
        const response = await fetch('https://your-worker.your-subdomain.workers.dev', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'client-response',
                messages: conversation,
                systemPrompt: CLIENT_SYSTEM_PROMPT
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '응답 생성 실패');
        }
        
        const data = await response.json();
        return data.reply;
    } catch (error) {
        console.error('Error:', error);
        return '(연결 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.)';
    }
}
```

`getSupervisionFeedback()` 함수도 동일하게 수정:

```javascript
async function getSupervisionFeedback(transcript, conceptualization) {
    const messages = [{
        role: 'user',
        content: `축어록:\n${transcript}\n\n학생 사례개념화:\n① ${conceptualization.coreIssue}\n② ${conceptualization.coreBeliefs}\n③ ${conceptualization.riskAssessment}\n\n내담자 설계서:\n${JSON.stringify(CASE, null, 2)}`
    }];
    
    try {
        const response = await fetch('https://your-worker.your-subdomain.workers.dev', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'supervision',
                messages: messages,
                systemPrompt: SUPERVISION_SYSTEM_PROMPT
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '피드백 생성 실패');
        }
        
        const data = await response.json();
        return data.feedback;
    } catch (error) {
        console.error('Error:', error);
        alert('슈퍼비전 생성 중 오류가 발생했습니다. 다시 시도해 주세요.');
        throw error;
    }
}
```

### 5단계: 배포

```bash
# Wrangler CLI 설치
npm install -g wrangler

# 로그인
wrangler login

# Worker 배포
wrangler deploy api-proxy/cloudflare-worker.js

# URL 확인: https://your-worker.your-subdomain.workers.dev
```

### 6단계: 학생에게 제공

1. HTML 파일을 GitHub Pages, Netlify, 또는 학교 서버에 업로드
2. 학생에게 URL 공유
3. 학생은 링크만으로 실습 가능

---

## 🔧 방법 2: Node.js + Express

로컬 서버 또는 학교 서버에서 운영하는 방법입니다.

### 파일: `api-proxy/express-server.js`

```javascript
const express = require('express');
const cors = require('cors');
const OpenAI = require('openai');

const app = express();
const PORT = process.env.PORT || 3000;

// OpenAI 클라이언트 초기화
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

app.use(cors());
app.use(express.json());

// 정적 파일 제공 (HTML 파일들)
app.use(express.static('public'));

// 내담자 응답 생성
app.post('/api/client-response', async (req, res) => {
  try {
    const { messages, systemPrompt } = req.body;
    
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        { role: 'system', content: systemPrompt },
        ...messages
      ],
      temperature: 0.8,
      max_tokens: 150,
    });
    
    const reply = completion.choices[0].message.content;
    res.json({ reply });
  } catch (error) {
    console.error('Error:', error);
    
    if (error.code === 'insufficient_quota') {
      return res.status(500).json({ 
        error: 'API 할당량이 초과되었습니다.',
        code: 'QUOTA_EXCEEDED'
      });
    }
    
    res.status(500).json({ 
      error: '요청 처리 중 오류가 발생했습니다.',
      code: 'INTERNAL_ERROR'
    });
  }
});

// 슈퍼비전 피드백 생성
app.post('/api/supervision', async (req, res) => {
  try {
    const { messages, systemPrompt } = req.body;
    
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o',
      messages: [
        { role: 'system', content: systemPrompt },
        ...messages
      ],
      temperature: 0.3,
      max_tokens: 2000,
      response_format: { type: 'json_object' }
    });
    
    const feedback = JSON.parse(completion.choices[0].message.content);
    res.json({ feedback });
  } catch (error) {
    console.error('Error:', error);
    res.status(500).json({ 
      error: '피드백 생성 중 오류가 발생했습니다.',
      code: 'INTERNAL_ERROR'
    });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
```

### 설치 및 실행

```bash
# 의존성 설치
npm init -y
npm install express cors openai dotenv

# .env 파일 생성
echo "OPENAI_API_KEY=your-api-key-here" > .env

# HTML 파일을 public 폴더에 복사
mkdir public
cp EC-*.html public/

# 서버 실행
node api-proxy/express-server.js
```

### HTML 파일 수정

```javascript
// API 엔드포인트를 localhost 또는 서버 주소로 변경
const API_BASE_URL = 'http://localhost:3000/api';

async function getClientResponse() {
    // ... (이전과 동일, URL만 변경)
    const response = await fetch(`${API_BASE_URL}/client-response`, {
        // ...
    });
}
```

---

## 💰 비용 예상 (OpenAI API)

### 모델별 가격 (2024년 11월 기준)

| 모델 | 입력 (1M 토큰) | 출력 (1M 토큰) | 용도 |
|------|----------------|----------------|------|
| GPT-4o-mini | $0.150 | $0.600 | 내담자 응답 |
| GPT-4o | $2.50 | $10.00 | 슈퍼비전 |

### 실습 1회 예상 비용

- 내담자 응답 15회: ~300토큰 × 15 = 4,500토큰 → **약 $0.003**
- 슈퍼비전 1회: ~3,000토큰 → **약 $0.03**
- **실습 1회 총 비용: 약 $0.033 (약 45원)**

### 수업 규모별 예상

| 학생 수 | 실습 횟수 | 월 비용 (USD) | 월 비용 (KRW) |
|---------|----------|--------------|--------------|
| 30명 | 각 3회 | ~$3 | ~₩4,000 |
| 50명 | 각 3회 | ~$5 | ~₩6,700 |
| 100명 | 각 5회 | ~$17 | ~₩23,000 |

**저렴합니다!** 전통적인 실습 대체재로 매우 경제적입니다.

---

## 🔒 보안 체크리스트

### ✅ 필수
- [ ] API 키를 HTML 파일에 직접 넣지 않기
- [ ] 환경 변수 또는 Workers Secrets 사용
- [ ] CORS 설정으로 허용된 도메인만 접근 가능하게
- [ ] 요청 속도 제한 (Rate Limiting) 설정

### ✅ 권장
- [ ] 로깅 설정 (오류 추적용)
- [ ] 사용량 모니터링 알림 설정
- [ ] 비용 한도 설정 (OpenAI 대시보드)

---

## 🐛 트러블슈팅

### "API 할당량 초과" 오류
→ OpenAI 계정에 결제 정보 등록 또는 한도 증액

### "CORS 오류"
→ Cloudflare Worker 또는 Express에서 CORS 헤더 확인

### "응답이 너무 느림"
→ 내담자 응답은 `gpt-4o-mini` 사용, 슈퍼비전만 `gpt-4o` 사용

### "JSON 파싱 오류" (슈퍼비전)
→ `response_format: { type: 'json_object' }` 옵션 확인
→ 시스템 프롬프트에 JSON 형식 명시

---

## 📞 지원

추가 질문이나 문제가 있으시면 이슈를 등록해 주세요.
