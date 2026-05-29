# 📡 순환매 상황실 — GitHub Actions 세팅 가이드
# 처음부터 끝까지 따라하면 됩니다 (서버 비용 $0)

---

## ✅ 전체 흐름 요약

```
내 PC에서 코드 업로드 → GitHub가 매일 오후 4시에 자동 실행
→ KIS API로 시세 수집 → Discord로 리포트 전송
```

서버 없음. 비용 없음. GitHub이 대신 실행해줌.

---

## STEP 1 — GitHub 계정 만들기

1. https://github.com 접속
2. Sign up 클릭
3. 이메일 / 비밀번호 입력 후 가입
4. 무료 플랜(Free) 선택 → OK

---

## STEP 2 — 새 저장소(Repository) 만들기

1. 로그인 후 우측 상단 **[+]** 클릭 → **New repository**
2. 아래처럼 입력:
   ```
   Repository name: stock-dashboard     ← 이름 (영어로)
   Description: 순환매 상황실           ← 설명 (선택)
   ● Private  ← 반드시 Private 선택! (API 키 보호)
   ```
3. **Create repository** 클릭

---

## STEP 3 — 내 PC에 Git 설치 (처음 한 번만)

**Windows:**
1. https://git-scm.com/download/win 접속
2. 다운로드 후 설치 (기본 옵션으로 Next Next Next)
3. 설치 후 바탕화면 우클릭 → **Git Bash** 열기

**Mac:**
```bash
# 터미널 열고 입력
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install git
```

---

## STEP 4 — 코드 폴더 업로드

다운받은 `stock_dashboard` 폴더를 열고,
Git Bash (또는 터미널) 에서 아래 명령어 순서대로 입력:

```bash
# 1. 폴더로 이동 (경로는 본인 것으로 수정)
cd C:/Users/본인이름/Downloads/stock_dashboard

# 2. git 초기화
git init

# 3. GitHub 저장소 연결 (본인 GitHub 아이디로 변경)
git remote add origin https://github.com/본인아이디/stock-dashboard.git

# 4. 전체 파일 추가
git add .

# 5. 첫 커밋
git commit -m "초기 세팅"

# 6. GitHub에 업로드
git push -u origin main
```

> 업로드 중 GitHub 로그인 팝업이 뜨면 로그인하면 됩니다.

---

## STEP 5 — KIS API 키 발급

1. https://apiportal.koreainvestment.com 접속
2. 로그인 → **앱 등록** 클릭
3. 앱 이름 입력 후 등록 완료
4. 발급된 **APP_KEY** 와 **APP_SECRET** 복사해두기

---

## STEP 6 — Discord Webhook URL 만들기

1. Discord 열기
2. 알림 받을 채널(예: #주식알림) 우클릭
3. **채널 편집** 클릭
4. 왼쪽 메뉴에서 **연동** 클릭
5. **웹후크** → **새 웹후크** 클릭
6. 이름 입력(예: 순환매봇) → **URL 복사** 클릭
7. 복사한 URL 메모해두기
   ```
   예시: https://discord.com/api/webhooks/1234567890/abcdefghijk...
   ```

---

## STEP 7 — GitHub Secrets 등록 (API 키 안전하게 저장)

GitHub에 API 키를 직접 올리면 안 됩니다.
Secrets에 등록하면 암호화되어 안전하게 보관됩니다.

1. GitHub에서 내 저장소(stock-dashboard) 접속
2. 상단 탭에서 **Settings** 클릭
3. 왼쪽 메뉴 → **Secrets and variables** → **Actions** 클릭
4. **New repository secret** 버튼 클릭
5. 아래 3개를 각각 등록:

| Name | Secret (값) |
|------|-------------|
| `KIS_APP_KEY` | KIS에서 발급받은 APP KEY |
| `KIS_APP_SECRET` | KIS에서 발급받은 APP SECRET |
| `DISCORD_WEBHOOK_URL` | Discord에서 복사한 Webhook URL |

각각 Name 입력 → Secret 입력 → **Add secret** 클릭

---

## STEP 8 — GitHub Actions 활성화 확인

1. 저장소 상단 **Actions** 탭 클릭
2. "순환매 일일 리포트" 워크플로우가 보이면 OK
3. **Enable workflow** 버튼이 있으면 클릭

---

## STEP 9 — 테스트 실행 (지금 바로 해보기)

스케줄은 평일 오후 4시지만, 지금 당장 테스트할 수 있습니다.

1. Actions 탭 → **순환매 일일 리포트** 클릭
2. 우측 **Run workflow** 버튼 클릭
3. **Run workflow** 확인
4. 약 5~10분 후 Discord에 리포트 도착 확인

---

## STEP 10 — 이후 코드 수정할 때

종목을 추가하거나 수정하고 싶을 때:

```bash
# 파일 수정 후 Git Bash에서:
git add .
git commit -m "종목 추가"
git push
```

끝. GitHub이 자동으로 반영합니다.

---

## 💡 자주 묻는 것들

**Q. 무료 한도는?**
GitHub Actions 무료 플랜: 월 2,000분
이 스크립트는 1회 실행에 약 5~10분 → 월 22회(평일) × 10분 = 220분
→ **무료 한도의 11%만 사용. 완전 무료.**

**Q. Private 저장소도 무료?**
네, 무료 플랜에서 Private 저장소 + Actions 모두 사용 가능합니다.

**Q. KIS API 무료 한도는?**
실전 계좌 기준 초당 20건, 일 500,000건 (충분히 여유 있음)
이 스크립트는 1회 실행에 약 2,000~3,000건 사용

**Q. 장 열리는 날만 실행되나요?**
네. cron: "0 7 * * 1-5" = 평일만 실행
추가로 워크플로우 내부에서 한국 공휴일 체크 후 스킵합니다.

**Q. 실행 중 오류가 나면?**
Discord로 자동 에러 알림이 옵니다.
Actions 탭에서 로그 클릭하면 상세 원인 확인 가능합니다.

---

## 📁 최종 폴더 구조

```
stock-dashboard/           ← GitHub 저장소
├── .github/
│   └── workflows/
│       └── daily_report.yml   ← 자동 실행 스케줄러
├── batch/
│   └── daily_report.py        ← 리포트 메인 스크립트
├── data/
│   └── sector_db_v2.py        ← 22개 섹터 / 1,735개 종목 DB
├── utils/
│   ├── kis_api.py
│   └── discord_alert.py
└── README.md
```
