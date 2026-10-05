# 산출물 A — 데이터 진단과 기준 정하기

## A-1. 데이터를 그냥 더하면 틀리는 지점

| 항목 | 발견 내용과 예시 | 왜 문제인가 | 처리 방법 | 부작용 / 한계 |
|---|---|---|---|---|
| Worklog 단위 혼재 | `jira_worklog.csv`의 `unit`에 `h`, `d`가 함께 존재. `HRG-1013`은 `8h, 8h, 1d, 6h` 기록 | 숫자만 더하면 `23`이 되어 실제 작업시간과 다름 | 계산 전에 공통 시간 단위로 변환. A-2 기준으로 `1d=8h` 적용 | 조직의 1일 기준 근무시간이 바뀌면 변환 규칙도 함께 변경 필요 |
| 복수 Fix Version | `HRG-1031`: `v1.8,v1.9` | 양쪽 Version에 같은 Worklog를 합산하면 중복 집계됨 | Jira 변경 이력이 있으면 실제 귀속을 확인. 현재 CSV 분석에서는 복수 Version Issue를 자동 집계에서 제외 | 실제로 두 Version에 걸쳐 작업한 경우 Worklog 분할 기준이 추가로 필요 |
| Worklog 결측 | `HRG-1012`는 Issue는 존재하지만 Worklog가 없음 | Worklog 합계는 실제 총투입량이 아니라 **기록된 MD**만 나타냄 | A-3에서 결측률을 별도 계산하고 Actual과 Estimate를 구분 | 결측값을 추정하지 않으면 전체 Actual MD를 완전히 복원할 수 없음 |

---

## A-2. 정의가 없는 항목을 직접 정하기

### 1. 1 MD의 정의

**1 MD = 사람 1명이 실제로 투입한 8시간**으로 정의한다.

여러 사람이 같은 Issue에 작업하면 각 Worklog를 사람별로 MD로 환산한 뒤 합산한다.

예: 8시간 + 4시간 작업 → `1 MD + 0.5 MD = 1.5 MD`

### 2. Issue를 어느 공정에 귀속시킬 것인가

Actual MD는 `assignee`가 아니라 **Worklog 작성자의 role**로 공정에 귀속한다.

| `people.role` | 공정 |
|---|---|
| planner | PLAN |
| server / client | DEV |
| art | ART |

`assignee`는 현재 책임자일 뿐 실제 참여 직군 전체를 나타내지 못하므로 Actual MD 산정에는 Worklog author를 우선한다.

작성자를 `people.csv`와 매핑할 수 없으면 임의로 포함하지 않고 `UNCLASSIFIED`로 관리한다.

### 3. QA MD는 측정할 수 있는가

현재 데이터에는 QA 담당자·QA role·QA Worklog가 없어 **실제 QA MD는 직접 측정할 수 없다.**

따라서 `QA 반려` Bug Issue의 Worklog 합계를 QA 관련 **개발 수정 공수 proxy**로 사용한다.  
이는 실제 테스트 MD가 아니므로 baseline의 실제 QA MD와 동일하게 취급하지 않는다.

### 4. 리소스 MD 범위

ART MD에는 내부 아트와 외주 아트 Worklog를 모두 포함한다.

`art_outsource01`, `art_outsource02`는 각각 별도 계정이므로 추가 정보가 없는 현재 과제에서는 **계정 1개를 작업자 1명**으로 간주하고, 동일하게 `8h = 1MD`로 계산한다.

### 5. Version 종료 시점

Version 종료는 **Jira Version Close일**로 정의한다.

실제 배포 이후에도 Worklog 수정, Reopen, 상태/Fix Version 변경이 가능하기 때문에 배포일보다 Close일이 실적 확정 기준에 적합하다.

예:

| Version | 실제 배포일 | Jira Close일 |
|---|---|---|
| v1.8 | 2025-09-15 | 2025-10-10 |
| v2.0 | 2026-01-19 | 2026-02-06 |

운영 흐름은 다음과 같다.

`실제 배포 → Jira 정리 → Version Close → Actual MD 확정 → baseline 갱신`

단점은 Close가 늦으면 baseline 갱신도 늦어진다는 점이다.

### 6. S / M / L 객관적 기준

Size는 작업 전에 확인 가능한 `orig_estimate`를 사용한다. 기존 `size_label`은 주관적 입력이므로 새 Size 경계 계산에는 사용하지 않는다.

공정별 작업량 차이를 반영하기 위해 `Category × Process`별로 `orig_estimate` 분포를 나누고, 1/3·2/3 지점을 8시간 단위로 정리하였다.

#### PLAN / DEV 기준

| Category | 공정 | S | M | L |
|---|---|---|---|---|
| CONTENT | PLAN | 32h 이하 | 32h 초과 ~ 56h 이하 | 56h 초과 |
| CONTENT | DEV | 32h 이하 | 32h 초과 ~ 88h 이하 | 88h 초과 |
| SYSTEM | PLAN | 72h 이하 | 72h 초과 ~ 136h 이하 | 136h 초과 |
| SYSTEM | DEV | 72h 이하 | 72h 초과 ~ 192h 이하 | 192h 초과 |

#### ART / QA 초기 기준

ART와 QA는 현재 데이터만으로 PLAN / DEV와 같은 방식의 경계를 충분히 만들기 어려워 `md_baseline_v0.csv`의 Size별 대표 MD 중간값을 **초기 임시 기준**으로 사용한다.

| Category | Process | S | M | L |
|---|---|---:|---:|---:|
| SYSTEM | ART | 4MD 이하 | 4MD 초과 ~ 9MD 이하 | 9MD 초과 |
| CONTENT | ART | 7MD 이하 | 7MD 초과 ~ 18MD 이하 | 18MD 초과 |
| SYSTEM | QA | 2MD 이하 | 2MD 초과 ~ 5MD 이하 | 5MD 초과 |
| CONTENT | QA | 2MD 이하 | 2MD 초과 ~ 3MD 이하 | 3MD 초과 |

향후 ART 예상 공수와 실제 QA Worklog가 충분히 쌓이면 PLAN / DEV와 같은 방식으로 재산정한다.

### 7. 안정적인 기획 일정

기존 `review_days`, `art_lead_days`를 그대로 쓰지 않고, 기준일 현재 종료된 v1.3~v1.9 데이터를 이용해 검수/인계 기간과 일정 Buffer를 다시 정의한다.

#### 기획 완료 후 개발 착수까지

별도 검수 기간 필드가 없으므로

`기획 Issue resolved → 관련 DEV Issue 최초 started`

사이의 영업일을 검수·인계 기간 proxy로 사용한다.

| Size | 분석 건수 | 중앙값 | 75% 지점 | 적용값 |
|---|---:|---:|---:|---:|
| S | 16 | 2일 | 2.25일 | 3영업일 |
| M | 16 | 3일 | 4일 | 4영업일 |
| L | 12 | 5일 | 6일 | 6영업일 |

`resolved → started`가 순수 검수만을 의미하지는 않으므로 proxy라는 한계가 있다.

#### 일정 Buffer

기획 예상기간은 다음과 같이 계산한다.

`예상 작업기간 = orig_estimate / (8시간 × 담당자 availability)`

실제 `started → resolved` 영업일과 비교한 결과:

- 분석 대상: 44건
- 예상보다 오래 걸린 Issue: 27건
- 실제/예상 기간 비율 중앙값: 약 1.04
- 75% 지점: 약 1.24

따라서 초기 일정 Buffer를 **25%**로 둔다.

최종적으로 안정적인 기획 일정은 다음 두 조건을 만족해야 한다.

1. 예상 기획기간에 25% Buffer를 적용
2. 기획 완료 후 개발 착수 전 S/M/L별 3/4/6영업일 확보

날짜 계산에는 주말, 공휴일, 담당자 PTO와 availability를 반영한다.

### 8. TF 제안 기준

TF는 마감일까지 필요한 작업량이 현재 인력의 가용량을 초과할 때 검토한다.

`부족 공수 = 남은 필요 MD - 마감일까지 가용 MD`

TF 제안 기준은 **해당 공정 평균 인력 1명의 1주 가용 공수**로 정의한다.

`TF 기준 = 공정별 평균 availability × 5영업일`

| 공정 | 평균 availability | TF 제안 기준 |
|---|---:|---:|
| PLAN | 0.80 | 부족 공수 4.0 MD 이상 |
| DEV | 약 0.88 | 부족 공수 약 4.4 MD 이상 |
| ART | 0.95 | 부족 공수 약 4.8 MD 이상 |

이는 평균 인력 1명을 약 1주 추가 투입해야 하는 수준부터 별도 인력 대안을 검토한다는 운영 기준이다.

QA는 현재 인력 availability가 없어 동일 기준을 계산하지 않는다.

---

## A-3. 기록이 빠진 데이터 다루기

기준일 현재 종료된 v1.3~v1.9의 Done / Won't Do Issue를 대상으로 Worklog 결측을 계산하였다.

### 결측 현황

총 251개 Issue 중:

- Worklog 있음: 160건
- Worklog 없음: 91건
- **결측률: 36.3%**

공정별:

| 공정 | 전체 Issue | Worklog 없음 | 결측률 |
|---|---:|---:|---:|
| PLAN | 45 | 26 | 57.8% |
| DEV | 141 | 53 | 37.6% |
| ART | 65 | 12 | 18.5% |

Issue Type별:

| Type | 전체 Issue | Worklog 없음 | 결측률 |
|---|---:|---:|---:|
| Bug | 30 | 15 | 50.0% |
| Story | 169 | 72 | 42.6% |
| Task | 52 | 4 | 7.7% |

결측률이 공정·유형별로 크게 다르므로 결측이 무작위라고 보기 어렵다.

### 전체 Actual MD 추정 여부

전체 기록률 63.7%를 이용해

`recorded MD / 0.637`

처럼 일괄 보정하지 않는다.

이 방식은 기록된 Issue가 결측 Issue를 대표한다는 전제가 필요한데, 실제 결측률이 PLAN 57.8%, ART 18.5%처럼 크게 달라 편향 위험이 있다.

### 결측 처리

91개 결측 Issue 중 71건(약 78%)에는 `orig_estimate`가 있다. 다만 이는 실제 공수가 아니라 최초 예상값이므로 Actual로 합산하지 않는다.

- Worklog 있음 → `observed_actual_md`
- Worklog 없음 + `orig_estimate` 있음 → Actual은 `UNKNOWN`, Estimate만 참고
- 둘 다 없음 → Actual / Estimate 모두 `UNKNOWN`

버전별 실적에는 **관측 Actual MD와 Worklog 기록률을 함께 표시**한다.

### 이 판단이 틀렸을 경우

결측이 실제로 무작위라면 본 방식은 활용 가능한 실적을 보수적으로 사용해 baseline 개선 속도가 느려질 수 있다.

반대로 편향된 결측을 강제로 보정하면 잘못된 Actual MD가 baseline에 반영되어 이후 공수, 기획 착수일, TF 판단까지 왜곡될 수 있다.

따라서 전체값을 억지로 복원하기보다 관측값과 추정값을 분리한다.

---

## A-4. 시간에 따른 변화 읽기

복수 Fix Version Issue는 귀속이 불명확하므로 제외하고 v1.3~v2.0의 배포 지연과 Worklog 기록률을 비교하였다.

| Version | 계획 대비 실제 배포 지연 | Worklog 기록률 |
|---|---:|---:|
| v1.3 | +6일 | 67.7% |
| v1.4 | 0일 | 75.7% |
| v1.5 | +15일 | 70.0% |
| v1.6 | +5일 | 52.8% |
| v1.7 | +8일 | 73.3% |
| v1.8 | +11일 | 55.3% |
| v1.9 | +11일 | 57.1% |
| v2.0 | +11일 | 53.4% |

### 1. 최근 배포 지연이 반복됨

v1.8~v2.0은 **3개 Version 연속 +11일 지연**되었다. 일회성 예외보다 반복되는 일정 문제로 보는 것이 타당하며, 고정 baseline보다 실적을 다음 계획에 되돌리는 구조가 필요하다.

### 2. 최근 Worklog 기록률이 낮음

v1.8~v2.0의 Worklog 기록률은 53~57% 수준이다.

특히 v1.8 recorded MD는 72.9 MD로 낮지만 Worklog 기록률도 55.3%이므로, 이를 실제 작업량 감소로 바로 해석할 수 없다.

### 3. 작업 규모는 커졌지만 기록 품질은 개선되지 않음

최근 단일 Version Issue 수는:

- v1.8: 38건
- v1.9: 49건
- v2.0: 58건

으로 증가했지만 Worklog 기록률은 50%대에 머물렀다.

### Baseline 운영 반영

- 마지막 1개 Version의 recorded MD만으로 baseline을 자동 갱신하지 않는다.
- Actual MD와 Worklog 기록률을 함께 관리한다.
- 여러 종료 Version 실적을 함께 사용해 특정 Version의 이상치 영향을 줄인다.
- v2.0은 기준일 현재 Jira Close 전이므로 추세 확인용 잠정 데이터로만 사용하고, Close 이후 최종 실적으로 확정한다.
