# ============================================================
# daily_report.py  —  네이버 금융 크롤링 버전
# 로그인 불필요 / 매일 오후 4시 GitHub Actions 자동 실행
# ============================================================
import os, sys, time, requests, re
from datetime import datetime, date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.sector_db_v2 import SECTOR_DATABASE

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]

# ── 네이버 금융 시세 수집 ─────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com",
})

# 종목명 → 코드 매핑
KNOWN_CODES = {
    "SK하이닉스":"000660","삼성전자":"005930",
    "HD현대일렉트릭":"267260","LS일렉트릭":"010120",
    "현대차":"005380","기아":"000270",
    "두산로보틱스":"454910","레인보우로보틱스":"277810",
    "알테오젠":"196170","삼성바이오로직스":"207940","셀트리온":"068270",
    "한화에어로스페이스":"012450","LIG넥스원":"079550",
    "두산에너빌리티":"034020","한국전력":"015760",
    "LG에너지솔루션":"373220","에코프로비엠":"247540","포스코홀딩스":"005490",
    "크래프톤":"259960","넷마블":"251270","넥슨게임즈":"225570",
    "카카오페이":"377300","카카오뱅크":"323410",
    "하이브":"352820","인바디":"041830",
    "LG화학":"051910","효성첨단소재":"298050",
    "HD한국조선해양":"009540","한화오션":"042660","HMM":"011200",
    "삼성물산":"028260","현대건설":"000720",
    "CJ제일제당":"097950","농심":"004370","오리온":"271560",
    "아모레퍼시픽":"090430","LG생활건강":"051900","클리오":"237880",
    "하나투어":"039130","모두투어":"080160","삼성SDS":"018260",
    "HPSP":"403870","테크윙":"089030","한미반도체":"042700",
    "에코프로":"086520","엘앤에프":"066970","포스코퓨처엠":"003670",
    "리가켐바이오":"141080","유한양행":"000100","한미약품":"128940",
    "풍산":"103140","현대로템":"064350","한국항공우주":"047810",
    "HL만도":"204320","현대모비스":"012330","현대위아":"011210",
    "효성중공업":"298040","일진전기":"103590","대한전선":"001440",
    "솔브레인":"357780","한솔케미칼":"014680","주성엔지니어링":"036930",
    "원익IPS":"240810","케이씨텍":"281820","에스피지":"058610",
    "클래시스":"214150","파마리서치":"214450","휴젤":"145020",
    "씨젠":"096530","뷰노":"338220","루닛":"328130",
    "이노와이어리스":"073490","케이엠더블유":"032500","RFHIC":"218410",
    "다산네트웍스":"039560","안랩":"053800","AP위성":"211270",
    "두산퓨어셀":"336260","한화솔루션":"009830","CS윈드":"112610",
    "성일하이텍":"365340","삼성SDI":"006400",
    "LG디스플레이":"034220","LG이노텍":"011070","삼성전기":"009150",
    "카카오":"035720","네이버":"035420","카카오게임즈":"293490",
    "펄어비스":"263750","엔씨소프트":"036570","위메이드":"112040",
    "더존비즈온":"012510","한글과컴퓨터":"030520",
    "에코프로비엠":"247540","코스모신소재":"005070",
    "에스티팜":"237690","셀트리온헬스케어":"091990",
    "고영":"098460","레고켐바이오":"141080","오스템임플란트":"048260",
    "HL만도":"204320","한온시스템":"018880","에스엘":"011810",
    "뉴로메카":"462870","에스피지":"058610","이랜시스":"126340",
    "두산퓨어셀":"336260","범한퓨어셀":"382900",
    "HD현대중공업":"329180","삼성중공업":"010140",
    "HMM":"011200","팬오션":"028670",
    "GS건설":"006360","DL이앤씨":"375500",
}

_price_cache: dict[str, dict] = {}

def get_code(name: str) -> str | None:
    return KNOWN_CODES.get(name)

def get_price_naver(code: str) -> dict | None:
    """네이버 금융 API로 시세 조회"""
    if code in _price_cache:
        return _price_cache[code]
    try:
        url = f"https://finance.naver.com/item/sise.naver?code={code}"
        r = SESSION.get(url, timeout=8)
        html = r.text

        # 현재가
        close_match = re.search(r'<strong[^>]*id="_nowVal"[^>]*>([\d,]+)<', html)
        # 등락률
        rate_match  = re.search(r'<strong[^>]*id="_rate"[^>]*><span[^>]*>([-\d.]+)</span>', html)
        # 거래량 (네이버 금융 API 사용)
        api_url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
        api_r = SESSION.get(api_url, timeout=5)
        api_data = api_r.json()
        stock_info = api_data.get("datas", [{}])[0] if api_data.get("datas") else {}

        close  = int(str(stock_info.get("closePrice", "0")).replace(",","")) if stock_info else 0
        chg    = float(stock_info.get("fluctuationsRatio", 0)) if stock_info else 0
        volume = int(str(stock_info.get("accumulatedTradingVolume","0")).replace(",","")) if stock_info else 0
        tv     = int(str(stock_info.get("accumulatedTradingValue","0")).replace(",","")) if stock_info else 0

        if close == 0 and close_match:
            close = int(close_match.group(1).replace(",",""))
        if chg == 0 and rate_match:
            chg = float(rate_match.group(1))

        result = {
            "close": close,
            "change_rate": round(chg, 2),
            "volume": volume,
            "trading_value": tv,
        }
        _price_cache[code] = result
        return result
    except Exception as e:
        return None

def get_avg_vol_5d_naver(code: str) -> float:
    """네이버 금융 일봉에서 5일 평균 거래량"""
    try:
        url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=10&requestType=0"
        r = SESSION.get(url, timeout=8)
        # XML 파싱
        volumes = re.findall(r'<item data="[^|]+\|[^|]+\|[^|]+\|[^|]+\|([^|]+)\|', r.text)
        vols = [int(v) for v in volumes if v.isdigit()]
        if len(vols) < 2:
            return 0
        return sum(vols[-6:-1]) / min(5, len(vols)-1)
    except Exception:
        return 0

def is_golden(chg: float, vol: int, avg5: float) -> bool:
    return (-1.5 <= chg <= 1.5) and (avg5 > 0) and (vol <= avg5 * 0.20)

# ── Discord 전송 ──────────────────────────────────────────────
def discord_send(payload: dict):
    r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
    if r.status_code not in (200, 204):
        print(f"Discord 실패: {r.status_code}")
    time.sleep(0.8)

def send_embed(title: str, desc: str, color: int, fields: list = None):
    embed = {
        "title": title, "description": desc, "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": f"순환매 상황실 | 네이버금융 | {date.today().strftime('%Y-%m-%d')}"},
    }
    if fields:
        embed["fields"] = fields
    discord_send({"embeds": [embed]})

def chunk_lines(lines: list[str], max_chars=1800) -> list[str]:
    chunks, cur = [], ""
    for line in lines:
        if len(cur) + len(line) + 1 > max_chars:
            chunks.append(cur)
            cur = line
        else:
            cur += "\n" + line if cur else line
    if cur:
        chunks.append(cur)
    return chunks or ["(없음)"]

# ── 메인 ─────────────────────────────────────────────────────
def run():
    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    print(f"\n{'='*50}")
    print(f" 순환매 상황실  {today_str}")
    print(f"{'='*50}\n")

    # ── 1. 대장주 시세 수집 ─────────────────────────────────
    print(f"[{datetime.now():%H:%M:%S}] 대장주 시세 수집...")
    leader_tv: dict[str, int] = {}

    for key, sec in SECTOR_DATABASE.items():
        total = 0
        for name in sec.get("대장주", []):
            code = get_code(name)
            if not code:
                continue
            d = get_price_naver(code)
            if d:
                total += d.get("trading_value", 0)
            time.sleep(0.1)
        leader_tv[key] = total

    base = leader_tv.get("01_반도체_AI", 1) or 1
    tv_ratios = {k: v / base * 100 for k, v in leader_tv.items()}

    # ── 2. PASS/FAIL 판정 ────────────────────────────────────
    pass_sectors, fail_sectors, sector_lines = [], [], []

    for key, sec in SECTOR_DATABASE.items():
        label   = sec["label"]
        ratio   = tv_ratios.get(key, 0)
        pass_ok = ratio >= 40
        (pass_sectors if pass_ok else fail_sectors).append(label)

        leader_chgs = []
        for name in sec.get("대장주", []):
            code = get_code(name)
            d = get_price_naver(code) if code else None
            chg = d["change_rate"] if d else 0
            arrow = "🔺" if chg > 0 else ("🔻" if chg < 0 else "➡️")
            leader_chgs.append(f"{name} {arrow}{chg:+.1f}%")

        icon = "🟢" if pass_ok else "🔴"
        sector_lines.append(
            f"{icon} **{label}** `{ratio:.0f}%`  |  " + "  ".join(leader_chgs)
        )

    # ── 3. 섹터 현황 전송 ────────────────────────────────────
    mid = len(sector_lines) // 2
    send_embed(
        title  = f"📡 순환매 상황실 — {today_str} 마감 리포트",
        desc   = f"🟢 PASS: **{len(pass_sectors)}개** | 🔴 FAIL: **{len(fail_sectors)}개**",
        color  = 0x00BFFF,
        fields = [
            {"name":"📊 섹터 현황 (1/2)", "value":"\n".join(sector_lines[:mid]),  "inline":False},
            {"name":"📊 섹터 현황 (2/2)", "value":"\n".join(sector_lines[mid:]), "inline":False},
        ],
    )
    time.sleep(1)
    send_embed(
        title = "✅ PASS 섹터 — 자금 유입 중",
        desc  = "\n".join([f"🟢 {s}" for s in pass_sectors]) or "없음",
        color = 0x00AA00,
    )
    time.sleep(1)
    send_embed(
        title = "❌ FAIL 섹터 — 소외",
        desc  = "\n".join([f"🔴 {s}" for s in fail_sectors]) or "없음",
        color = 0xAA0000,
    )
    time.sleep(1)

    # ── 4. 황금별 스캔 ──────────────────────────────────────
    print(f"[{datetime.now():%H:%M:%S}] 황금별 스캔 시작...")
    targets = [
        (sec["label"], mid_name, sub_name, name)
        for key, sec in SECTOR_DATABASE.items()
        for mid_name, subs in sec.get("중분류", {}).items()
        for sub_name, stocks in subs.items()
        for name in stocks
    ]

    stars = []
    def _check(label, mid_name, sub_name, name):
        code = get_code(name)
        if not code:
            return None
        d = get_price_naver(code)
        if not d:
            return None
        chg = d["change_rate"]
        vol = d["volume"]
        avg5 = get_avg_vol_5d_naver(code)
        if is_golden(chg, vol, avg5):
            return {
                "sector": label, "sub": sub_name,
                "name": name, "change_rate": chg,
                "vol_ratio": (vol/avg5*100) if avg5 > 0 else 0,
            }
        return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_check, *t) for t in targets]
        for i, f in enumerate(as_completed(futs)):
            if (i+1) % 200 == 0:
                print(f"  진행: {i+1}/{len(targets)}")
            r = f.result()
            if r:
                stars.append(r)

    print(f"[{datetime.now():%H:%M:%S}] 황금별 {len(stars)}개 감지")

    # ── 5. 황금별 전송 ───────────────────────────────────────
    if not stars:
        send_embed(
            title = "⭐ 황금별 타점 — 오늘은 없음",
            desc  = "조건 충족 종목 없음\n(등락률 ±1.5% & 거래량 5일평균 20% 이하)",
            color = 0x555555,
        )
    else:
        by_sector: dict[str, list] = {}
        for s in sorted(stars, key=lambda x: x["sector"]):
            by_sector.setdefault(s["sector"], []).append(s)

        star_lines = []
        for sec_label, items in by_sector.items():
            star_lines.append(f"\n**[{sec_label}]**")
            for s in items:
                star_lines.append(
                    f"  ⭐ `{s['name']}` ({s['sub']})  "
                    f"등락 `{s['change_rate']:+.2f}%`  "
                    f"거래량비율 `{s['vol_ratio']:.0f}%`"
                )

        chunks = chunk_lines(star_lines)
        for i, chunk in enumerate(chunks):
            send_embed(
                title = (f"⭐ 황금별 타점 {len(stars)}종목 ({i+1}/{len(chunks)})"
                         if len(chunks) > 1 else f"⭐ 황금별 타점 총 {len(stars)}종목"),
                desc  = chunk,
                color = 0xFFD700,
            )
            time.sleep(1)

    # ── 6. 마감 ─────────────────────────────────────────────
    send_embed(
        title = "📋 리포트 완료",
        desc  = (
            f"스캔: **{len(targets)}종목**  황금별: **{len(stars)}종목**\n\n"
            f"> ⚠️ 참고용입니다. 투자 손실 책임은 본인에게 있습니다."
        ),
        color = 0x333333,
    )
    print(f"[{datetime.now():%H:%M:%S}] 완료!")

if __name__ == "__main__":
    run()
