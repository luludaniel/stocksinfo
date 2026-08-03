from __future__ import annotations

from datetime import date, datetime, timedelta

import history

VOLUME_SPIKE_RATIO = 2.0
PER_BAND_MIN_SAMPLES = 20
TARGET_PRICE_CHANGE_THRESHOLD_PCT = 3.0
EARNINGS_LOOKAHEAD_DAYS = 7
# Ceiling on how stale the "prior" snapshot may be before a target-price
# comparison stops being labeled a recent change. Without this, a sparse DB
# could compare against a snapshot from months ago and still call it "주간".
TARGET_PRICE_LOOKBACK_MAX_DAYS = 14

ALL_SIGNAL_TYPES = frozenset({
    "ma200_cross", "week52_high", "week52_low", "volume_spike",
    "earnings_soon", "valuation_band", "target_price_change",
})


def _allowed(cfg: dict, signal_type: str) -> bool:
    """A symbol's resolved `signals` list is a full allow-list (profile,
    overridden per-symbol via store.resolve_symbol_config). No list at all
    (e.g. a caller that never wired store.py config through) means "no
    restriction" — every signal type stays eligible.
    """
    signals = cfg.get("signals")
    return signal_type in signals if signals is not None else True


def _threshold(cfg: dict, key: str, default):
    return (cfg.get("thresholds") or {}).get(key, default)


def evaluate(watchlist: dict, fundamentals: dict, today: str, resolved_config: dict | None = None) -> list[dict]:
    """The rule engine: numbers and verdicts are decided here in Python, not
    by the LLM. A signal only exists if a rule below actually fires — a quiet
    day for a stock means it produces nothing at all.

    resolved_config is {symbol: {"signals": [...], "thresholds": {...}}} from
    store.resolve_all_symbols() — a "핵심보유" profile might skip volume
    spikes entirely while a "관찰중" one wants a lower spike threshold.
    """
    resolved_config = resolved_config or {}
    detected = []
    for symbol, pos in (watchlist or {}).items():
        if not pos or "error" in pos:
            continue
        detected.extend(_position_signals(symbol, pos, resolved_config.get(symbol, {})))

    for symbol, fund in (fundamentals or {}).items():
        if not fund or "error" in fund:
            continue
        detected.extend(_fundamental_signals(symbol, fund, today, resolved_config.get(symbol, {})))

    return detected


def _position_signals(symbol: str, pos: dict, cfg: dict | None = None) -> list[dict]:
    cfg = cfg or {}
    out = []

    if _allowed(cfg, "ma200_cross"):
        cross = pos.get("ma200_cross")
        months = pos.get("ma200_cross_months_since_prior")
        detail = f" ({months}개월 만)" if months else ""
        if cross == "golden":
            out.append({
                "symbol": symbol, "severity": "yellow", "type": "ma200_cross",
                "message": f"200일선 상향 돌파{detail}",
            })
        elif cross == "death":
            out.append({
                "symbol": symbol, "severity": "red", "type": "ma200_cross",
                "message": f"200일선 하향 이탈{detail}",
            })

    if _allowed(cfg, "week52_high") and pos.get("is_new_52w_high"):
        out.append({
            "symbol": symbol, "severity": "yellow", "type": "week52_high",
            "message": "52주 신고가 경신",
        })
    if _allowed(cfg, "week52_low") and pos.get("is_new_52w_low"):
        out.append({
            "symbol": symbol, "severity": "red", "type": "week52_low",
            "message": "52주 신저가 경신",
        })

    if _allowed(cfg, "volume_spike"):
        ratio = pos.get("volume_ratio")
        threshold = _threshold(cfg, "volume_spike_ratio", VOLUME_SPIKE_RATIO)
        if ratio is not None and ratio >= threshold:
            out.append({
                "symbol": symbol, "severity": "yellow", "type": "volume_spike",
                "message": f"거래량 20일 평균 대비 {ratio}배",
            })

    return out


def _fundamental_signals(symbol: str, fund: dict, today: str, cfg: dict | None = None) -> list[dict]:
    cfg = cfg or {}
    out = []

    if _allowed(cfg, "earnings_soon"):
        next_earnings = fund.get("next_earnings_date")
        lookahead = _threshold(cfg, "earnings_lookahead_days", EARNINGS_LOOKAHEAD_DAYS)
        if next_earnings:
            try:
                edate = datetime.fromisoformat(str(next_earnings)[:10]).date()
                days_left = (edate - date.fromisoformat(today)).days
                if 0 <= days_left <= lookahead:
                    out.append({
                        "symbol": symbol, "severity": "yellow", "type": "earnings_soon",
                        "message": f"실적발표 D-{days_left}",
                    })
            except ValueError:
                pass

    if _allowed(cfg, "valuation_band"):
        trailing_pe = fund.get("trailing_pe")
        if trailing_pe is not None:
            since = _days_ago(today, 730)
            pe_values = [
                r["trailing_pe"] for r in history.get_snapshots_since(symbol, since)
                if r.get("trailing_pe") is not None
            ]
            # A real 5-year PER band needs 5 years of stored snapshots, which
            # a fresh DB doesn't have yet — the band strengthens as history
            # accumulates. Below this floor we skip rather than judge on noise.
            if len(pe_values) >= PER_BAND_MIN_SAMPLES:
                mean = sum(pe_values) / len(pe_values)
                variance = sum((v - mean) ** 2 for v in pe_values) / len(pe_values)
                std = variance ** 0.5
                if std > 0 and abs(trailing_pe - mean) > std:
                    direction = "상단" if trailing_pe > mean else "하단"
                    out.append({
                        "symbol": symbol, "severity": "yellow", "type": "valuation_band",
                        "message": f"PER {trailing_pe:.1f}배 — 자체 밴드 {direction} 이탈 (평균 {mean:.1f}배)",
                    })

    if _allowed(cfg, "target_price_change"):
        target_mean = fund.get("target_mean_price")
        if target_mean is not None:
            prior = history.get_latest_snapshot_before(symbol, _days_ago(today, 6))
            prior_target = prior.get("target_mean_price") if prior else None
            if prior_target and prior.get("date"):
                elapsed_days = (date.fromisoformat(today) - date.fromisoformat(prior["date"])).days
                # A sparse DB can return a snapshot from months ago as "the
                # most recent one before 6 days ago" — cap how stale it may
                # be before we stop calling the comparison recent.
                if elapsed_days <= TARGET_PRICE_LOOKBACK_MAX_DAYS:
                    change_pct = (target_mean - prior_target) / prior_target * 100
                    if abs(change_pct) >= TARGET_PRICE_CHANGE_THRESHOLD_PCT:
                        direction = "상향" if change_pct > 0 else "하향"
                        out.append({
                            "symbol": symbol, "severity": "yellow", "type": "target_price_change",
                            "message": f"애널리스트 목표주가 {elapsed_days}일간 {direction} {abs(change_pct):.1f}%",
                        })

    return out


def _days_ago(today: str, days: int) -> str:
    return (date.fromisoformat(today) - timedelta(days=days)).isoformat()
