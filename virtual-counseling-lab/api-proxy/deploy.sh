#!/bin/bash

# Cloudflare Workers 자동 배포 스크립트
# 사용법: ./deploy.sh

set -e

echo "🚀 가상내담자 상담실습실 API 배포"
echo "================================="
echo ""

# Wrangler 설치 확인
if ! command -v wrangler &> /dev/null; then
    echo "❌ Wrangler CLI가 설치되어 있지 않습니다."
    echo ""
    echo "설치 방법:"
    echo "  npm install -g wrangler"
    echo ""
    exit 1
fi

echo "✅ Wrangler CLI 확인 완료"
echo ""

# 로그인 확인
echo "🔐 Cloudflare 로그인 확인..."
if ! wrangler whoami &> /dev/null; then
    echo "⚠️  Cloudflare에 로그인이 필요합니다."
    echo ""
    wrangler login
    echo ""
fi

echo "✅ 로그인 완료"
echo ""

# OpenAI API 키 확인
echo "🔑 OpenAI API 키 설정"
echo ""
echo "OpenAI API 키를 입력해주세요:"
echo "(https://platform.openai.com/api-keys 에서 발급)"
echo ""
read -sp "API Key: " OPENAI_API_KEY
echo ""
echo ""

if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ API 키가 입력되지 않았습니다."
    exit 1
fi

# Secret 설정
echo "🔐 API 키를 Workers Secret으로 저장 중..."
echo "$OPENAI_API_KEY" | wrangler secret put OPENAI_API_KEY
echo ""

# 배포
echo "📦 Workers 배포 중..."
wrangler deploy cloudflare-worker.js
echo ""

# Worker URL 가져오기
WORKER_URL=$(wrangler deployments list | grep -m1 "https://" | awk '{print $1}')

echo ""
echo "✅ 배포 완료!"
echo "================================="
echo ""
echo "Worker URL: $WORKER_URL"
echo ""
echo "다음 단계:"
echo "1. 위의 Worker URL을 복사하세요"
echo "2. EC-01.html 파일을 열고"
echo "3. 'API_BASE_URL = null'을 찾아서"
echo "4. 'API_BASE_URL = \"$WORKER_URL\"'로 변경하세요"
echo ""
echo "또는 자동 설정:"
echo "  sed -i 's|API_BASE_URL = null|API_BASE_URL = \"$WORKER_URL\"|' ../EC-01.html"
echo ""
