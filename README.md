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

## 이후 진행

산출물 B부터 Jira API 데이터 적재 및 DB 설계를 진행합니다.