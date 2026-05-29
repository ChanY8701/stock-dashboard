# ============================================================
# scheduler.py  —  장중 감시 루프 + 4시 자동 리포트
# 실행: python scheduler.py
# ============================================================
import os
import time
import threading
from datetime import datetime, time as dtime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.sector_db     import SECTOR_DATABASE
from utils.kis_api      import fetch_sector_data, calc_sector_trading_value, get_tv_ratios_fn
from utils.discord_alert import (
    alert_leader_break, alert_golden_stars, send_daily_report, send_message
)

# ── 설정 ─────────────────────────────────────────────────────
INTRADAY_INTERVAL_SEC = 60        # 장중 감시 주기 (초)
MARKET_OPEN           = dtime(9, 0)
MARKET_CLOSE          = dtime(15, 30)
DAILY_REPORT_TIME     = dtime(16, 0)
DANGER_THRESHOLD      = -4.0      # 대장주 낙폭 경고 기준

# ── 중복 알림 방지용 플래그 ──────────────────────────────────
_alerted_leaders: set[str] = set()
_daily_sent_today: str      = ""   # 오늘 날짜 문자열


def is_market_hours() -> bool:
    now = datetime.now().time()
    return MARKET_OPEN <= now <= MARKET_CLOSE


def is_daily_report_time() -> bool:
    now = datetime.now().time()
    return (
        now.hour   == DAILY_REPORT_TIME.hour   and
        now.minute == DAILY_REPORT_TIME.minute
    )


def get_tv_ratios_fn(tv_dict: dict) -> dict:
    base = tv_dict.get("01_반도체_AI", 1) or 1
    return {k: v / base * 100 for k, v in tv_dict.items()}


# ── 장중 감시 루프 ────────────────────────────────────────────
def intraday_watch_loop():
    global _alerted_leaders

    print(f"[{datetime.now():%H:%M:%S}] 장중 감시 시작")
    send_message("✅ 순환매 상황실 스케줄러 가동. 장중 감시 시작합니다.")

    while True:
        now = datetime.now()

        if not is_market_hours():
            # 장 시작 전에는 플래그 초기화
            if now.time() < MARKET_OPEN:
                _alerted_leaders = set()
            time.sleep(30)
            continue

        try:
            stock_data = fetch_sector_data(SECTOR_DATABASE, max_workers=10)

            # ─ 대장주 부러짐 감시 ─
            for sec_key, sector in SECTOR_DATABASE.items():
                label   = sector.get("label", sec_key)
                leaders = sector.get("대장주", [])
                for leader in leaders:
                    d = stock_data.get(leader)
                    if not d:
                        continue
                    chg = d.get("change_rate", 0)
                    if chg <= DANGER_THRESHOLD and leader not in _alerted_leaders:
                        print(f"[DANGER] {leader} {chg:.2f}% — 디스코드 알림 발송")
                        alert_leader_break(label, leader, chg)
                        _alerted_leaders.add(leader)
                    # 회복 시 플래그 해제
                    elif chg > DANGER_THRESHOLD + 1 and leader in _alerted_leaders:
                        _alerted_leaders.discard(leader)

            # ─ 황금별 스캔 (장중 1회 알림, 오전 11시) ─
            if now.hour == 11 and now.minute == 0:
                stars = collect_golden_stars(stock_data)
                if stars:
                    alert_golden_stars(stars)

        except Exception as e:
            print(f"[ERROR] 장중 감시 오류: {e}")

        time.sleep(INTRADAY_INTERVAL_SEC)


# ── 황금별 목록 수집 ──────────────────────────────────────────
def collect_golden_stars(stock_data: dict) -> list[dict]:
    stars = []
    for sec_key, sector in SECTOR_DATABASE.items():
        label = sector.get("label", sec_key)
        for mid_name, sub_dict in sector.get("중분류", {}).items():
            for sub_name, stocks in sub_dict.items():
                for name in stocks:
                    d = stock_data.get(name)
                    if d and d.get("golden_star"):
                        stars.append({
                            "sector":      label,
                            "sub":         sub_name,
                            "name":        name,
                            "change_rate": d.get("change_rate", 0),
                            "vol_ratio":   d.get("vol_ratio", 0),
                        })
    return stars


# ── 일일 마감 리포트 스케줄러 ─────────────────────────────────
def daily_report_loop():
    global _daily_sent_today
    print(f"[{datetime.now():%H:%M:%S}] 일일 리포트 스케줄러 대기")

    while True:
        today_str = datetime.now().strftime("%Y-%m-%d")
        if is_daily_report_time() and _daily_sent_today != today_str:
            try:
                print(f"[REPORT] 일일 리포트 생성 중...")
                stock_data = fetch_sector_data(SECTOR_DATABASE, max_workers=10)
                tv_dict    = calc_sector_trading_value(SECTOR_DATABASE, stock_data)
                tv_ratios  = get_tv_ratios_fn(tv_dict)

                pass_sectors = [
                    SECTOR_DATABASE[k]["label"]
                    for k, v in tv_ratios.items() if v >= 40
                ]
                fail_sectors = [
                    SECTOR_DATABASE[k]["label"]
                    for k, v in tv_ratios.items() if v < 40
                ]
                golden_stars = collect_golden_stars(stock_data)
                tv_ratio_pct = {
                    SECTOR_DATABASE[k]["label"]: v
                    for k, v in tv_ratios.items()
                }

                send_daily_report(pass_sectors, fail_sectors, golden_stars, tv_ratio_pct)
                _daily_sent_today = today_str
                print(f"[REPORT] 발송 완료")
            except Exception as e:
                print(f"[ERROR] 리포트 오류: {e}")

        time.sleep(55)   # 1분 미만으로 체크


# ── 진입점 ────────────────────────────────────────────────────
if __name__ == "__main__":
    t1 = threading.Thread(target=intraday_watch_loop, daemon=True)
    t2 = threading.Thread(target=daily_report_loop,   daemon=True)
    t1.start()
    t2.start()

    print("스케줄러 실행 중. Ctrl+C로 종료.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("종료")
