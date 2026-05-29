# ============================================================
# discord_alert.py  —  Discord Webhook + Bot 알림 핸들러
# ============================================================
import os
import requests
from datetime import datetime

# 환경변수 설정
# DISCORD_WEBHOOK_URL  : 채널 우클릭 → 웹후크 → URL 복사
# DISCORD_BOT_TOKEN    : (선택) 슬래시 명령 등 확장 시 사용
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_BOT_TOKEN   = os.getenv("DISCORD_BOT_TOKEN", "")


def _post_webhook(payload: dict) -> bool:
    """Discord Webhook으로 메시지 전송"""
    if not DISCORD_WEBHOOK_URL:
        print("[DISCORD] WEBHOOK URL 없음 — 환경변수 DISCORD_WEBHOOK_URL 확인")
        return False
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        return resp.status_code in (200, 204)
    except Exception as e:
        print(f"[DISCORD] 전송 실패: {e}")
        return False


# ── 기본 텍스트 알림 ──────────────────────────────────────────
def send_message(content: str) -> bool:
    return _post_webhook({"content": content})


# ── Embed(카드형) 알림 ────────────────────────────────────────
def send_embed(title: str, description: str, color: int = 0xFF0000, fields: list = None) -> bool:
    embed = {
        "title":       title,
        "description": description,
        "color":       color,
        "timestamp":   datetime.utcnow().isoformat(),
        "footer":      {"text": "순환매 상황실 | KIS API"},
    }
    if fields:
        embed["fields"] = fields
    return _post_webhook({"embeds": [embed]})


# ── 🚨 대장주 부러짐 긴급 알림 ────────────────────────────────
def alert_leader_break(sector_label: str, leader_name: str, change_rate: float):
    """
    대장주가 -4% 이탈 시 호출
    color: 빨간색 0xFF0000
    """
    send_embed(
        title       = f"🚨 [{sector_label}] 대장주 부러짐 포착!",
        description = (
            f"**{leader_name}** 현재 등락률: `{change_rate:.2f}%`\n"
            f"> 아우 종목 **즉시 손절 / 비중 축소** 권장\n"
            f"> 섹터 전체 매수 신규진입 **금지**"
        ),
        color       = 0xFF0000,
        fields      = [
            {"name": "발생시각", "value": datetime.now().strftime("%H:%M:%S"), "inline": True},
            {"name": "기준선", "value": "-4.0%", "inline": True},
        ],
    )


# ── ⭐ 황금별 타점 알림 ──────────────────────────────────────
def alert_golden_stars(stars: list[dict]):
    """
    stars: [{"sector": "반도체 & AI", "sub": "TC본더", "name": "한미반도체",
              "change_rate": 0.3, "vol_ratio": 0.15}, ...]
    """
    if not stars:
        return
    lines = []
    for s in stars:
        lines.append(
            f"⭐ **{s['name']}** ({s['sector']} > {s['sub']})  "
            f"등락률 `{s['change_rate']:+.2f}%`  거래량비율 `{s['vol_ratio']*100:.0f}%`"
        )
    send_embed(
        title       = f"⭐ 황금별 타점 감지 — {len(stars)}종목",
        description = "\n".join(lines),
        color       = 0xFFD700,   # 골드
    )


# ── 📊 일일 마감 리포트 ───────────────────────────────────────
def send_daily_report(
    pass_sectors: list[str],
    fail_sectors: list[str],
    golden_stars: list[dict],
    sector_tv_ratio: dict,
):
    """
    오후 4시 자동 발송용 일일 요약 리포트
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # PASS / FAIL 섹터 요약
    pass_lines = "\n".join([f"🟢 {s}" for s in pass_sectors]) or "없음"
    fail_lines = "\n".join([f"🔴 {s}" for s in fail_sectors]) or "없음"

    # 거래대금 비율 TOP
    sorted_tv = sorted(sector_tv_ratio.items(), key=lambda x: x[1], reverse=True)
    tv_lines  = "\n".join([f"`{k}` {v:.1f}%" for k, v in sorted_tv[:5]])

    # 황금별 요약
    star_lines = (
        "\n".join([f"⭐ {s['name']} ({s['sector']})" for s in golden_stars[:10]])
        or "오늘은 없음"
    )

    fields = [
        {"name": "🟢 PASS 섹터",          "value": pass_lines, "inline": False},
        {"name": "🔴 FAIL 섹터",          "value": fail_lines, "inline": False},
        {"name": "📊 거래대금 비율 TOP5", "value": tv_lines,   "inline": False},
        {"name": "⭐ 황금별 타점 종목",   "value": star_lines, "inline": False},
    ]

    send_embed(
        title       = f"📋 일일 순환매 상황실 리포트 — {now_str}",
        description = "장 마감 자동 스캔 결과입니다. 내일 길목 지키기 참고용.",
        color       = 0x00BFFF,   # 하늘색
        fields      = fields,
    )
