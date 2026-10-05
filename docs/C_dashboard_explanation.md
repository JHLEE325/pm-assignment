# 산출물 C — 기획 착수일 역산 상황판 설명

대상 파일: `docs/C_dashboard.html`

## C-1. 기획 착수일 역산

화면은 `업데이트일 / 콘텐츠 / 담당 기획자`를 입력받아 다음 순서로 역산한다.

`업데이트 ← QA/코드프리즈 ← 개발 ← 리소스 선행 ← 리소스 제작 ← 검수/인계 ← 기획`

계산에는 다음 기준을 적용한다.

- 주말·공휴일·담당자 PTO 제외
- `person.availability` 반영
- 동시 담당 데이터가 부족하므로 목업에서는  
  `실효 가용률 = 기본 availability / (기존 동시 담당 건수 + 현재 대상 1건)`으로 계산
- 기획기간에 A-2의 **25% 일정 Buffer** 적용
- 검수/인계는 Size별 **S 3 / M 4 / L 6영업일**
- DEV/ART는 인력별 availability 합계에서 PTO를 차감해 일별 capacity 계산
- QA 인력 데이터가 없어 QA baseline MD를 일정 proxy로 사용
- `art_lead_days`는 별도 재산정 근거가 없어 v0 baseline 값을 임시 정책값으로 사용
- 기준일은 시스템 날짜가 아니라 `as_of = 2026-01-26`

기본 예시 `2026-03-12 / SYSTEM-L / pd_lee`에서는 availability 80%, 기존 동시 담당 1건을 반영해 실효 가용률을 40%로 계산하며, 기획 착수 필요일은 `2025-11-07`이다. 기준일 대비 **54영업일 초과** 상태다.

기존 목업의 FIXME는 위 계산 규칙을 적용하도록 수정했다.  
특히 PLAN/DEV만 보던 구조를 ART/QA까지 포함한 전체 역산 흐름으로 확장하고, 단순 날짜 차감 대신 영업일·PTO·가용률·동시 담당을 반영하며, 화면에 계산 근거와 `as_of`를 함께 표시하도록 변경했다.

## C-2. 일정 초과 시 대안

초과 상태에서는 동일 계산기를 다시 실행해 실제 선택 가능한 대안을 제시한다.

- **담당자 변경:** 다른 planner의 availability/PTO/동시 담당을 적용해 재계산
- **범위 축소:** 동일 Category의 더 작은 Size baseline으로 재계산
- **업데이트 연기:** 현재 범위/담당자를 유지할 수 있는 최소 업데이트일 탐색
- **기획 TF:** 추가 FTE를 넣어 재계산하되, 후속 단계 자체가 이미 늦은 경우 `기획 TF만으로 해결 불가` 표시

기본 예시에서는 `SYSTEM-L → SYSTEM-S`로 줄이면 착수 필요일이 `2026-02-06`으로 이동해 3/12 업데이트 유지가 가능하다. 범위와 담당자를 유지하면 최소 업데이트일은 `2026-05-28`이다.

## C-3. 화면용 데이터 형태와 계산 위치

기존 `/api/md_summary`의 `version / epic_key / total_timespent_hours / issue_count`만으로는 담당자 capacity, 단계별 일정, 위험도와 대안을 계산할 수 없다.

화면에는 최소 다음 형태의 응답이 필요하다.

```json
{
  "as_of": "2026-01-26",
  "input": {"release_date":"2026-03-12","content_id":"CLS","owner":"pd_lee"},
  "content": {"category":"SYSTEM","size":"L"},
  "baseline": {"plan_md":15,"dev_md":30,"art_md":12,"qa_md":6,"review_days":6,"art_lead_days":10},
  "owner_capacity": {"availability":0.8,"concurrent_issue_count":1,"effective_availability":0.4},
  "schedule": [
    {"stage":"PLAN","start":"2025-11-07","end":"2026-01-15"},
    {"stage":"DEV","start":"2026-02-23","end":"2026-03-03"},
    {"stage":"QA_FREEZE","start":"2026-03-04","end":"2026-03-11"}
  ],
  "risk": {"level":"danger","slack_business_days":-54},
  "alternatives": []
}
```

| 화면 값 | B-6 원천 | 계산 단계 |
|---|---|---|
| 업데이트일 | `version.planned_release_date` 또는 사용자 입력 | 화면 입력 + 서버 검증 |
| Category / Size | `issue.category_type`, `issue.size_class` | DB 조회 |
| 승인 baseline MD | Version 실적 + B-8 승인 결과 | 서버 배치 + 사람 승인 |
| availability | `person.availability` | DB 조회 |
| 휴일/PTO | `calendar_day` | DB 조회 |
| 동시 담당 건수 | `issue.assignee_person_key`, `started_at`, `resolved_at` | DB 쿼리 |
| DEV/ART capacity | `person` + `calendar_day` | 서버 계산 |
| 단계별 일정 | 위 값 전체 | 결정론적 서버 계산 |
| 위험도 / 대안 | schedule + baseline + capacity | 조건식 / 동일 엔진 재계산 |
| HTML 표시 | API 응답 | 화면 스크립트 |
| AI 호출 | 없음 | 사용하지 않음 |

일정·MD·대안 계산은 같은 입력에 같은 결과가 나와야 하므로 AI가 아니라 결정론적 로직으로 처리한다.  
`review_days`, `art_lead_days`, `as_of`처럼 B-6 원천 테이블에 직접 없는 값은 운영 정책 또는 요청 파라미터로 분리한다.
