# 개편 결과 리뷰 (commit `adedb2a`)

리뷰일: 2026-08-02 · 대상: Phase 1~2 + Phase 3 일부

---

## 총평

**구조는 제대로 잡혔습니다.** 특히 이 두 가지가 핵심을 정확히 짚었습니다.

- 규칙 엔진(`signals.py`)이 숫자와 판정을 담당하고 LLM은 해석만 → **LLM이 숫자를 지어낼 구조적 여지가 사라짐**
- 신호 0건이면 LLM 호출 자체를 생략 → 조용한 날이 조용하게 읽힘

`history.py`의 SQLite 스냅샷도 REDESIGN.md가 "전체 개선의 70%"라고 한 부분을 제대로 구현했습니다.
`period="1y"`가 251행이라 12개월 수익률이 항상 `None`이던 것을 찾아낸 것도 좋습니다.

다만 **아직 실제 yfinance 응답으로 한 번도 돌려보지 않은 상태**로 보이고,
그 위에 아래 이슈들이 남아 있습니다.

---

## 🔴 반드시 처리 (동작·신뢰에 직결)

### 1. 컬렉터 3개가 매일 헛돌고 결과가 버려짐
`main.py`가 `us_market`, `kr_market`, `news`를 fetch하지만 `build_email`은 이 셋을 받지 않습니다.

```python
# main.py:144
email_body = build_email(
    data.get("watchlist"), data.get("fundamentals"), data.get("economic_cal")
)   # ← us_market, kr_market, news 없음
```

`_attach_related_news`가 쓰는 뉴스는 `news.py`가 아니라 **watchlist 안의 yfinance 뉴스**입니다.
즉 매일 RSS 3개를 긁어서 통째로 버리고, 지수 데이터도 버립니다.
→ **연결하든 제거하든 결정 필요.** 지금은 실패해도 `_errors`만 늘어납니다.

### 2. 종목별 실패가 사용자에게 안 보임 ★ 가장 위험
`watchlist_stocks.fetch`는 실패 시 `result[sym] = {"error": ...}`를 넣고,
`signals.evaluate`는 `if "error" in pos: continue`로 조용히 건너뜁니다.

**결과: 전 종목 수집이 실패해도 이메일은 "신호 0건 / 특이사항 없습니다"로 나갑니다.**
정상인 날과 완전히 실패한 날이 구분되지 않습니다.

yfinance는 GitHub Actions 공용 IP에서 429(rate limit)를 자주 던지고,
지금 호출량은 **종목당 4회**(`history` + `news` + `info` + `calendar`) + 벤치마크 2회입니다.
5종목이면 22회. 충분히 맞을 수 있는 수치입니다.

→ 종목 error를 `_errors`로 올리고, 실패 종목이 있으면 이메일 상단에 명시.

### 3. `future.result(timeout=30)`이 아무 일도 하지 않음
```python
for future in as_completed(futures):
    results[name] = future.result(timeout=30)
```
`as_completed`는 **이미 완료된** future만 내주므로 `result()`는 절대 블록되지 않습니다.
타임아웃이 사실상 없습니다. yfinance 호출 하나가 걸리면 워크플로 20분 한도까지 매달립니다.
→ `as_completed(futures, timeout=120)`로 옮기고 `TimeoutError` 처리.

### 4. "주간 목표주가 변화"가 주간이 아닐 수 있음
```python
prior = history.get_latest_snapshot_before(symbol, _days_ago(today, 6))
```
6일 전보다 **이전의 가장 최근** 스냅샷을 가져옵니다. 하한이 없습니다.
DB가 듬성듬성하면 3개월 전 값과 비교해놓고 **"주간 하향 12%"**라고 표기합니다.
→ 하한 추가 (예: `today-14`보다 오래되면 신호 생략), 또는 실제 경과일수를 문구에 반영.

### 5. 거래량 급증 비율이 과소평가됨
```python
volume_avg_20d = float(volume.iloc[-20:].mean())   # ← 오늘이 포함됨
```
오늘 거래량이 평소의 10배면 평균 자체가 1.45배로 올라가, 비율이 10이 아니라 **6.9**로 나옵니다.
임계값 2.0은 넘겠지만 **표시되는 숫자가 틀립니다.** 이메일에 "20일 평균 대비 6.9배"로 인쇄됩니다.
→ `volume.iloc[-21:-1]`로 오늘 제외.

---

## 🟡 개선 권장 (정보 가치에 직결)

### 6. 축 A를 다 계산해놓고 이메일에 한 번도 안 씀 ★ 제일 아까움
`_position_metrics`가 만드는 필드 중 **실제로 쓰이는 건 4개뿐**입니다.

| 필드 | 사용처 |
|---|---|
| `ma200_cross`, `is_new_52w_high/low`, `volume_ratio` | ✅ signals.py |
| `week52_pct` | ❌ 미사용 |
| `pct_vs_ma200` | ❌ 미사용 |
| `drawdown_from_high_pct` | ❌ 미사용 |
| `return_3m/6m/12m_pct` | ❌ 미사용 |
| `relative_strength_6m_pct` | ❌ 미사용 |

REDESIGN.md 축 A의 취지는 *"AAPL은 52주 밴드 88% 지점, 200일선 +14%, 6개월 S&P500 대비 +9%p"*
같은 한 줄을 보여주는 것이었는데, 계산만 하고 버리고 있습니다.

→ `⚪ 정상 범위` 블록을 티커 나열에서 **위치 한 줄 요약**으로 승격:
```
⚪ 정상 범위 (3)
  TSLA      52주 41% · 200일선 -3% · 6M +12%p
  000660    52주 77% · 200일선 +9% · 6M  -4%p
```
신호가 없는 날에도 읽을 가치가 생깁니다. **이 하나가 체감 개선이 가장 큽니다.**

### 7. 초기 한 달은 신호가 3종류뿐
축 B 신호의 히스토리 요구량:

| 신호 | 필요 히스토리 | 첫 발생 시점 |
|---|---|---|
| 200일선 교차 / 52주 신고저 / 거래량 | 없음 (당일 계산) | 즉시 |
| 목표주가 주간 변화 | 6일+ | 약 1주 후 |
| PER 밴드 이탈 | 20개 샘플 | **약 4주 후** |

즉 **첫 한 달은 개편 전과 체감이 크게 다르지 않을 수 있습니다.**
→ 6번(위치 요약 노출)을 먼저 하면 이 공백이 메워집니다.
→ 이메일 하단에 `히스토리 축적 12일차 · PER 밴드 활성화까지 8일` 한 줄 추가도 유용.

### 8. 종목명이 없음
`005930.KS`, `000660.KS`, `069500.KS`로 표시됩니다.
2~3분 훑기가 목표인데 **티커를 암산으로 변환**해야 합니다.
→ `info["shortName"]` 캐싱 또는 `watchlist.json`에 이름 필드 추가.
`005930 삼성전자` 형태가 맞습니다.

### 9. 모바일 이메일 가독성 미검증
`email_sender`가 `<pre>` 태그로 감싸는데, 이모지 + 고정폭 정렬 + `<pre>`는
**Gmail 모바일에서 폰트가 줄고 가로 스크롤이 생기기 쉽습니다.**
`f"  {s['symbol']:<8}{s['message']}"`도 `005930.KS`(9자)에서 이미 정렬이 깨집니다.
→ 실제 수신 화면 확인 필요. 깨지면 `<pre>` 대신 간단한 HTML 테이블/div로.

---

## ⚪ 사소함

- `build_email()`이 이름과 달리 DB 쓰기 부작용을 가짐(`_save_snapshots`). 메일 발송 실패 시에도 저장됨 → `main()`으로 분리
- `datetime.utcnow()`, `utcfromtimestamp()` 는 Python 3.12+ deprecated (현재 3.11이라 동작은 함)
- 워크플로 `git push`에 재시도/`pull --rebase` 없음 → 충돌 시 그날 히스토리 유실
- 바이너리 DB를 매일 커밋 → diff가 무의미. CSV로 저장하면 히스토리 변화가 눈에 보임 (선택)
- `report.group_signals`는 red/yellow만 렌더 → severity 추가 시 조용히 누락

---

## 다음 단계 우선순위

```
1. 실제 1회 실행 검증          ← 가장 먼저. 아래 전부 이것에 달림
2. 🔴 2번 (실패 가시화)         ← 신뢰 문제
3. 🟡 6번 (위치 요약 노출)      ← 체감 개선 최대
4. 🔴 1·3·4·5번 (정확성 버그)
5. 🟡 8번 (종목명)
6. 🟡 9번 (모바일 확인)
```

**1번이 압도적으로 먼저입니다.** 지금까지 검증된 건 80개의 mock 테스트뿐이고,
`ticker.calendar`, `info["targetMeanPrice"]`, `ticker.news`의 **실제 응답 형태는 아직 아무도 안 봤습니다.**
yfinance는 이 필드들의 구조를 자주 바꿉니다.

```bash
cd ~/dev/stocksinfo
python -c "from collectors import watchlist_stocks, fundamentals; import json; \
print(json.dumps(watchlist_stocks.fetch(['NVDA','005930.KS']), indent=2, ensure_ascii=False))"
python -c "from collectors import fundamentals; import json; \
print(json.dumps(fundamentals.fetch(['NVDA','005930.KS']), indent=2, ensure_ascii=False))"
python main.py    # 실제 메일 수신까지
```
