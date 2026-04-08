# NoteForEverything
- 내가 쓰려고 만든 메모 프로그램. 딱딱하지 않고 자유로운 느낌의 메모장 느낌
- 로컬 작동. 시각화 탭은 최초 로딩 시 인터넷 연결 필요.
- 맥 OS 기반(MS는 안 됨)

## 기능

- 할 일 - 근시일 내, 언젠가 구분 가능. 체크박스 형식
- 위키 - 주제별 카테고리, 지식의 출처
- 아이디어/기록 - 자유롭게 쓰고 싶은 것, 시기별 구분 가능.
- 시각화 - 모든 테그와 노트를 그물 그래프로 한번에 볼 수 있음.
  - 태그 노드: 2개 이상 노트와 공유되는 경우만 표시
  - 태그 클릭 → 연결 노트 하이라이트
  - 노트 1회 클릭 → 연결 태그 하이라이트
  - 노트 2회 클릭 → 연결 노트 전체 하이라이트
- 이미지 업로드, URL 링크 가능. 

## 사용 방법

### 0. 설치방법

1. 파일 다운로드 후 압축해제
2. 본인이 원하는 위치에 폴더로 저장

### 1. 터미널에서 실행
```bash
cd 실행 폴더 경로
./run.sh
```
### 2. 파이썬에서 직접
```bash
cd second_brain
pip install -r requirements.txt
python3 app.py
```

브라우저에서 자동으로 http://localhost:5001이 열림.
종료방법: `Ctrl+C`

## 정보

- Python 3.9+
- flask, requests, beautifulsoup4
```
Note For Everything/ 
├── app.py — Flask 백엔드 + REST API <
├── templates/ 
│ └── index.html — 프론트엔드 전체 (HTML+CSS+JS) 
├── data/ 
│ ├── brain.db — SQLite DB (런타임 생성) 
│ └── uploads/ — 이미지 저장소 
└── run.sh — 실행 스크립트 
```

## 데이터 저장 위치
- `data/brain.db` (SQLite), `data/uploads/` (이미지)
