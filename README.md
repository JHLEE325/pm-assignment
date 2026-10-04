# 호랑 PM파트 사전 과제

업데이트 일정 역산 자동화 시스템 설계 과제 저장소입니다.

과제의 기준일은 `2026-01-26`입니다.

## 진행 상태

- 산출물 A: 완료
- 산출물 B: 진행 예정
- 산출물 C: 진행 예정
- 산출물 D: 진행 예정

## 폴더 구조

```text
horang-pm-assignment/
├── README.md
├── requirements.txt
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
│   └── A_data_diagnosis.md
├── scripts/
│   ├── a_profile.py
│   ├── a2_schedule.py
│   ├── a2_size.py
│   ├── a3_worklog.py
│   └── a4_version.py
├── sql/
├── dashboard/
└── output/
    └── a_analysis/
```

`data/source/`에는 과제에서 제공된 원본 데이터를 보관합니다.

## 실행 환경

Python 3 기준입니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

## 산출물 A

최종 분석 내용과 판단 근거:

```text
docs/A_data_diagnosis.md
```

### A-1. 데이터 기본 진단

사용 스크립트:

```bash
python scripts/a_profile.py
```

원본 데이터의 구조와 주요 결측 상태를 확인합니다.

### A-2. S / M / L 기준 분석

사용 스크립트:

```bash
python scripts/a2_size.py
```

`orig_estimate`를 이용해 공정 및 카테고리별 규모 기준을 분석합니다.

### A-2. 안정적인 기획 일정 분석

사용 스크립트:

```bash
python scripts/a2_schedule.py
```

기획 완료 후 개발 착수까지의 기간과 일정 Buffer 산정을 위한 데이터를 분석합니다.

### A-3. Worklog 결측 분석

사용 스크립트:

```bash
python scripts/a3_worklog.py
```

전체, 공정별, 이슈 유형별 Worklog 결측률을 계산합니다.

### A-4. Version별 추세 분석

사용 스크립트:

```bash
python scripts/a4_version.py
```

v1.3 ~ v2.0의 이슈 수, Worklog 기록률, recorded MD, 배포 지연 등을 비교합니다.

## 재현 순서

저장소 루트에서 아래 순서로 실행합니다.

```bash
python scripts/a_profile.py
python scripts/a2_size.py
python scripts/a2_schedule.py
python scripts/a3_worklog.py
python scripts/a4_version.py
```

세부 분석 결과와 판단 근거는 `docs/A_data_diagnosis.md`를 참고합니다.

## 산출물 B

산출물 B의 최종 설계 문서는 다음 파일에 정리되어 있습니다.

`docs/B_jira_db_design.md`

### 관련 파일

```text
docs/
└── B_jira_db_design.md

scripts/
└── b7_load_sqlite.py

sql/
├── schema.sql
├── b7_version_md.sql
└── b7_concurrent_issues.sql

output/
└── horang_pm.db
```

### SQLite DB 생성 및 데이터 적재

저장소 루트에서 다음 명령어를 실행합니다.

```bash
python scripts/b7_load_sqlite.py
```

실행하면 B-6에서 정의한 테이블 구조를 생성하고,
제공된 CSV 데이터를 적재한 SQLite DB가 생성됩니다.

```text
output/horang_pm.db
```

적재 과정에서 다음 데이터를 변환합니다.

- Worklog의 `h`, `d` 단위를 초 단위로 통일
- 복수 Fix Version을 Issue-Version 관계로 분리
- 복수 Fix Version 이슈는 Version별 MD 중복 집계를 방지하기 위해 집계 대상에서 제외
- CSV에 Worklog ID가 없으므로 테스트용 고유 ID 생성
- 제공 CSV의 `started`, `resolved` 값을 정제된 작업기간 값으로 사용

### 핵심 조회 SQL

Version별 Category × Size Actual MD:

```text
sql/b7_version_md.sql
```

실행:

```bash
sqlite3 -header -column output/horang_pm.db < sql/b7_version_md.sql
```

특정 기간 담당자의 동시 담당 Issue 수:

```text
sql/b7_concurrent_issues.sql
```

SQLite 실행:

```bash
sqlite3 output/horang_pm.db
```

SQLite 콘솔에서 조회 조건을 설정한 뒤 실행합니다.

```text
.headers on
.mode column

.parameter init
.parameter set :person_key "'dev_oh'"
.parameter set :from_date "'2025-10-13'"
.parameter set :to_date "'2025-10-23'"

.read sql/b7_concurrent_issues.sql
```

종료:

```text
.quit
```

### 산출물 B 재현 순서

```bash
python scripts/b7_load_sqlite.py
sqlite3 -header -column output/horang_pm.db < sql/b7_version_md.sql
```

동시 담당 Issue 조회는 위의 SQLite parameter 설정 방법을 사용합니다.

세부 설계와 판단 근거는 `docs/B_jira_db_design.md`를 참고합니다.