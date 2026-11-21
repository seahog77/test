#!/bin/bash

# OpenAI API 키로 자동 배포
# 사용법: OPENAI_API_KEY=sk-xxx ./deploy-with-key.sh

set -e

# 환경 변수에서 API 키 읽기
API_KEY="${OPENAI_API_KEY}"

if [ -z "$API_KEY" ]; then
    echo "❌ OPENAI_API_KEY 환경 변수가 설정되지 않았습니다."
    echo ""
    echo "사용법:"
    echo "  OPENAI_API_KEY=sk-xxx ./deploy-with-key.sh"
    echo ""
    exit 1
fi

echo "🚀 가상내담자 상담실습실 API 자동 배포"
echo "========================================="
echo ""

# Wrangler 설치 확인
if ! command -v wrangler &> /dev/null; then
    echo "⚠️  Wrangler CLI가 설치되어 있지 않습니다."
    echo ""
    echo "설치 중..."
    npm install -g wrangler
    echo ""
fi

# 로그인
echo "🔐 Cloudflare 로그인..."
wrangler login

# Secret 설정
echo ""
echo "🔑 API 키 설정 중..."
echo "$API_KEY" | wrangler secret put OPENAI_API_KEY

# 배포
echo ""
echo "📦 Workers 배포 중..."
wrangler deploy cloudflare-worker.js

# Worker URL 가져오기
echo ""
echo "🔍 Worker URL 확인 중..."
WORKER_URL=$(wrangler deployments list 2>/dev/null | grep -m1 "https://" | awk '{print $1}')

if [ -z "$WORKER_URL" ]; then
    echo "⚠️  Worker URL을 자동으로 가져올 수 없습니다."
    echo "수동으로 확인하세요: wrangler deployments list"
    exit 1
fi

echo ""
echo "✅ 배포 완료!"
echo "========================================="
echo ""
echo "Worker URL: $WORKER_URL"
echo ""

# HTML 파일 자동 업데이트
echo "📝 HTML 파일 업데이트 중..."
cd ..
sed -i.bak "s|const API_BASE_URL = null|const API_BASE_URL = '$WORKER_URL'|" EC-01.html
sed -i.bak "s|const API_BASE_URL = null|const API_BASE_URL = '$WORKER_URL'|" ../docs/index.html

# 백업 파일 삭제
rm -f EC-01.html.bak ../docs/index.html.bak

echo "✅ HTML 파일 업데이트 완료"
echo ""

# Git 커밋
echo "📦 Git 커밋 중..."
cd ..
git add EC-01.html ../docs/index.html
git commit -m "feat: OpenAI API 서버 연결 ($WORKER_URL)"
git push

echo ""
echo "🎉 모든 설정이 완료되었습니다!"
echo "========================================="
echo ""
echo "이제 실습실에서 실제 AI를 사용할 수 있습니다!"
echo ""
echo "⚠️  보안 경고:"
echo "API 키가 노출되었으므로 OpenAI 대시보드에서"
echo "키를 재발급하고 다시 설정하는 것을 권장합니다."
echo ""
echo "링크: https://raw.githack.com/seahog77/test/cursor/virtual-counseling-lab-8d5b/docs/index.html"
echo ""
