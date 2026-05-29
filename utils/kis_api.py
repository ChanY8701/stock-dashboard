# ============================================================
# kis_api.py  —  한국투자증권 KIS Developers API 핸들러
# ============================================================
import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from functools import lru_cache
import threading

# ── 환경변수에서 키 로드 (절대 하드코딩 금지) ──────────────────
KIS_APP_KEY    = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
KIS_ACCOUNT    = os.getenv("KIS_ACCOUNT", "")       # 계좌번호 (XXXXXXXXXX-XX)
KIS_MOCK       = os.getenv("KIS_MOCK", "false").lower() == "true"  # 모의투자 여부

BASE_URL = (
    "https://openapivts.koreainvestment.com:29443"   # 모의투자
    if KIS_MOCK else
    "https://openapi.koreainvestment.com:9443"        # 실전
)

# ── 토큰 캐시 (만료 전까지 재사용) ────────────────────────────
_token_cache: dict = {"access_token": None, "expires_at": 0}
_token_lock = threading.Lock()


def get_access_token() -> str:
    """OAuth2 접근 토큰 발급 (24시간 캐싱)"""
    with _token_lock:
        now = time.time()
        if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
            return _token_cache["access_token"]

        url = f"{BASE_URL}/oauth2/tokenP"
        body = {
            "grant_type":  "client_credentials",
            "appkey":      KIS_APP_KEY,
            "appsecret":   KIS_APP_SECRET,
        }
        resp = requests.post(url, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"]   = now + int(data.get("expires_in", 86400))
        return _token_cache["access_token"]


def _headers(tr_id: str) -> dict:
    return {
        "content-type":  "application/json; charset=utf-8",
        "authorization": f"Bearer {get_access_token()}",
        "appkey":        KIS_APP_KEY,
        "appsecret":     KIS_APP_SECRET,
        "tr_id":         tr_id,
        "custtype":      "P",
    }


# ── 종목코드 조회용 캐시 (이름 → 코드) ────────────────────────
_name_to_code: dict[str, str] = {}

def load_stock_code_map(csv_path: str = "data/stock_codes.csv"):
    """
    한국거래소 종목 마스터(CSV) 로딩
    컬럼: 종목코드, 종목명
    없으면 KIS 검색 API로 폴백
    """
    global _name_to_code
    try:
        df = pd.read_csv(csv_path, dtype=str)
        _name_to_code = dict(zip(df["종목명"], df["종목코드"]))
    except FileNotFoundError:
        pass  # 동적 검색으로 폴백


def search_stock_code(name: str) -> str | None:
    """종목명 → 종목코드 (KIS 검색 API 폴백)"""
    if name in _name_to_code:
        return _name_to_code[name]

    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/search-stock-info"
    params = {"PRDT_TYPE_CD": "300", "MKET_ID_CD": "STK", "PDNO": name}
    try:
        resp = requests.get(url, headers=_headers("CTPF1604R"), params=params, timeout=5)
        items = resp.json().get("output", [])
        if items:
            code = items[0]["shtn_pdno"]
            _name_to_code[name] = code
            return code
    except Exception:
        pass
    return None


# ── 주식 현재가 조회 ───────────────────────────────────────────
def get_current_price(code: str) -> dict:
    """
    반환: {
        code, name, current_price, change_rate,
        volume, trading_value, open, high, low
    }
    """
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    resp = requests.get(url, headers=_headers("FHKST01010100"), params=params, timeout=5)
    resp.raise_for_status()
    o = resp.json().get("output", {})
    return {
        "code":          code,
        "name":          o.get("hts_kor_isnm", ""),
        "current_price": int(o.get("stck_prpr", 0)),
        "change_rate":   float(o.get("prdy_ctrt", 0)),      # 전일대비 등락률(%)
        "volume":        int(o.get("acml_vol", 0)),          # 당일 누적거래량
        "trading_value": int(o.get("acml_tr_pbmn", 0)),      # 당일 누적거래대금(원)
        "open":          int(o.get("stck_oprc", 0)),
        "high":          int(o.get("stck_hgpr", 0)),
        "low":           int(o.get("stck_lwpr", 0)),
    }


# ── 과거 일봉 (5거래일 평균거래량 계산용) ─────────────────────
def get_daily_ohlcv(code: str, days: int = 10) -> pd.DataFrame:
    """
    최근 N 거래일 OHLCV 반환
    컬럼: date, open, high, low, close, volume
    """
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    end_dt   = datetime.today().strftime("%Y%m%d")
    start_dt = (datetime.today() - timedelta(days=days * 2)).strftime("%Y%m%d")
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD":         code,
        "FID_INPUT_DATE_1":       start_dt,
        "FID_INPUT_DATE_2":       end_dt,
        "FID_PERIOD_DIV_CODE":    "D",
        "FID_ORG_ADJ_PRC":        "0",
    }
    resp = requests.get(url, headers=_headers("FHKST03010100"), params=params, timeout=8)
    resp.raise_for_status()
    rows = resp.json().get("output2", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "stck_bsop_date": "date",
        "stck_oprc": "open",
        "stck_hgpr": "high",
        "stck_lwpr": "low",
        "stck_clpr": "close",
        "acml_vol":  "volume",
    })[["date","open","high","low","close","volume"]]
    df = df.astype({"open":"int","high":"int","low":"int","close":"int","volume":"int"})
    return df.sort_values("date").tail(days).reset_index(drop=True)


# ── 황금별 ★ 판정 ─────────────────────────────────────────────
def is_golden_star(code: str, current: dict | None = None) -> bool:
    """
    조건:
    1. 당일 등락률 -1.5% ~ +1.5%
    2. 당일 거래량 ≤ 최근 5거래일 평균 거래량의 20%
    """
    try:
        if current is None:
            current = get_current_price(code)
        chg = current["change_rate"]
        if not (-1.5 <= chg <= 1.5):
            return False

        hist = get_daily_ohlcv(code, days=6)
        if len(hist) < 5:
            return False
        avg_vol_5d = hist["volume"].iloc[:-1].tail(5).mean()
        today_vol  = current["volume"]
        return today_vol <= avg_vol_5d * 0.20
    except Exception:
        return False


# ── 일괄 섹터 데이터 수집 ──────────────────────────────────────
def fetch_sector_data(sector_db: dict, max_workers: int = 8) -> dict:
    """
    전체 섹터 종목의 현재가 + 황금별 여부를 병렬로 수집.
    반환: { 종목명: {current_price, change_rate, volume, trading_value, golden_star} }
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 전체 종목명 수집
    all_names: set[str] = set()
    for sector in sector_db.values():
        all_names.update(sector.get("대장주", []))
        for mid in sector.get("중분류", {}).values():
            for stocks in mid.values():
                all_names.update(stocks)

    results: dict = {}

    def fetch_one(name: str):
        code = search_stock_code(name)
        if not code:
            return name, None
        try:
            cur = get_current_price(code)
            cur["golden_star"] = is_golden_star(code, cur)
            return name, cur
        except Exception as e:
            return name, {"error": str(e)}

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_one, n): n for n in all_names}
        for fut in as_completed(futures):
            name, data = fut.result()
            results[name] = data

    return results


# ── 섹터별 총거래대금 집계 ─────────────────────────────────────
def calc_sector_trading_value(sector_db: dict, stock_data: dict) -> dict:
    """
    반환: { "01_반도체_AI": 1234567890, ... }
    """
    totals = {}
    for key, sector in sector_db.items():
        tv = 0
        for mid in sector.get("중분류", {}).values():
            for stocks in mid.values():
                for name in stocks:
                    d = stock_data.get(name)
                    if d and "trading_value" in d:
                        tv += d["trading_value"]
        totals[key] = tv
    return totals
