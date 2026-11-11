// Node.js + Express 서버
// 로컬 서버 또는 학교 서버에서 운영
//
// 설치: npm install express cors openai dotenv
// 실행: node express-server.js
// 환경 변수: .env 파일에 OPENAI_API_KEY 설정

const express = require('express');
const cors = require('cors');
const OpenAI = require('openai');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// OpenAI 클라이언트 초기화
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

// 미들웨어
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// 정적 파일 제공 (HTML 파일들)
// public 폴더에 EC-*.html 파일들을 넣으세요
app.use(express.static('public'));

// 요청 로깅 미들웨어
app.use((req, res, next) => {
  if (req.path.startsWith('/api/')) {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  }
  next();
});

// 내담자 응답 생성
app.post('/api/client-response', async (req, res) => {
  try {
    const { messages, systemPrompt } = req.body;
    
    if (!messages || !systemPrompt) {
      return res.status(400).json({ 
        error: '필수 파라미터가 누락되었습니다.',
        code: 'MISSING_PARAMS'
      });
    }
    
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
    console.error('Client response error:', error);
    handleError(error, res);
  }
});

// 슈퍼비전 피드백 생성
app.post('/api/supervision', async (req, res) => {
  try {
    const { messages, systemPrompt } = req.body;
    
    if (!messages || !systemPrompt) {
      return res.status(400).json({ 
        error: '필수 파라미터가 누락되었습니다.',
        code: 'MISSING_PARAMS'
      });
    }
    
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
    
    let feedback;
    try {
      feedback = JSON.parse(completion.choices[0].message.content);
    } catch (e) {
      console.error('JSON parse error:', e);
      return res.status(500).json({
        error: 'AI 응답을 처리하는 중 오류가 발생했습니다.',
        code: 'JSON_PARSE_ERROR'
      });
    }
    
    res.json({ feedback });
    
  } catch (error) {
    console.error('Supervision error:', error);
    handleError(error, res);
  }
});

// 헬스 체크
app.get('/api/health', (req, res) => {
  res.json({ 
    status: 'ok',
    timestamp: new Date().toISOString(),
    openaiConfigured: !!process.env.OPENAI_API_KEY
  });
});

// 에러 핸들러
function handleError(error, res) {
  if (error.code === 'insufficient_quota') {
    return res.status(429).json({ 
      error: 'API 할당량이 초과되었습니다. 관리자에게 문의하세요.',
      code: 'QUOTA_EXCEEDED'
    });
  }
  
  if (error.code === 'rate_limit_exceeded') {
    return res.status(429).json({ 
      error: '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.',
      code: 'RATE_LIMIT'
    });
  }
  
  if (error.status === 401) {
    return res.status(401).json({ 
      error: 'API 인증에 실패했습니다. 관리자에게 문의하세요.',
      code: 'AUTH_ERROR'
    });
  }
  
  res.status(500).json({ 
    error: '요청 처리 중 오류가 발생했습니다.',
    code: 'INTERNAL_ERROR',
    details: process.env.NODE_ENV === 'development' ? error.message : undefined
  });
}

// 404 핸들러
app.use((req, res) => {
  res.status(404).json({ 
    error: 'Not found',
    code: 'NOT_FOUND'
  });
});

// 서버 시작
app.listen(PORT, () => {
  console.log(`✅ 가상내담자 상담실습실 서버 실행 중`);
  console.log(`📍 주소: http://localhost:${PORT}`);
  console.log(`🔑 OpenAI API 설정: ${process.env.OPENAI_API_KEY ? '✅' : '❌'}`);
  console.log(`\n학생들에게 제공할 주소:`);
  console.log(`   - EC-01: http://localhost:${PORT}/EC-01.html`);
  console.log(`   - EC-02: http://localhost:${PORT}/EC-02.html (예정)`);
  console.log(`\n헬스 체크: http://localhost:${PORT}/api/health`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM 신호 수신. 서버를 종료합니다...');
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('\nSIGINT 신호 수신. 서버를 종료합니다...');
  process.exit(0);
});
