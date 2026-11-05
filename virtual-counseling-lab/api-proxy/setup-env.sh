#!/bin/bash

# .env 파일에서 환경 변수 로드하고 배포
# 사용법: ./setup-env.sh

set -e

# .env 파일 확인
if [ ! -f .env ]; then
    echo "❌ .env 파일이 없습니다."
    echo ""
    echo ".env 파일을 생성하세요:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    echo ""
    exit 1
fi

# .env 로드
export $(cat .env | grep -v '^#' | xargs)

echo "🚀 가상내담자 상담실습실 API 배포"
echo "================================="
echo ""
echo "✅ .env 파일 로드 완료"
echo ""

# deploy-with-key.sh 실행
./deploy-with-key.sh
