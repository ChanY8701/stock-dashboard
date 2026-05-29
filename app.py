# ============================================================
# app.py  —  순환매 상황실 전광판  (Streamlit)
# ============================================================
import time
import streamlit as st
import pandas as pd
from datetime import datetime

# ── 내부 모듈 ─────────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from data.sector_db   import SECTOR_DATABASE
from utils.kis_api    import fetch_sector_data, calc_sector_trading_value
from utils.discord_alert import alert_leader_break

# ── 페이지 기본 설정 ──────────────────────────────────────────
st.set_page_config(
    page_title = "순환매 상황실 전광판",
    layout     = "wide",
    initial_sidebar_state = "collapsed",
)

# ── 전역 CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
/* ── 전체 배경 ── */
body, .main { background:#0d0d0d; color:#e8e8e8; font-family:'Noto Sans KR',sans-serif; }

/* ── 섹터 기둥 카드 ── */
.sector-col  { background:#141414; border:1px solid #2a2a2a; border-radius:8px;
               padding:8px 6px; margin:4px 2px; min-width:160px; }

/* ── 대분류 타이틀 배너 ── */
.sector-title { font-size:0.78rem; font-weight:700; padding:4px 6px;
                border-radius:4px; margin-bottom:6px; text-align:center; }
.pass-banner  { background:#003300; border:1px solid #00aa00; color:#00ff88; }
.fail-banner  { background:#330000; border:1px solid #aa0000; color:#ff4444; }

/* ── 중분류 / 소분류 헤더 ── */
.mid-label  { font-size:0.65rem; color:#888; margin:6px 0 2px 0;
              border-bottom:1px solid #2a2a2a; padding-bottom:2px; }
.sub-label  { font-size:0.60rem; color:#555; margin:4px 0 2px 4px; }

/* ── 종목 버튼/셀 ── */
.stock-cell { font-size:0.70rem; padding:2px 4px; margin:1px 0;
              border-radius:3px; display:flex; justify-content:space-between;
              align-items:center; }
.stock-hot   { background:#1a0000; color:#ff4444; }
.stock-star  { background:#1a1400; color:#ffd700; }
.stock-normal{ background:#111; color:#ccc; }

/* ── 거래대금 비율 바 ── */
.tv-bar-wrap { height:4px; background:#222; border-radius:2px; margin:4px 0 8px 0; }
.tv-bar-fill { height:4px; background:#00cc66; border-radius:2px; }

/* ── 실시간 위험 배너 ── */
.danger-banner { background:#ff0000; color:#fff; font-size:0.9rem; font-weight:700;
                 text-align:center; padding:10px; border-radius:6px; margin-bottom:12px;
                 animation: blink 0.8s step-start infinite; }
@keyframes blink { 50% { opacity:0.3; } }

/* ── 황금별 깜빡임 ── */
@keyframes goldBlink { 0%,100%{opacity:1} 50%{opacity:0.2} }
.blink-gold { animation: goldBlink 1.2s ease-in-out infinite; }

/* ── 상단 헤더 ── */
.dashboard-header { font-size:1.4rem; font-weight:900; color:#fff;
                    border-bottom:2px solid #333; padding-bottom:8px; margin-bottom:12px; }
.time-badge { font-size:0.75rem; color:#888; }
</style>
""", unsafe_allow_html=True)


# ── 모의 데이터 (KIS API 미연결 시 대체) ────────────────────
import random
def _mock_stock_data(sector_db: dict) -> dict:
    """개발/테스트용 랜덤 데이터 생성"""
    result = {}
    all_names: set[str] = set()
    for sector in sector_db.values():
        all_names.update(sector.get("대장주", []))
        for mid in sector.get("중분류", {}).values():
            for stocks in mid.values():
                all_names.update(stocks)
    for name in all_names:
        chg       = random.uniform(-5, 5)
        vol       = random.randint(10_000, 5_000_000)
        avg_5d    = random.randint(100_000, 3_000_000)
        is_golden = (-1.5 <= chg <= 1.5) and (vol <= avg_5d * 0.2)
        result[name] = {
            "change_rate":   round(chg, 2),
            "volume":        vol,
            "trading_value": random.randint(1_000_000_000, 200_000_000_000),
            "golden_star":   is_golden,
        }
    return result


# ── 데이터 로드 (30초 캐싱) ──────────────────────────────────
@st.cache_data(ttl=30)
def load_data():
    use_mock = os.getenv("KIS_APP_KEY", "") == ""
    if use_mock:
        sd = _mock_stock_data(SECTOR_DATABASE)
    else:
        sd = fetch_sector_data(SECTOR_DATABASE)
    tv = calc_sector_trading_value(SECTOR_DATABASE, sd)
    return sd, tv


# ── 반도체 기준 거래대금 비율 계산 ──────────────────────────
def get_tv_ratios(tv_dict: dict) -> dict:
    base = tv_dict.get("01_반도체_AI", 1) or 1
    return {k: v / base * 100 for k, v in tv_dict.items()}


# ── 종목 셀 HTML 렌더링 ───────────────────────────────────────
def render_stock_cell(name: str, data: dict | None) -> str:
    if not data:
        return f'<div class="stock-cell stock-normal">{name[:6]} <span>-</span></div>'

    chg    = data.get("change_rate", 0)
    is_hot  = abs(chg) > 3 or data.get("volume", 0) > 3_000_000
    is_star = data.get("golden_star", False)

    if is_star:
        cls   = "stock-star"
        badge = '<span class="blink-gold">⭐</span>'
    elif is_hot:
        cls   = "stock-hot"
        badge = "🚫"
    else:
        cls   = "stock-normal"
        badge = ""

    chg_str = f"{chg:+.1f}%" if chg != 0 else "0.0%"
    return (
        f'<div class="stock-cell {cls}">'
        f'<span>{name[:7]}{badge}</span>'
        f'<span style="font-size:0.62rem">{chg_str}</span>'
        f'</div>'
    )


# ── 섹터 기둥 HTML ────────────────────────────────────────────
def render_sector_column(key: str, sector: dict, stock_data: dict, tv_ratio: float) -> str:
    label    = sector.get("label", key)
    leaders  = sector.get("대장주", [])
    pass_ok  = tv_ratio >= 40

    banner_cls  = "pass-banner" if pass_ok else "fail-banner"
    banner_icon = "🟢 PASS" if pass_ok else "🔴 FAIL"

    # 거래대금 비율 바 (최대 100%)
    bar_w = min(tv_ratio, 100)

    html = f"""
    <div class="sector-col">
      <div class="sector-title {banner_cls}">
        {label}<br>{banner_icon} &nbsp;{tv_ratio:.0f}%
      </div>
      <div class="tv-bar-wrap"><div class="tv-bar-fill" style="width:{bar_w}%"></div></div>
      <div class="mid-label">🏆 대장주</div>
    """
    for ln in leaders:
        html += render_stock_cell(ln, stock_data.get(ln))

    # 중분류 → 소분류 → 종목
    for mid_name, sub_dict in sector.get("중분류", {}).items():
        html += f'<div class="mid-label">📂 {mid_name}</div>'
        for sub_name, stocks in sub_dict.items():
            html += f'<div class="sub-label">└ {sub_name}</div>'
            for name in stocks:
                html += render_stock_cell(name, stock_data.get(name))

    html += "</div>"
    return html


# ── 긴급 위험 배너 판단 ──────────────────────────────────────
def check_danger(stock_data: dict) -> list[str]:
    """대장주 -4% 이하 이탈 감지"""
    dangers = []
    for key, sector in SECTOR_DATABASE.items():
        for leader in sector.get("대장주", []):
            d = stock_data.get(leader)
            if d and d.get("change_rate", 0) <= -4.0:
                dangers.append((sector["label"], leader, d["change_rate"]))
    return dangers


# ── 메인 렌더링 ───────────────────────────────────────────────
def main():
    # 자동 새로고침 30초
    REFRESH_SEC = 30

    # 헤더
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.markdown(
        f'<div class="dashboard-header">📡 순환매 상황실 전광판 '
        f'<span class="time-badge">⏱ {now_str} &nbsp;|&nbsp; 30초 자동갱신</span></div>',
        unsafe_allow_html=True,
    )

    # 사이드바 — 설정
    with st.sidebar:
        st.header("⚙️ 설정")
        st.caption("KIS API 연결 상태")
        kis_ok = os.getenv("KIS_APP_KEY","") != ""
        st.success("✅ KIS API 연결됨") if kis_ok else st.warning("⚠️ 모의(Mock) 데이터 모드")
        st.divider()
        st.caption("Discord 알림")
        disc_ok = os.getenv("DISCORD_WEBHOOK_URL","") != ""
        st.success("✅ Discord 연결됨") if disc_ok else st.warning("⚠️ Discord 미설정")
        st.divider()
        if st.button("🔄 강제 새로고침"):
            st.cache_data.clear()
            st.rerun()

    # 데이터 로드
    with st.spinner("시세 로딩 중..."):
        stock_data, tv_dict = load_data()

    tv_ratios = get_tv_ratios(tv_dict)

    # ── 긴급 위험 배너 ─────────────────────────────────────
    dangers = check_danger(stock_data)
    if dangers:
        for sec_label, leader, chg in dangers:
            st.markdown(
                f'<div class="danger-banner">🚨 위험! [{sec_label}] 대장주 <b>{leader}</b> '
                f'{chg:.2f}% 부러짐 — 아우 종목 즉시 손절 권장!</div>',
                unsafe_allow_html=True,
            )
            # 디스코드 알림 (중복 방지는 session_state로 관리)
            alert_key = f"alerted_{leader}"
            if not st.session_state.get(alert_key):
                alert_leader_break(sec_label, leader, chg)
                st.session_state[alert_key] = True
    else:
        # 이전 알림 플래그 초기화
        for k in list(st.session_state.keys()):
            if k.startswith("alerted_"):
                del st.session_state[k]

    # ── 황금별 요약 배너 ────────────────────────────────────
    all_stars = [
        {"name": name, "sector": sec["label"], "change_rate": d["change_rate"]}
        for sec_key, sec in SECTOR_DATABASE.items()
        for mid in sec.get("중분류", {}).values()
        for stocks in mid.values()
        for name in stocks
        if (d := stock_data.get(name)) and d.get("golden_star")
    ]
    if all_stars:
        star_text = "  |  ".join([f"⭐ {s['name']} ({s['change_rate']:+.1f}%)" for s in all_stars[:8]])
        st.markdown(
            f'<div style="background:#1a1400;border:1px solid #ffd700;border-radius:6px;'
            f'padding:8px;margin-bottom:10px;font-size:0.78rem;color:#ffd700">'
            f'🔍 황금별 타점 감지: {star_text}</div>',
            unsafe_allow_html=True,
        )

    # ── 전광판 기둥 배치 ─────────────────────────────────────
    sector_keys  = list(SECTOR_DATABASE.keys())
    COLS_PER_ROW = 5   # 한 행에 5개 섹터

    for row_start in range(0, len(sector_keys), COLS_PER_ROW):
        row_keys = sector_keys[row_start : row_start + COLS_PER_ROW]
        cols     = st.columns(len(row_keys))
        for col, key in zip(cols, row_keys):
            sector    = SECTOR_DATABASE[key]
            tv_ratio  = tv_ratios.get(key, 0)
            html_col  = render_sector_column(key, sector, stock_data, tv_ratio)
            with col:
                st.markdown(html_col, unsafe_allow_html=True)

    # ── 자동 새로고침 (meta-refresh 방식) ───────────────────
    st.markdown(
        f'<meta http-equiv="refresh" content="{REFRESH_SEC}">',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
