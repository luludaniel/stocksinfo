# StocksInfo 대시보드 명세서

버전: 0.1 (초안) · 작성일: 2026-08-02
선행 문서: `REDESIGN.md`, `REVIEW.md`

---

## 0. 확정된 전제

| 항목 | 결정 |
|---|---|
| 편집 범위 | **종목별 개별 설정** + **이메일 구성** |
| 추천 성격 | **내 종목 우선순위** + **신규 발굴** (분리된 영역) |
| 구동 방식 | **GitHub Pages 정적 페이지** |
| 데이터 신선도 | 기본은 배치 결과, **버튼으로 갱신** |
| 비용 | 무료만 |
| 사용자 | 중장기 보유 투자자 1인 |

---

## 1. 목적과 비목적

### 목적
1. 이메일이 "이미 설정된 것"만 보여주는 한계를 깨고, **설정 자체를 브라우저에서 바꾼다**
2. 신호가 여러 개일 때 **무엇부터 볼지** 당일 기사를 반영해 순서를 매긴다
3. 관심종목 밖에서 **오늘 이슈가 생긴 종목**을 후보로 제시한다

### 비목적 (명시적으로 안 함)
- 실시간 시세 · 차트 트레이딩 도구 (중장기 투자자에게 불필요)
- 매수/매도 추천, 목표가·손절가 제시
- 주문 실행, 계좌 연동

---

## 2. 핵심 아키텍처 결정

### 2.1 정적 페이지에서 "편집"과 "갱신"을 하는 방법

GitHub Pages는 서버가 없습니다. 따라서 **브라우저가 GitHub API를 직접 호출**합니다.

```
┌─────────────────────────────────────────────────────────┐
│  브라우저 (GitHub Pages에서 로드된 정적 HTML/JS)          │
│                                                          │
│   ① 데이터 읽기   GET  /repos/../contents/data/latest.json│
│   ② 설정 저장     PUT  /repos/../contents/config/*.json   │
│   ③ 지금 갱신     POST /repos/../actions/workflows/../dispatches
│                                                          │
│   인증: Fine-grained PAT (localStorage 보관)             │
└─────────────────────────────────────────────────────────┘
                          ↕
┌─────────────────────────────────────────────────────────┐
│  GitHub Actions  (매일 07:30 KST + workflow_dispatch)     │
│   collect → signals → recommend → 산출물 2개              │
│     · 이메일 발송                                         │
│     · data/latest.json 커밋                               │
└─────────────────────────────────────────────────────────┘
```

**중요:** 데이터를 Pages에 정적 파일로 굽지 않고 **GitHub API로 가져옵니다.**
이유 두 가지:

- Pages 재빌드(30~60초)를 갱신 루프에서 제거 → 갱신 버튼이 빨라짐
- 정적 셸에는 데이터가 0 → **URL이 노출돼도 내 종목이 안 보임** (아래 2.2)

### 2.2 프라이버시 — 결정 필요 ⚠️

무료 플랜에서 **GitHub Pages는 public 저장소에서만** 동작합니다.
즉 `data/latest.json`을 같은 저장소에 두면 **내 관심종목·보유메모가 전세계 공개**됩니다.

| 옵션 | 구성 | 노출 | 난이도 |
|---|---|---|---|
| **A. 단일 public 저장소** | 지금 구조 그대로 | 관심종목 티커 공개 | ★ |
| **B. 셸/데이터 분리** | public(셸+Pages) + private(데이터·설정) | 없음 | ★★★ |
| **C. Cloudflare Pages + Access** | private 저장소 유지, 이메일 OTP 인증 | 없음 | ★★ |

> **권장: C.** Cloudflare Pages는 private repo를 지원하고 Access(무료 티어)로
> 본인 이메일 OTP 인증을 걸 수 있습니다. GitHub Pages를 고집할 이유가 없다면
> 프라이버시·난이도 균형이 가장 좋습니다.
>
> **A로 시작해도 무방한 경우:** 보유수량·메모를 저장하지 않고 티커만 관리한다면
> 실질 위험은 낮습니다. 단 §4의 `memo`, `shares` 필드는 쓰지 마세요.

**이 문서는 A/C 어느 쪽이든 동작하도록 작성되었습니다.** (호스팅만 다름)

### 2.3 인증 토큰

- **Fine-grained PAT**, 대상 저장소 1개로 한정
- 권한: `Contents: Read and write`, `Actions: Read and write`, `Metadata: Read`
- 브라우저 `localStorage`에 보관, 화면에서 언제든 삭제 가능
- 만료일 90일 권장 → 만료 시 화면 상단에 재발급 안내 배너

> 공용 PC에서는 사용하지 않습니다. 토큰은 저장소 1개에만 유효하므로
> 유출 시 피해 범위는 이 저장소로 한정됩니다.

---

## 3. 화면 명세

### 3.1 레이아웃

```
┌───────────────────────────────────────────────────────────┐
│ 📊 StocksInfo          2026-08-03 07:30 기준   [🔄 지금 갱신]│
│                                          [브리핑] [설정]    │
├───────────────────────────────────────────────────────────┤
│ ⚠️ 수집 실패 1건: 000660.KS (rate limit)          ← 있을 때만│
├───────────────────────────────────────────────────────────┤
│                                                            │
│  ① 오늘 볼 순서                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 1  NVDA   엔비디아                          점수 7.5  │ │
│  │    🔴 200일선 -8% 이탈 (6개월 만)                     │ │
│  │    📰 관련 기사 3건 · "데이터센터 수요 둔화 우려"      │ │
│  │    [▾ 자세히]                                         │ │
│  ├──────────────────────────────────────────────────────┤ │
│  │ 2  005930 삼성전자                          점수 4.0  │ │
│  │    🟡 실적발표 D-3 · 목표주가 주간 -4.2%              │ │
│  │    📰 관련 기사 1건                                   │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ② 전체 포지션                          [정렬: 52주 위치 ▾]│
│  ┌────────┬──────┬────────┬───────┬──────┬──────┬───────┐│
│  │ 종목   │ 종가 │ 52주 % │200일선│ 3M   │ 6M   │ vs지수││
│  │ NVDA   │ 812  │  22%   │ -8.1% │ -14% │ -22% │ -19%p ││
│  │ AAPL   │ 241  │  88%   │+14.2% │  +6% │ +11% │  +2%p ││
│  │ 005930 │ 71K  │  41%   │ -2.9% │  -3% │  +4% │  -1%p ││
│  └────────┴──────┴────────┴───────┴──────┴──────┴───────┘│
│                                                            │
│  ③ 오늘 기사에서 뜬 종목 (관심종목 밖)          [ⓘ 주의]   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ AMD   기사 4건 · NVDA와 동일 섹터                     │ │
│  │       "MI400 양산 일정 앞당겨" 외 3건                 │ │
│  │       PER 42배 · 52주 76% 지점      [+ 관심종목 추가] │ │
│  └──────────────────────────────────────────────────────┘ │
│  ⓘ 기사 빈도는 중장기 가치와 상관이 낮습니다. 후보일 뿐입니다.│
│                                                            │
│  ④ 이번 주 일정                                            │
│     NVDA 실적(수) · CPI(목) · AAPL 배당락(금)              │
│                                                            │
│  히스토리 축적 12일차 · PER 밴드 활성화까지 8일             │
└───────────────────────────────────────────────────────────┘
```

### 3.2 설정 탭

```
┌───────────────────────────────────────────────────────────┐
│  종목 설정                                    [+ 종목 추가] │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ NVDA   엔비디아                    프로필 [핵심보유 ▾]│ │
│  │        메모: 장기 보유, 실적 중심으로 관찰            │ │
│  │        ▾ 이 종목만 다르게                             │ │
│  │          ☑ 200일선 교차   ☑ 실적 임박                │ │
│  │          ☑ PER 밴드      ☐ 52주 신고저               │ │
│  │          ☑ 거래량 급증  → 임계값 [3.0]배             │ │
│  │                                            [삭제]     │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  프로필                                                     │
│   핵심보유  실적·밸류에이션 중심, 가격 노이즈 무시          │
│   관찰중    가격 움직임 포함 전부                           │
│   장기적립  분기 1회만 알림                                 │
│                                       [프로필 편집]         │
│                                                            │
│  이메일 구성                                                │
│   포함 블록  ☑ 오늘 볼 순서  ☑ 전체 포지션                 │
│             ☑ 이번 주 일정   ☐ 신규 발굴                   │
│   신호 0건인 날   ○ 발송 안 함  ● 한 줄로 발송             │
│   발송 시각      [07:30] KST                               │
│   수신자         won7seo@gmail.com          [+ 추가]        │
│                                                            │
│                              [저장 (GitHub에 커밋)]         │
└───────────────────────────────────────────────────────────┘
```

**저장 동작:** 버튼 클릭 → `config/watchlist.json`, `config/report.json`을
GitHub Contents API로 커밋 → 성공 시 "저장됨 · 내일 아침부터 반영" 토스트.
"지금 반영해서 보기"를 누르면 이어서 워크플로를 트리거합니다.

---

## 4. 설정 스키마

### 4.1 `config/watchlist.json`

기존 `{"us": [...], "kr": [...]}` 를 대체합니다. **마이그레이션 스크립트 필요.**

```json
{
  "version": 2,
  "profiles": {
    "core_holding": {
      "label": "핵심보유",
      "signals": ["ma200_cross", "earnings_soon", "valuation_band", "target_price_change"],
      "thresholds": { "volume_spike_ratio": 3.0, "earnings_lookahead_days": 7 }
    },
    "watching": {
      "label": "관찰중",
      "signals": ["ma200_cross", "week52_high", "week52_low", "volume_spike",
                  "earnings_soon", "valuation_band", "target_price_change"],
      "thresholds": { "volume_spike_ratio": 2.0, "earnings_lookahead_days": 7 }
    },
    "accumulating": {
      "label": "장기적립",
      "signals": ["earnings_soon", "valuation_band"],
      "thresholds": { "earnings_lookahead_days": 3 }
    }
  },
  "symbols": [
    {
      "symbol": "NVDA",
      "name": "엔비디아",
      "market": "us",
      "profile": "core_holding",
      "memo": "장기 보유, 실적 중심",
      "overrides": { "thresholds": { "volume_spike_ratio": 3.5 } }
    },
    {
      "symbol": "005930.KS",
      "name": "삼성전자",
      "market": "kr",
      "profile": "accumulating",
      "memo": ""
    }
  ]
}
```

**해석 규칙:** `프로필 값` ← `symbol.overrides`로 얕은 병합(shallow merge).
`signals`는 배열 전체 교체, `thresholds`는 키 단위 병합.

### 4.2 `config/report.json`

```json
{
  "version": 1,
  "email": {
    "blocks": ["focus", "positions", "calendar"],
    "send_when_no_signal": "one_line",
    "send_time_kst": "07:30",
    "recipients": ["won7seo@gmail.com"]
  },
  "discovery": {
    "enabled": true,
    "max_candidates": 3,
    "min_article_mentions": 2,
    "min_market_cap_usd": 1000000000
  },
  "focus": {
    "severity_weight": { "red": 3.0, "yellow": 1.0 },
    "news_weight": 0.5,
    "event_bonus": { "earnings_d3": 2.0, "ex_dividend_d2": 1.0 }
  }
}
```

`send_when_no_signal`: `"skip"` | `"one_line"` | `"full"`

---

## 5. 데이터 계약 — `data/latest.json`

대시보드와 파이프라인 사이의 **유일한 인터페이스**입니다.
필드 추가는 자유, 제거·의미변경은 `schema_version` 증가.

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-03T07:30:12+09:00",
  "market_date": "2026-08-02",
  "trigger": "schedule",

  "status": {
    "ok": false,
    "failed_symbols": [{ "symbol": "000660.KS", "reason": "rate limit (429)" }],
    "collector_errors": ["news/Investing.com KR: timeout"]
  },

  "history_status": { "days_collected": 12, "per_band_ready_in_days": 8 },

  "focus": [
    {
      "symbol": "NVDA", "name": "엔비디아", "rank": 1, "score": 7.5,
      "score_breakdown": { "severity": 3.0, "news": 1.5, "event": 3.0 },
      "signals": [
        { "type": "ma200_cross", "severity": "red",
          "message": "200일선 -8% 이탈 (6개월 만)" }
      ],
      "news": [
        { "title": "...", "url": "...", "source": "Yahoo Finance",
          "published": "2026-08-02T18:40:00Z", "relevance": "high" }
      ],
      "interpretation": "LLM이 생성한 2~3문장 해설"
    }
  ],

  "positions": [
    {
      "symbol": "NVDA", "name": "엔비디아", "profile": "core_holding",
      "last_close": 812.4, "change_pct": -1.9,
      "week52_pct": 22.0, "pct_vs_ma200": -8.1,
      "drawdown_from_high_pct": -31.2,
      "return_3m_pct": -14.0, "return_6m_pct": -22.0, "return_12m_pct": 8.0,
      "relative_strength_6m_pct": -19.0,
      "trailing_pe": 38.2, "next_earnings_date": "2026-08-05"
    }
  ],

  "discovery": [
    {
      "symbol": "AMD", "name": "AMD",
      "article_count": 4,
      "why": "관심종목 NVDA와 동일 섹터 · 당일 기사 4건 언급",
      "headlines": [{ "title": "...", "url": "..." }],
      "basic": { "trailing_pe": 42.1, "week52_pct": 76.0, "market_cap_usd": 2.6e11 }
    }
  ],

  "calendar": [
    { "date": "2026-08-05", "weekday": "수", "label": "NVDA 실적", "kind": "earnings" }
  ]
}
```

> `positions`는 **신호가 없는 종목도 전부 포함**합니다.
> `REVIEW.md` 6번(축 A를 계산만 하고 안 쓰는 문제)이 여기서 해소됩니다.

---

## 6. 추천 로직

### 6.1 영역 ① — 내 종목 우선순위 (focus)

```
focus_score(종목) =
    Σ severity_weight[신호.severity]              # red 3.0 / yellow 1.0
  + min(관련기사수, 3) × news_weight              # 최대 1.5
  + event_bonus                                   # 실적 D-3 이내 +2.0
                                                  # 배당락 D-2 이내 +1.0
```

- 점수 0점(신호·기사·이벤트 전무)인 종목은 ①에 **표시하지 않습니다**
- `score_breakdown`을 함께 저장해 **왜 1위인지 화면에서 설명 가능**하게 합니다
- 계산은 전부 Python. LLM은 순위에 관여하지 않습니다

**"관련 기사" 판정:**
1. `yfinance Ticker.news` (종목 직결, 신뢰도 높음) — 기본
2. RSS 기사 제목에 종목명/티커 문자열 포함 — 보조
3. 당일(24시간 이내) 발행분만

### 6.2 영역 ② — 신규 발굴 (discovery)

```
1. 당일 기사 제목 수집        RSS 3개 피드 + 관심종목 뉴스 → 제목 20~30개
2. LLM 1회 배치 호출          "다음 제목에서 언급된 상장사와 티커를 추출.
                              이미 보유 중인 [관심종목]은 제외."
3. 필터                       · 언급 min_article_mentions(기본 2)회 이상
                              · 시총 min_market_cap_usd 이상 (잡주 배제)
                              · yfinance로 티커 유효성 검증 (환각 방지)
4. 정렬 후 상위 max_candidates(기본 3)개
5. 각 후보에 근거 첨부        기사 원문 링크 + PER + 52주 위치
```

**환각 방지가 핵심입니다.** LLM이 뱉은 티커는 **반드시 yfinance로 존재를 확인**하고,
조회에 실패하면 후보에서 제외합니다. 회사명만 맞고 티커가 틀리는 경우가 흔합니다.

**화면 경고 문구 (필수):**
> ⓘ 기사 빈도는 중장기 가치와 상관이 낮습니다. 매수 추천이 아니라 후보 제시입니다.

이 경고를 빼면 이 기능은 **오히려 해롭습니다.** 중장기 투자자에게
"오늘 뉴스에 많이 나온 종목"은 대부분 노이즈이고, 종종 이미 급등한 뒤입니다.

**LLM 비용:** 하루 1~2회 추가 호출. 무료 티어로 충분합니다.
`discovery.enabled: false`로 끌 수 있어야 합니다.

---

## 7. 파이프라인 변경 사항

| 파일 | 변경 |
|---|---|
| `store.py` | v2 스키마 로더 + v1→v2 마이그레이션, 프로필 병합 함수 |
| `signals.py` | `evaluate(...)`에 종목별 설정 주입. 프로필에 없는 신호 타입은 생성 안 함 |
| `recommend.py` **(신규)** | focus 스코어링 + discovery 후보 생성 |
| `collectors/news.py` | **결과를 실제로 사용** (현재 버려짐 — `REVIEW.md` 1번) |
| `publish.py` **(신규)** | `data/latest.json` 직렬화 및 커밋 |
| `report.py` | `config/report.json`의 `blocks` 순서대로 이메일 조립 |
| `main.py` | `collect → signals → recommend → publish → email` |
| `web/` | **삭제 또는 로컬 전용으로 격리** (정적 대시보드가 대체) |
| 워크플로 | `workflow_dispatch`에 `trigger` 입력 추가, `data/` 커밋 |

### 선행 조건 (`REVIEW.md`에서 넘어온 것)

이 대시보드는 아래 3개가 먼저 고쳐져야 제대로 동작합니다.

1. **🔴 2번 수집 실패 가시화** → `status.failed_symbols`가 이 명세의 핵심 필드
2. **🔴 1번 뉴스 파이프라인 연결** → discovery와 focus 기사 점수의 유일한 재료
3. **🟡 8번 종목명** → `config/watchlist.json`의 `name` 필드로 자연 해결

---

## 8. 구현 순서

| 단계 | 내용 | 산출물 | 예상 |
|---|---|---|---|
| **0** | 실제 1회 실행 검증 (`REVIEW.md` 최우선) | 실제 응답 샘플 | 0.5일 |
| **1** | v2 스키마 + 마이그레이션 + 프로필 병합 | `store.py` | 0.5일 |
| **2** | `signals.py`가 종목별 설정 반영 | 신호 필터링 | 0.5일 |
| **3** | `recommend.py` focus 스코어링 | `focus[]` | 0.5일 |
| **4** | `publish.py` + `data/latest.json` 커밋 | 데이터 계약 | 0.5일 |
| **5** | 정적 대시보드 — **읽기 전용** | 브리핑 탭 | 1일 |
| **6** | 편집 기능 (Contents API 커밋) | 설정 탭 | 1일 |
| **7** | 갱신 버튼 (workflow_dispatch + 폴링) | 🔄 | 0.5일 |
| **8** | discovery (뉴스 → 후보) | 영역 ③ | 1일 |
| **9** | `report.json` 기반 이메일 재조립 | 블록 구성 | 0.5일 |

> **5단계까지가 최소 동작 제품(MVP)입니다.** 여기까지만 해도
> "축 A를 계산만 하고 안 쓰는" 문제가 해소되어 체감이 크게 달라집니다.
> 6~7단계(편집·갱신)는 그 다음, discovery(8)는 가장 마지막입니다.

---

## 9. 비기능 요구사항

| 항목 | 기준 |
|---|---|
| 첫 화면 로딩 | 2초 이내 (JSON 1회 fetch) |
| 갱신 버튼 완료 | 2~4분 (Actions 실행 시간) — **진행 상태를 반드시 표시** |
| 모바일 | 세로 화면 우선. 표는 가로 스크롤 대신 카드로 접기 |
| 오프라인/토큰 없음 | 빈 화면 대신 안내 문구 |
| 의존성 | CDN Tailwind만. 빌드 도구 없음 |
| 브라우저 저장 | 토큰(localStorage), 정렬·필터 선택(localStorage) |

---

## 10. 테스트 계획

**파이프라인 (pytest)**
- v1→v2 마이그레이션 왕복
- 프로필 병합: override가 threshold만 덮고 signals는 교체하는지
- 프로필에서 제외한 신호 타입이 실제로 생성되지 않는지
- focus 스코어 경계값 (0점 종목 제외, 동점 시 정렬 안정성)
- discovery: LLM이 없는 티커를 뱉었을 때 **후보에서 제외되는지** ★
- `latest.json` 스키마 검증 (필수 키 존재, 타입)

**대시보드 (수동 체크리스트)**
- 토큰 없이 접속 → 데이터 노출 0 확인
- 설정 저장 → GitHub 커밋 확인 → 다음 실행에 반영 확인
- 갱신 버튼 → Actions 실행 → 데이터 갱신 확인
- 수집 실패 시 ⚠️ 배너 노출 확인
- 모바일 실기기 확인

---

## 11. 열린 질문

1. **호스팅 최종 결정** (§2.2) — GitHub Pages(A) / 분리(B) / Cloudflare(C)
2. `discovery`의 한국 종목 처리 — 한글 회사명 → 티커 매핑 테이블 필요.
   KRX 상장사 목록을 받아 저장할지, 미국 종목만 발굴할지
3. 보유수량·평단가를 넣을지 — 넣으면 수익률 표시가 가능해지지만 §2.2 프라이버시 등급이 올라감
4. 히스토리 저장 형식 — SQLite 바이너리 유지 vs CSV 전환 (`REVIEW.md` 참고)
