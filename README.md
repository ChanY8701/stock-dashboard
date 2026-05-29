# 📡 순환매 상황실 전광판

한국 주식 섹터 순환매를 기계적으로 감시하는 실시간 대시보드입니다.

---

## 📁 파일 구조

```
stock_dashboard/
├── app.py                   # Streamlit 전광판 메인
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example             # 환경변수 템플릿
├── data/
│   └── sector_db.py         # 전체 섹터 DB (10개 대분류 병합)
├── utils/
│   ├── kis_api.py           # KIS API 핸들러 (시세, 황금별 판정)
│   └── discord_alert.py     # Discord Webhook 알림
└── scheduler/
    └── scheduler.py         # 장중 감시 + 4시 자동 리포트
```

---

## ⚙️ 초기 설정

### 1. 환경변수 설정
```bash
cp .env.example .env
# .env 파일 열어서 KIS API 키, Discord Webhook URL 입력
```

### 2. KIS API 발급
1. https://apiportal.koreainvestment.com 접속
2. 앱 등록 → APP_KEY / APP_SECRET 발급
3. `.env` 에 입력

### 3. Discord Webhook 설정
1. Discord 서버 → 알림 받을 채널 → ⚙️ 채널 편집
2. 연동 → 웹후크 → 새 웹후크 → URL 복사
3. `.env` 의 `DISCORD_WEBHOOK_URL` 에 붙여넣기

---

## 🚀 실행 방법

### Docker Compose (권장 — AWS/GCP)
```bash
docker-compose up -d --build
# 대시보드: http://서버IP:8501
# 로그 확인: docker-compose logs -f
```

### 로컬 직접 실행
```bash
pip install -r requirements.txt
cp .env.example .env && nano .env   # 키 입력

# 터미널 1: 대시보드
streamlit run app.py

# 터미널 2: 스케줄러
python scheduler/scheduler.py
```

---

## 🔍 전광판 읽는 법

| 표시 | 의미 |
|------|------|
| 🟢 PASS | 섹터 거래대금이 반도체의 40% 이상 → 자금 유입 중 |
| 🔴 FAIL | 40% 미만 → 소외 섹터 |
| ⭐ (황금별) | 등락률 -1.5%~+1.5% + 거래량 5일평균의 20% 이하 → **길목 지키기 적기** |
| 🚫 빨간 글씨 | 급등 or 거래량 폭발 → **추격매수 금지** |
| 🚨 빨간 배너 | 대장주 -4% 이탈 → **아우 종목 즉시 손절 권장** |

---

## 🤖 Discord 알림 종류

1. **🚨 대장주 부러짐** — 장중 대장주 -4% 이탈 시 즉시 발송
2. **⭐ 황금별 타점** — 오전 11시 황금별 종목 일괄 알림
3. **📋 일일 마감 리포트** — 매일 오후 4시 자동 발송

---

## ⚠️ 주의사항
- KIS API 무료 계정은 초당 요청 제한(약 20 req/s) 있음
- 종목 마스터 CSV(`data/stock_codes.csv`)를 미리 준비하면 API 호출 횟수 절감
- 이 도구는 참고용입니다. 투자 손실에 대한 책임은 사용자 본인에게 있습니다.
