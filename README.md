# 호랑 PM파트 사전 과제

업데이트 일정 역산 자동화 시스템 설계 과제 저장소입니다.

- 과제 기준일: `2026-01-26`
- 산출물 A~D 완료
- 제공 데이터는 `data/source/`에 원본 그대로 보관
- B-7 재현용 SQLite DB는 실행 시 생성되며 저장소에는 커밋하지 않음

## 폴더 구조

```text
pm-assignment/
├── README.md
├── requirements.txt
├── .gitignore
├── data/
│   └── source/
│       ├── 과제문서_호랑PM파트.html
│       ├── jira_issues.csv
│       ├── jira_worklog.csv
│       ├── jira_api_raw_sample.json
│       ├── md_baseline_v0.csv
│       ├── people.csv
│       ├── calendar.csv
│       └── dashboard_mockup.html
├── docs/
│   ├── A_data_diagnosis.md
│   ├── B_jira_db_design.md
│   ├── C_dashboard.html
│   ├── C_dashboard_explanation.md
│   ├── D_operation.md
│   └── images/
│       ├── b7_version_md.png
│       └── b7_concurrent_issues.png
├── scripts/
│   ├── a_profile.py
│   ├── a2_size.py
│   ├── a2_schedule.py
│   ├── a3_worklog.py
│   ├── a4_version.py
│   └── b7_load_sqlite.py
├── sql/
│   ├── schema.sql
│   ├── b7_version_md.sql
│   └── b7_concurrent_issues.sql
└── output/
    └── a_analysis/
        └── a2_size_thresholds.csv
```

`output/horang_pm.db`는 `scripts/b7_load_sqlite.py` 실행 시 생성됩니다.  
`.gitignore`의 `*.db` 규칙으로 저장소에는 포함하지 않습니다.

## 실행 환경

Python 3과 SQLite CLI가 필요합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

SQLite CLI 설치 여부 확인:

```bash
sqlite3 --version
```

모든 명령은 저장소 루트에서 실행합니다.

---

## 산출물 A — 데이터 진단과 기준 정하기

문서:

```text
docs/A_data_diagnosis.md
```

분석 재현:

```bash
python scripts/a_profile.py
python scripts/a2_size.py
python scripts/a2_schedule.py
python scripts/a3_worklog.py
python scripts/a4_version.py
```

주요 역할:

- `a_profile.py`: 제공 CSV 구조/결측/분포 확인
- `a2_size.py`: `orig_estimate` 기반 Category × Process Size 경계 분석
- `a2_schedule.py`: 기획 완료→개발 착수 간격과 일정 Buffer 분석
- `a3_worklog.py`: Worklog 결측률 분석
- `a4_version.py`: v1.3~v2.0 Version별 기록률/MD/배포 지연 분석

`a2_size.py` 실행 결과는 다음 파일로도 저장됩니다.

```text
output/a_analysis/a2_size_thresholds.csv
```

---

## 산출물 B — Jira → DB 설계 및 핵심 조회

설계 문서:

```text
docs/B_jira_db_design.md
```

DDL / 조회 SQL:

```text
sql/schema.sql
sql/b7_version_md.sql
sql/b7_concurrent_issues.sql
```

### 1. SQLite DB 생성 및 CSV 적재

```bash
python scripts/b7_load_sqlite.py
```

생성 파일:

```text
output/horang_pm.db
```

적재 과정에서 다음을 처리합니다.

- Worklog `h` / `d`를 초 단위로 통일 (`1d = 8h`)
- 복수 Fix Version을 Issue-Version 관계로 분리
- 귀속이 불명확한 복수 Version Issue는 Version별 MD 중복 방지를 위해 집계 제외
- CSV에 없는 Worklog ID는 재현 가능한 테스트용 ID 생성
- 기존 Jira `size_label`은 원본 보존
- A-2 기준 `Category × Process × orig_estimate`로 `size_class` 재계산
- Size를 계산할 수 없는 Issue는 `UNCLASSIFIED`로 유지

정상 적재 시 제공 데이터 기준으로 Issue 333건, Worklog 1,311건이 적재됩니다.

### 2. Version별 Category × Size Actual MD

```bash
sqlite3 -header -column output/horang_pm.db < sql/b7_version_md.sql
```

문서의 v1.9 예시 합계는 `164.0 MD`입니다.

### 3. 특정 기간 담당자의 동시 담당 Issue 수

SQLite 실행:

```bash
sqlite3 output/horang_pm.db
```

SQLite 콘솔:

```text
.headers on
.mode column

.parameter init
.parameter set :person_key "'dev_oh'"
.parameter set :from_date "'2025-10-13'"
.parameter set :to_date "'2025-10-23'"

.read sql/b7_concurrent_issues.sql
.quit
```

예시 조건에서 최대 동시 담당 Issue는 `7건`입니다.

실제 실행 화면은 다음 파일에 포함되어 있습니다.

```text
docs/images/b7_version_md.png
docs/images/b7_concurrent_issues.png
```

---

## 산출물 C — 기획 착수일 역산 상황판

HTML:

```text
docs/C_dashboard.html
```

설명 문서:

```text
docs/C_dashboard_explanation.md
```

별도 DB 연결 없이 제공 데이터와 A/B에서 정한 규칙을 정적 mock payload로 사용합니다.

간단히 로컬 서버를 실행한 뒤 브라우저에서 확인할 수 있습니다.

```bash
python -m http.server 8000
```

브라우저:

```text
http://localhost:8000/docs/C_dashboard.html
```

기본 입력:

```text
업데이트일: 2026-03-12
콘텐츠: 신규 클래스 추가 (SYSTEM / L)
담당 기획자: pd_lee
```

기본 예시 결과:

```text
기획 착수 필요일: 2025-11-07
기준일 대비: 54영업일 초과
실효 가용률: 40%
범위 축소 SYSTEM-L → SYSTEM-S 시 착수 필요일: 2026-02-06
범위/담당 유지 시 최소 업데이트일: 2026-05-28
```

화면 계산에는 주말, 공휴일, PTO, availability, 동시 담당 Issue 수를 반영합니다.

---

## 산출물 D — 운영 설계

문서:

```text
docs/D_operation.md
```

포함 내용:

- 파트 리더 / 담당 기획자 Slack 알림 문안
- 기계적 계산과 AI 사용 영역 구분
- 월 AI 사용량·비용 추정 및 비용 절감 방안
- AI 사용 기록과 잘못 판단한 지점 3건의 수정 과정

---

## 전체 재현 순서

```bash
# 1. Python 환경
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 산출물 A 분석
python scripts/a_profile.py
python scripts/a2_size.py
python scripts/a2_schedule.py
python scripts/a3_worklog.py
python scripts/a4_version.py

# 3. 산출물 B DB 생성
python scripts/b7_load_sqlite.py

# 4. 산출물 B 핵심 조회
sqlite3 -header -column output/horang_pm.db < sql/b7_version_md.sql

# 5. 산출물 C 확인
python -m http.server 8000
# http://localhost:8000/docs/C_dashboard.html
```

특정 기간 동시 담당 Issue 조회는 위 B 섹션의 SQLite parameter 예시를 사용합니다.

산출물 A/B의 판단 근거는 각 Markdown 문서에, C의 동작과 데이터 계약은 C 설명 문서에, 운영/AI 정책은 D 문서에 정리되어 있습니다.
