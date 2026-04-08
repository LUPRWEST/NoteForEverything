#!/bin/bash
cd "$(dirname "$0")"
echo "🧠 Note For Everything 시작 중..."
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "❌ Python3 가 설치되어 있지 않습니다."
  exit 1
fi

# Install dependencies
python3 -m pip install -r requirements.txt -q
echo "✅ 의존성 설치 완료"
echo ""
python3 app.py
