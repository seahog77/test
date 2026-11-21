// Cloudflare Workers - AI API 프록시
// 학생 브라우저 -> Cloudflare Worker -> OpenAI API
// 
// 환경 변수 설정 필요:
// - OPENAI_API_KEY: OpenAI API 키

export default {
  async fetch(request, env) {
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
        return await generateClientResponse(messages, systemPrompt, env.OPENAI_API_KEY, corsHeaders);
      } 
      else if (action === 'supervision') {
        return await generateSupervision(messages, systemPrompt, env.OPENAI_API_KEY, corsHeaders);
      }
      else {
        return new Response(JSON.stringify({ 
          error: 'Invalid action',
          code: 'INVALID_ACTION' 
        }), { 
          status: 400,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }
    } catch (error) {
      console.error('Error:', error);
      return new Response(JSON.stringify({ 
        error: '요청 처리 중 오류가 발생했습니다.',
        code: 'INTERNAL_ERROR',
        details: error.message
      }), { 
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
  }
};

async function generateClientResponse(messages, systemPrompt, apiKey, corsHeaders) {
  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
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

async function generateSupervision(messages, systemPrompt, apiKey, corsHeaders) {
  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
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
  
  let feedback;
  try {
    feedback = JSON.parse(data.choices[0].message.content);
  } catch (e) {
    console.error('JSON parse error:', e);
    return new Response(JSON.stringify({ 
      error: 'AI 응답을 처리하는 중 오류가 발생했습니다.',
      code: 'JSON_PARSE_ERROR'
    }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }

  return new Response(JSON.stringify({ feedback }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}

function handleAPIError(error, corsHeaders) {
  console.error('API Error:', error);
  
  let userMessage = '요청 처리 중 오류가 발생했습니다.';
  let errorCode = 'API_ERROR';
  let status = 500;

  if (error.error?.type === 'insufficient_quota') {
    userMessage = 'API 할당량이 초과되었습니다. 관리자에게 문의하세요.';
    errorCode = 'QUOTA_EXCEEDED';
    status = 429;
  } else if (error.error?.code === 'rate_limit_exceeded') {
    userMessage = '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.';
    errorCode = 'RATE_LIMIT';
    status = 429;
  } else if (error.error?.code === 'invalid_api_key') {
    userMessage = 'API 인증에 실패했습니다. 관리자에게 문의하세요.';
    errorCode = 'AUTH_ERROR';
    status = 401;
  }

  return new Response(JSON.stringify({ 
    error: userMessage,
    code: errorCode 
  }), {
    status: status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' }
  });
}
