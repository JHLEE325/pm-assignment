# 산출물 B — Jira 데이터를 DB로 가져오는 방법 설계

### B-1. Jira API 원본에서 MD 계산을 막는 지점

A-2에서 Actual MD는 실제 Worklog를 기준으로 계산하고,
`8시간 = 1 MD`로 정의하였다.

또한 Worklog 작성자의 직군을 기준으로 PLAN / DEV / ART 공정을 구분하고,
Category × Size × 공정 단위로 실적을 집계하기로 하였다.

그러나 `jira_api_raw_sample.json`의 값을 가공 없이 그대로 DB에 넣으면
이 기준으로 MD를 바로 계산하기 어려운 지점이 있다.


#### 1. 시간 값의 단위와 표현이 통일되어 있지 않다

Jira 원본에는 시간과 관련된 값이 여러 형태로 존재한다.

예를 들어 HRG-1032에는 다음 값들이 있다.

- `originalEstimate = "30d"`
- `originalEstimateSeconds = 864000`
- `timeSpent = "18d 2h"`
- `timeSpentSeconds = 525600`
- Worklog의 `timeSpentSeconds`

즉 사람이 읽는 문자열과 초 단위 숫자가 함께 존재한다.

이 값을 그대로 사용하면 `"30d"`, `"18d 2h"`와 같은 문자열을
매번 해석해야 하고, A-2에서 정의한 `8시간 = 1 MD` 기준과도 바로 연결되지 않는다.

**처리 방법**

MD 계산에는 문자열이 아니라 초 단위 값을 기준으로 사용한다.

`1 MD = 8시간 = 28,800초`

따라서 Actual MD는 다음과 같이 계산한다.

`Actual MD = Worklog timeSpentSeconds 합계 / 28,800`

원본 문자열은 확인용으로 보존하되 계산에는 사용하지 않는다.


#### 2. Worklog가 Issue 내부의 중첩 배열로 들어 있다

실제 작업시간은 Issue 한 건에 하나의 숫자로 들어 있는 것이 아니라
`fields.worklog.worklogs[]` 안에 여러 건으로 존재한다.

각 Worklog에는 작성자, 작업 시각, 작업 시간이 각각 기록되어 있다. 

이 구조를 Issue 한 행에 그대로 저장하면
작성자별 작업시간을 합산하거나 공정별 MD를 계산하기 어렵다.

**처리 방법**

Issue와 Worklog를 분리하여 저장한다.

Worklog 한 건을 한 행으로 만들고 최소한 다음 값을 관리한다.

- issue_key
- worklog_id
- author_account_id
- started_at
- time_spent_seconds

Actual MD는 이 Worklog 테이블을 기준으로 계산한다.


#### 3. Worklog 작성자의 직군 정보가 없다

원본 Worklog의 작성자는 `author.accountId`로 제공된다.

하지만 A-2에서는 작성자의 직군을 이용하여 다음과 같이 공정을 구분하기로 했다.

- planner → PLAN
- server / client → DEV
- art → ART

Jira 원본의 `accountId`만으로는 해당 사람이 planner인지,
server인지, client인지, art인지 알 수 없다.

**처리 방법**

Jira `accountId`와 사람 정보를 연결할 수 있는 별도 매핑이 필요하다.

현재 제공된 `people.csv`에는 사람별 `role` 정보가 존재하므로
Jira 계정과 해당 정보를 연결해 Worklog의 공정을 결정한다. `people.csv`에는 planner, server, client, art 등의 role과 availability가 제공된다. 

실제 운영에서는 Jira `accountId ↔ 사내 인력 정보`의 연결 정보가 추가로 필요하다.


#### 4. Fix Version이 하나의 값이 아니라 배열이다

Jira 원본의 `fixVersions`는 단일 값이 아니라 배열이다.

HRG-1032에는 `v1.8`과 `v1.9`가 동시에 들어 있다. 

이 값을 그대로 저장하면 한 Issue의 Worklog를 어느 Version의 MD로 집계해야 하는지
명확하지 않으며, 두 Version에 동시에 합산하면 MD가 중복될 수 있다.

**처리 방법**

Issue와 Version의 관계를 분리해서 저장하고,
복수 Version이 존재하는 경우에는 A-1에서 정한 Version 귀속 규칙을 적용한다.

필요한 경우 Fix Version 변경 이력도 함께 사용하여
어느 Version에 귀속할지 판단한다.


#### 5. Category / Size가 의미가 드러나지 않는 Custom Field에 들어 있다

A-2의 기준표는 Category와 Size를 기준으로 MD를 구분한다.

하지만 Jira 원본에서는 이 값들이
`customfield_10031`, `customfield_10245`와 같이
이름만 보고 의미를 알 수 없는 Custom Field에 들어 있다.

예를 들어 HRG-1032에는

- `customfield_10031 = {"value": "L"}`
- `customfield_10245 = "시스템"`

형태의 값이 존재한다. 

반면 다른 Issue에서는 `customfield_10032 = "L"`처럼
다른 필드와 형태가 나타나기도 한다. 

따라서 Custom Field ID만 코드에 직접 적어두면
어떤 필드가 Size이고 Category인지 안정적으로 판단하기 어렵다.

**처리 방법**

Jira Field Metadata를 추가로 조회하여
각 Custom Field의 의미를 확인한 뒤,

- Size
- Category
- Story Point

등의 내부 표준 컬럼으로 변환한다.

원본에도 Field Metadata는 별도 `/rest/api/3/field`에서 조회해야 한다고 명시되어 있다. 


#### 6. Issue 단위 시간 값만으로는 공정별 Actual MD를 계산할 수 없다

HRG-1032에는 Issue 단위로

- `timeSpentSeconds`
- `aggregatetimespent`

값도 존재한다. 

하지만 A-2에서는 Worklog 작성자의 직군을 기준으로
PLAN / DEV / ART를 구분하기로 했다.

Issue 단위 총합만 사용하면 여러 직군이 같은 Issue에 작업했을 때
각 공정에 얼마의 MD가 투입되었는지 나눌 수 없다.

**처리 방법**

Actual MD의 원천은 Issue 단위 총합이 아니라
작성자 정보가 포함된 개별 Worklog로 통일한다.

Issue 단위 `timeSpentSeconds` 등은 검증 또는 참고용 값으로만 사용한다.


### MD 계산을 위해 추가로 필요한 정보

현재 Jira Issue 원본만으로 부족한 정보는 다음과 같다.

1. **Jira Account와 사내 인력 정보의 연결**
   - Worklog 작성자의 role을 알아야 PLAN / DEV / ART를 구분할 수 있다.

2. **Jira Custom Field Metadata**
   - Size, Category, Story Point 등이 어떤 `customfield_xxx`에 해당하는지 알아야 한다.

3. **Jira Version 종료 정보**
   - A-2에서는 Jira Version Close 시점을 실적 확정 시점으로 정의했으므로,
     해당 Version이 최종 종료되었는지를 확인할 정보가 필요하다.

4. **QA 실제 작업 정보**
   - 현재 원본에는 QA 담당자의 Worklog나 role 정보가 없어
     실제 QA MD는 직접 계산할 수 없다.
   - A-2에서 정한 대로 현재는 QA 반려 Bug의 수정 Worklog를 proxy로 사용하며,
     실제 QA MD를 계산하려면 QA 담당자와 QA Worklog 정보가 추가로 필요하다.


### 결론

Jira API 원본은 보관용 Raw 데이터로는 그대로 저장할 수 있지만,
A-2에서 정의한 MD 계산에는 바로 사용할 수 없다.

MD 계산 전에 최소한 다음 처리가 필요하다.

- 시간 단위를 초 단위로 통일
- Issue 내부 Worklog를 개별 행으로 분리
- Worklog 작성자와 직군 연결
- 복수 Fix Version 처리
- Custom Field를 Category / Size 등의 표준 컬럼으로 변환

구체적으로 어느 원본 값을 어떤 DB 컬럼으로 변환할지는 B-2에서 정의한다.

### B-2. Jira 원본 → DB 필드 매핑

Jira API 원본은 중첩된 JSON 형태이므로,
MD 계산과 이후 일정 분석에 사용할 수 있도록 필요한 값을 분리하여 저장한다.

시간 값은 사람이 읽는 문자열보다 Jira가 제공하는 초 단위 값을 우선 사용하며,
배열 형태의 Worklog와 Fix Version은 각각 별도 행으로 분리한다.

| 원본 위치 | DB 컬럼 | 데이터 타입 | 적재 전 변환 | 값이 비었을 때 | Jira 변경 영향 |
|---|---|---|---|---|---|
| `id` | `issue.jira_issue_id` | TEXT | 문자열 그대로 저장 | 적재 오류 처리 | 낮음. Jira 내부 식별자로 사용 |
| `key` | `issue.issue_key` | TEXT | 그대로 저장 | 적재 오류 처리 | 낮음. 프로젝트 Key 변경 시 영향 가능 |
| `fields.summary` | `issue.summary` | TEXT | 그대로 저장 | NULL 허용 | 낮음 |
| `fields.issuetype.name` | `issue.issue_type` | TEXT | 그대로 저장 | NULL이면 `UNKNOWN` | 이슈 유형 추가/이름 변경 시 영향 |
| `fields.status.id` | `issue.status_id` | TEXT | 그대로 저장 | NULL이면 적재 오류 처리 | Workflow 변경 시 새 Status ID 확인 필요 |
| `fields.status.name` | `issue.status_name` | TEXT | 원본 표시값 그대로 저장 | NULL 허용 | 상태명 변경 및 한/영문 변경 영향 |
| `fields.status.statusCategory.key` | `issue.status_category` | TEXT | 소문자로 통일 | NULL이면 `UNKNOWN` | 비교적 낮음 |
| `fields.assignee.accountId` | `issue.assignee_account_id` | TEXT | accountId만 추출 | 미지정 이슈는 NULL | 계정 변경/퇴사 시 인력 매핑 영향 |
| `fields.created` | `issue.created_at` | TIMESTAMP | UTC 기준으로 변환 | 적재 오류 처리 | 낮음 |
| `fields.updated` | `issue.updated_at` | TIMESTAMP | UTC 기준으로 변환 | 적재 오류 처리 | 낮음. 향후 증분 적재 기준으로 사용 가능 |
| `fields.resolutiondate` | `issue.resolution_at` | TIMESTAMP | UTC 기준으로 변환 | 미완료 또는 값이 없으면 NULL | Workflow의 Resolution 사용 방식에 영향 |
| `fields.timetracking.originalEstimateSeconds` | `issue.original_estimate_seconds` | INTEGER | 초 단위 그대로 저장 | 입력되지 않았으면 NULL | 낮음. MD 계산 시 문자열보다 안정적 |
| Size에 해당하는 Custom Field | `issue.size_label` | TEXT | Field Metadata로 해당 필드를 찾은 뒤 S/M/L 추출 | NULL 유지 | 높음. Custom Field ID 변경 가능 |
| Category에 해당하는 Custom Field | `issue.category_type` | TEXT | `시스템`/`SYSTEM` → `SYSTEM`, `콘텐츠`/`CONTENT` → `CONTENT`으로 통일 | NULL이면 `UNKNOWN` | 높음. Custom Field ID/선택지 변경 가능 |
| Story Point에 해당하는 Custom Field | `issue.story_points` | REAL | Field Metadata로 해당 필드 식별 후 숫자로 변환 | NULL 유지 | 높음. Custom Field ID 변경 가능 |
| `fields.parent.key` | `issue.parent_key` | TEXT | parent의 key만 추출 | parent가 없으면 NULL | Jira 계층 구조 변경 시 영향 |
| `fields.fixVersions[].id` | `issue_version.version_id` | TEXT | 배열의 각 Version을 별도 행으로 분리 | Version이 없으면 관계행 생성 안 함 | 낮음 |
| `fields.fixVersions[].name` | `issue_version.version_name` | TEXT | 그대로 저장 | NULL 허용 | Version 이름 변경 시 영향 |
| `fields.fixVersions[].released` | `issue_version.released` | BOOLEAN | boolean으로 저장 | NULL이면 false로 추정하지 않고 NULL | Jira Version 운영 규칙 변경 시 영향 |
| `fields.fixVersions[].releaseDate` | `issue_version.release_date` | DATE | 날짜 형식으로 변환 | 없으면 NULL | 낮음 |
| `fields.worklog.worklogs[].id` | `worklog.worklog_id` | TEXT | Worklog별 별도 행 생성 | 적재 오류 처리 | 낮음 |
| `fields.worklog.worklogs[].author.accountId` | `worklog.author_account_id` | TEXT | accountId 추출 | 없으면 `UNCLASSIFIED` 처리 | 인력 매핑 정보 변경 시 영향 |
| `fields.worklog.worklogs[].started` | `worklog.started_at` | TIMESTAMP | UTC 기준으로 변환 | 없으면 해당 Worklog 적재 오류 처리 | 낮음 |
| `fields.worklog.worklogs[].timeSpentSeconds` | `worklog.time_spent_seconds` | INTEGER | 초 단위 그대로 저장 | 없으면 해당 Worklog는 MD 계산에서 제외하고 오류 기록 | Actual MD 계산 핵심 값 |
| `changelog.histories[].id` | `change_event.history_id` | TEXT | 이력별 식별자 저장 | 적재 오류 처리 | 낮음 |
| `changelog.histories[].created` | `change_event.changed_at` | TIMESTAMP | UTC 기준으로 변환 | 적재 오류 처리 | 낮음 |
| `changelog.histories[].items[].field` | `change_event.field_name` | TEXT | 원본 값 보존 | NULL이면 적재 오류 처리 | Jira 표시명 변경 가능 |
| `fromString` | `change_event.from_value` | TEXT | 원본 문자열 저장 | 변경 전 값이 없으면 NULL | Status 이름 변경 영향 |
| `toString` | `change_event.to_value` | TEXT | 원본 문자열 저장 | 변경 후 값이 없으면 NULL | Status 이름 변경 영향 |

#### 시간 값 처리

Jira 원본에는 다음처럼 사람이 읽는 문자열과 숫자가 같이 존재한다.

- `originalEstimate = "30d"`
- `originalEstimateSeconds = 864000`
- `timeSpent = "18d 2h"`
- `timeSpentSeconds = 525600`

계산 과정에서 `"30d"` 또는 `"18d 2h"` 문자열을 다시 해석하지 않고
초 단위 숫자를 표준값으로 사용한다.

A-2에서 `8시간 = 1 MD`로 정의했으므로,

`1 MD = 8 × 60 × 60 = 28,800초`

이며 실제 MD는 다음과 같이 계산한다.

`Actual MD = SUM(worklog.time_spent_seconds) / 28,800`

문자열 형태의 시간 값은 원본 확인용으로만 보존한다.

#### Worklog 처리

Worklog는 Issue 한 건 안에 배열 형태로 들어 있지만,
DB에서는 Worklog 한 건을 한 행으로 분리한다.

예를 들어 HRG-1032에는 다음과 같이 작성자와 작업시간이 각각 존재한다.

- 작성자: `author.accountId`
- 시작 시각: `started`
- 작업시간: `timeSpentSeconds`

따라서 Actual MD는 Issue 전체의 `timeSpentSeconds`가 아니라
개별 Worklog를 합산하여 계산한다.

이 방식으로 저장해야 A-2에서 정의한 것처럼
Worklog 작성자의 직군에 따라 PLAN / DEV / ART MD를 구분할 수 있다.

#### Fix Version 처리

`fixVersions`는 배열이므로 하나의 문자열 컬럼에 넣지 않고,
Issue와 Version의 관계를 별도의 행으로 저장한다.

예를 들어 HRG-1032는 `v1.8`, `v1.9` 두 Version을 동시에 가지고 있으므로
다음과 같이 저장한다.

| issue_key | version_id | version_name |
|---|---|---|
| HRG-1032 | 10041 | v1.8 |
| HRG-1032 | 10042 | v1.9 |

실제 Version별 MD 귀속 시에는 A-1에서 정한 복수 Version 처리 규칙을 적용한다.

#### Custom Field 처리

Jira Custom Field는 `customfield_10016`,
`customfield_10031`처럼 ID만으로 의미를 알 수 없다.

또한 샘플에서 HRG-1032에는

`customfield_10031 = {"id": "10501", "value": "L"}`

처럼 object 형태의 값이 존재하지만,
HRG-0914에는

`customfield_10032 = "L"`

처럼 다른 Custom Field와 값 구조도 나타난다.

따라서 특정 ID가 항상 Size나 Story Point라고 코드에 직접 작성하지 않는다.

Jira의 `/rest/api/3/field`에서 Field Metadata를 별도로 조회하고,
다음과 같은 Field Mapping을 관리한다.

| semantic_key | jira_field_id | 의미 |
|---|---|---|
| `size_label` | Metadata 조회 결과 | S / M / L |
| `category_type` | Metadata 조회 결과 | SYSTEM / CONTENT |
| `story_points` | Metadata 조회 결과 | Story Point |
| `epic_link` | Metadata 조회 결과 | 상위 작업 연결 |

ETL 코드는 `customfield_10031` 같은 Jira ID가 아니라
`size_label`, `category_type` 같은 내부 의미 이름을 기준으로 동작한다.

예를 들어 Jira 관리자가 Size 필드의 ID를 변경하더라도
Field Mapping만 갱신하면 MD 계산 로직 자체는 수정하지 않는다.

Field Metadata에서 해당 필드를 찾을 수 없거나
예상한 데이터 타입과 다른 경우에는 임의로 NULL 처리하여 계속 계산하지 않고,
Mapping 오류로 표시하여 확인 후 적재하도록 한다.

### B-3. "언제부터 언제까지 일했는지" 알아내기

Jira에는 별도의 작업 시작일이 없으므로
Changelog의 상태 변경 기록을 이용하여 작업 기간을 계산한다.

상태 변경 이력은 다음 형태로 저장한다.

| 컬럼 | 의미 |
|---|---|
| `issue_key` | Jira 이슈 번호 |
| `history_id` | 변경 이력 ID |
| `changed_at` | 상태 변경 시각 |
| `from_status` | 변경 전 상태 |
| `to_status` | 변경 후 상태 |

예를 들어 HRG-1032에는 다음과 같은 상태 변화가 있다.

`To Do → In Progress → In Review → Done → In Progress → Done`

따라서 작업 시작일과 종료일은 다음과 같이 정의한다.

- 작업 시작일: 최초 `In Progress` 진입 시점
- 작업 종료일: 마지막 `Done` 진입 시점
- 실제 작업기간: `In Progress` 상태였던 기간의 합

마지막 `Done`을 사용하는 이유는
HRG-1032처럼 완료 후 다시 열려 추가 작업이 발생할 수 있기 때문이다.

`검토 대기(In Review)`와 `보류(On Hold)` 상태는
실제 작업기간에서 제외한다.

두 상태는 담당자가 실제 작업을 진행하는 시간보다
검토, 의사결정, 외부 조건 등을 기다리는 시간에 가깝기 때문에
포함할 경우 실제 작업기간을 과대 계산할 수 있다고 판단하였다.

다만 해당 기간에 실제 Worklog가 기록되어 있다면
그 시간은 실제 투입 공수이므로 Actual MD에는 포함한다.

즉,

- 상태 변경 이력: 실제 작업이 진행된 기간 계산
- Worklog: 실제 투입 MD 계산

으로 용도를 구분한다.

Jira에서 동일한 의미의 상태가 `In Progress` / `진행 중`처럼
다른 이름으로 사용되는 경우에는 계산 시 같은 상태로 매핑한다.

### B-4. Jira 데이터 동기화 방식

#### 1. 전체 적재가 아닌 증분 동기화

매번 Jira 전체 데이터를 다시 가져오지 않고,
마지막 동기화 이후 변경된 Issue만 가져오는 증분 동기화를 기본으로 한다.

연간 약 2천 건 수준의 데이터이므로 전체 적재도 불가능한 규모는 아니지만,
변경되지 않은 Issue까지 반복해서 요청할 필요는 없다.

따라서 Jira의 `updated` 값을 기준으로 변경된 Issue를 조회하고,
해당 Issue의 Worklog와 Changelog를 다시 수집한다.


#### 2. 어디까지 가져왔는지 기억하는 방법

마지막으로 정상 완료된 동기화 시각을 `watermark`로 저장한다.

예를 들어

`watermark = 2026-01-26 12:00:00`

이라면 다음 실행에서는 해당 시점 이후 수정된 Issue를 가져온다.

단, 동기화 시각 경계에서 변경된 데이터가 누락되는 것을 줄이기 위해
정확히 watermark 이후만 조회하지 않고 일정 시간을 겹쳐 다시 조회한다.

예:

`조회 시작 시각 = watermark - 24시간`

같은 데이터가 다시 조회되더라도 아래의 멱등성 규칙으로 중복을 방지한다.

`updated`만으로 모든 변경을 완벽하게 감지할 수 있다고 가정하는 것은 위험하므로,
운영 중에는 주기적으로 전체 데이터와 건수 및 갱신 시점을 대조하여 누락 여부를 확인한다.


#### 3. 동기화 주기

증분 동기화는 **하루 2회, 00시와 12시에 실행**한다.

이 시스템은 실시간 현황판이 아니라
실제 MD 측정과 다음 버전 일정 계획을 위한 시스템이며,
데이터 규모 역시 연간 약 2천 건 수준이므로
몇 시간 단위의 실시간 동기화는 필요성이 낮다고 판단하였다.

- 00시 동기화: 이전 업무일 오후 및 이후 변경사항 반영
- 12시 동기화: 당일 오전 업무 변경사항 반영

따라서 일반적인 업무 변경사항은 최대 약 반나절 이내에 반영할 수 있고,
Jira API 호출 횟수도 불필요하게 늘리지 않을 수 있다.

단, Version Close와 같이 Actual MD를 최종 확정해야 하는 시점에는
정기 실행 시간을 기다리지 않고 한 번 추가 동기화한 뒤 최종 MD를 계산한다.


#### 4. 중복 적재 방지

같은 데이터를 여러 번 가져와도 결과가 중복되지 않도록
Jira가 제공하는 고유 ID를 기준으로 저장한다.

예를 들어

- Issue: `jira_issue_id`
- Worklog: `worklog_id`
- Changelog: `history_id`

를 고유키로 사용한다.

이미 존재하는 ID가 다시 들어오면 새 행을 추가하지 않고
기존 값을 갱신하는 Upsert 방식으로 처리한다.

따라서 watermark를 일부 겹쳐 조회하거나
동기화 작업을 다시 실행해도 MD가 두 번 합산되지 않는다.


#### 5. Jira API 요청 제한 대응

Jira가 요청 과다로 응답을 거부하면 즉시 계속 요청하지 않고
일정 시간 기다린 뒤 재시도한다.

재시도 간격은 점차 늘리는 방식으로 처리한다.

예:

`1분 → 2분 → 4분 → 8분`

정해진 재시도 횟수를 초과하면 해당 동기화를 실패 처리하고
watermark를 갱신하지 않는다.

따라서 다음 실행에서 실패한 구간부터 다시 수집할 수 있도록 한다.


#### 6. 이미 배포된 Version의 Issue가 수정된 경우

A-2에서는 Version 종료 시점을 실제 배포일이 아니라
**Jira Version Close 시점**으로 정의하였다.

따라서 실제 배포가 끝났더라도 Jira Version이 아직 Close되지 않았다면
추가 Worklog나 Issue 수정사항을 계속 반영하여 Actual MD를 다시 계산한다.

반면 Jira Version Close 이후에는 해당 Version의 Actual MD를 확정값으로 보고
자동으로 다시 계산하지 않는다.

Close 이후 과거 Issue가 수정된 경우에는
원본 데이터에는 변경사항을 저장하되,
이미 확정된 MD는 바로 덮어쓰지 않는다.

필요한 경우 수정 내역을 확인한 뒤
명시적인 재계산 절차를 통해서만 확정값을 변경한다.

이를 통해 과거 데이터 수정으로 인해
이미 갱신된 baseline과 일정이 조용히 바뀌는 것을 방지한다.

### B-5. 원본 데이터 보관 및 재처리

Jira API에서 받은 원본 데이터는 DB 적재 후 삭제하지 않고
JSON 파일 형태로 그대로 보관한다.

원본을 남기는 이유는
향후 MD 계산 규칙이나 데이터 변환 규칙이 변경되었을 때
Jira API를 다시 호출하지 않고 과거 데이터를 다시 계산하기 위해서이다.

또한 ETL 로직에 오류가 발견되었을 경우에도
원본부터 다시 처리할 수 있다.

#### 저장 방식

원본은 수집 날짜와 실행 시점을 기준으로 구분하여 저장한다.

```text
data/raw/jira/
├── 2026-01-26/
│   ├── 0000/
│   │   ├── issues.json
│   │   ├── worklogs.json
│   │   └── changelogs.json
│   └── 1200/
│       ├── issues.json
│       ├── worklogs.json
│       └── changelogs.json
└── ...
```

저장한 Raw 파일은 이후 수정하지 않는다.

#### 계산 규칙이 변경된 경우

MD 계산 또는 데이터 변환 규칙이 변경되면
저장된 Raw 데이터를 새로운 규칙으로 다시 처리한다.

재처리 순서는 다음과 같다.

`Raw 데이터 → 새로운 변환 규칙 적용 → DB 재적재 → MD 재계산`

기존 결과를 단순히 수정하는 대신,
재계산 대상 Version 또는 기간의 기존 결과를 제거한 뒤
새로운 규칙으로 계산한 결과를 다시 적재한다.

이를 통해 이전 계산 규칙의 값이 DB에 남아
새 결과와 섞이는 것을 방지한다.

### B-6. DB 테이블 설계

DB는 SQLite를 사용한다.

현재 데이터는 연간 약 2천 건 수준이며,
주요 작업도 Jira 데이터 적재와 Version별 MD 집계이므로
별도의 DB 서버가 필요한 구조보다
하나의 파일로 실행 가능한 SQLite가 과제 재현성과 운영 복잡도 측면에서 적절하다고 판단하였다.

데이터는 다음 3단계로 구분한다.

| 단계 | 목적 | 주요 객체 |
|---|---|---|
| Raw | Jira에서 받은 원본 보관 | `raw_jira_payload` |
| 정제 | 계산과 조회에 사용할 구조화 데이터 | `issue`, `worklog`, `issue_version`, `person`, `issue_status_history`, `version`, `calendar_day` |
| 요약 | Version × Category × Size × 공정별 Actual MD 조회 | `vw_version_category_size_md` |

Raw 원본 파일 자체는 B-5에서 정의한 방식으로 별도 보관하며,
DB의 Raw 영역은 수집한 데이터를 적재·재처리하기 위한 단계로 사용한다.


#### Raw 단계

`raw_jira_payload`

Jira API에서 받은 JSON을 가공하지 않은 상태로 저장한다.

주요 값은 다음과 같다.

- 어떤 종류의 데이터를 받은 것인지
- 어떤 Issue 또는 API 요청에 대한 데이터인지
- 언제 수집했는지
- 원본 JSON

Raw 데이터는 수정하지 않고 계속 추가한다.


#### 정제 단계

`issue`

Issue의 기본 정보를 저장한다.

- Issue Key
- Category
- 원본 Size
- A-2 기준으로 계산한 Size
- 담당자
- 상태
- 생성 / 시작 / 완료 시각
- 최초 추정 공수
- Story Point
- Reopen 횟수

`issue_version`

하나의 Issue가 여러 Fix Version을 가질 수 있으므로
Issue와 Version을 별도 관계로 저장한다.

Version별 MD 계산에 포함할 관계는 `include_in_md`로 구분하여
복수 Fix Version으로 인한 중복 집계를 방지한다.

`worklog`

Actual MD 계산의 원천 데이터이다.

Worklog 한 건을 한 행으로 저장하며

- Issue
- 작성자
- 작업 시각
- 작업시간(초)

을 저장한다.

Actual MD는

`SUM(time_spent_seconds) / 28,800`

으로 계산한다.

`person`

Worklog 작성자의 role과 공정을 연결하기 위한 인력 정보이다.

예를 들어

- planner → PLAN
- server / client → DEV
- art → ART

로 관리한다.

`issue_status_history`

B-3에서 정의한 상태 변경 이력을 저장한다.

최초 In Progress 진입 시점,
마지막 Done 진입 시점,
실제 작업 진행 구간을 계산하는 데 사용한다.

`version`

Version별 계획 배포일, 실제 배포일,
Jira Close 시점을 관리한다.

A-2에서 Jira Close를 Version 종료 기준으로 정의했으므로
Actual MD 최종 확정 여부를 판단할 때 사용한다.

`calendar_day`

공휴일과 담당자 PTO를 저장하며
이후 일정 역산 시 실제 작업 가능일 계산에 사용한다.


#### 요약 단계

현재 데이터 규모에서는 Version별 MD 결과를
별도 테이블로 저장하지 않고 VIEW로 계산한다.

`vw_version_category_size_md`

는 정제된 Issue, Worklog, Version, Person 데이터를 결합하여

`Version × Category × Size × 공정`

별 Actual MD를 보여준다.

정제 데이터가 수정되면 VIEW 결과도 바로 변경되므로
별도의 요약 테이블을 다시 동기화할 필요가 없다.


#### 저장 및 조회 기준

SQLite는 물리적인 정렬키나 Partition을 별도로 사용하지 않는다.

대신 자주 조회하는 조건에 Index를 생성한다.

| 대상 | Index 기준 | 이유 |
|---|---|---|
| Worklog | `issue_key` | Issue별 MD 집계 |
| Worklog | `author_person_key, started_at` | 담당자별 작업 조회 |
| Issue Version | `version_name` | Version별 MD 조회 |
| Issue | `assignee_person_key, started_at, resolved_at` | 특정 기간 동시 담당 Issue 조회 |
| Status History | `issue_key, changed_at` | 상태 변경 순서 계산 |

연간 약 2천 건 규모이므로 물리적인 Partition은 사용하지 않는다.
테이블은 데이터 의미에 따라 논리적으로 분리하고,
조회 성능은 Index로 보완한다.

### B-7. 핵심 조회 쿼리

B-6에서 설계한 SQLite 테이블에 제공 CSV를 실제로 적재한 뒤,
다음 두 가지 핵심 조회 쿼리를 실행하였다.

DB 적재에는 `scripts/b7_load_sqlite.py`를 사용하였으며,
실행 결과 `output/horang_pm.db`가 생성된다.

적재 과정에서 다음 데이터를 변환하였다.

- Worklog의 `h`, `d` 단위를 초 단위로 통일
  - `1h = 3,600초`
  - `1d = 8시간 = 28,800초`
- 복수 Fix Version은 Issue-Version 관계로 분리
- 복수 Fix Version 이슈는 Version별 MD 중복 집계를 방지하기 위해 집계 대상에서 제외
- 제공 CSV에는 Worklog ID가 없으므로 적재 테스트용 고유 ID 생성
- `started`, `resolved`는 제공 CSV에 정리된 값을 사용

실제 Jira API 연동 시에는 Jira가 제공하는 Worklog ID와
Changelog를 이용하여 동일한 구조로 적재한다.


#### 1. Version별 Category × Size 실제 MD

사용 쿼리:

`sql/b7_version_md.sql`

Actual MD는 A-2에서 정의한 기준에 따라
Worklog 작업시간을 합산한 뒤 다음과 같이 계산한다.

`Actual MD = SUM(time_spent_seconds) / 28,800`

Issue에 Fix Version이 두 개 이상 지정되어
Version 귀속이 명확하지 않은 경우에는 중복 집계를 방지하기 위해
Version별 Actual MD 집계에서 제외한다.

실행 예시 중 v1.9 결과는 다음과 같다.

| Version | Category | Size | Actual MD |
|---|---|---:|---:|
| v1.9 | CONTENT | M | 14.500 |
| v1.9 | CONTENT | S | 29.775 |
| v1.9 | SYSTEM | L | 111.175 |
| v1.9 | SYSTEM | M | 2.125 |
| v1.9 | SYSTEM | S | 6.425 |

v1.9의 기록된 Actual MD 합계는 `164.0 MD`이다.

실제 SQLite 실행 화면은 아래와 같다.

![Version별 Category × Size Actual MD 실행 결과](images/b7_version_md.png)


#### 2. 특정 기간 담당자의 동시 담당 Issue 수

사용 쿼리:

`sql/b7_concurrent_issues.sql`

동시 담당 Issue는 특정 날짜가 Issue의 작업기간 안에 포함되는 경우로 정의한다.

`started_at <= 기준일 <= resolved_at`

특정 기간의 각 날짜별 담당 Issue 수를 계산한 뒤
그중 최댓값을 해당 기간의 최대 동시 담당 건수로 사용한다.

실행 조건은 다음과 같다.

- 담당자: `dev_oh`
- 기간: `2025-10-13 ~ 2025-10-23`

실행 결과는 다음과 같다.

| 날짜 | 동시 담당 Issue |
|---|---:|
| 2025-10-13 | 6 |
| 2025-10-14 | 6 |
| 2025-10-15 | 6 |
| 2025-10-16 | 7 |
| 2025-10-17 | 7 |
| 2025-10-18 | 7 |
| 2025-10-19 | 7 |
| 2025-10-20 | 7 |
| 2025-10-21 | 7 |
| 2025-10-22 | 7 |
| 2025-10-23 | 7 |

따라서 해당 기간 동안 `dev_oh`가 동시에 맡고 있던 Issue는
최대 **7건**이다.

여기서 동시 담당 건수는 해당 날짜에 Issue가 열려 있었는지를 확인하기 위한 값이므로
주말도 포함한다.

실제 작업 가능 공수를 계산하는 이후 일정 역산 단계에서는
별도로 공휴일, PTO, availability를 반영한다.

실제 SQLite 실행 화면은 아래와 같다.

![담당자 동시 담당 Issue 수 실행 결과](images/b7_concurrent_issues.png)

### B-8. 측정한 MD를 기준표로 되돌리는 규칙

#### 1. 기존 값을 덮어쓰지 않고 버전별 실적을 쌓는다

기존 baseline 값을 직접 덮어쓰지 않는다.

Jira Version이 Close되면 해당 Version에서 측정된 Actual MD를
`Category × Size × 공정` 단위로 저장하고,
어떤 Version의 실적으로 계산된 값인지 함께 남긴다.

현재 기준표는 이 이력 중 **가장 최근에 승인된 baseline**을 사용한다.

이렇게 하면 기준이 변경된 과정과 이전 값을 추적할 수 있고,
잘못된 갱신이 발생했을 때 이전 기준으로 되돌릴 수도 있다.


#### 2. 최근 3개 종료 Version의 중앙값을 baseline 후보로 사용한다

한 Version의 특이한 결과가 기준표를 크게 바꾸는 것을 막기 위해
가장 최근의 유효한 종료 Version 3개의 실적을 사용한다.

평균이 아니라 **중앙값(Median)** 을 사용한다.

예를 들어 최근 세 Version의 DEV MD가

`8 MD / 9 MD / 25 MD`

라면

- 평균: 14 MD
- 중앙값: 9 MD

가 된다.

따라서 한 Version에서 일시적으로 공수가 크게 증가하더라도
baseline 전체가 해당 값에 끌려가는 것을 줄일 수 있다.

3개 Version을 사용하는 것은 최근 작업 방식을 반영하면서도
한 Version의 이상값이 기준을 결정하지 않도록 하기 위한 초기 운영 기준이다.

Worklog가 없는 이슈의 MD를 임의로 추정해서 넣지는 않으며,
A-3에서 정한 것처럼 실제 관측된 Worklog만 Actual MD 계산에 사용한다.


#### 3. 큰 변화는 자동 반영하지 않고 사람이 승인한다

Version Close 후 새로운 baseline 후보값까지는 자동으로 계산한다.

다만 실제 baseline 반영은 **파트 리더 승인 후** 진행한다.

승인자는 다음 정보를 확인한다.

- 기존 baseline
- 새 baseline 후보
- 최근 3개 Version의 Actual MD
- 계산에 사용된 Issue 수
- Worklog 기록률

특히 새 후보값이 기존 승인 baseline보다
**50% 이상 증가하거나 감소한 경우**에는 큰 변화로 표시하여
반드시 원인을 확인하도록 한다.

50%는 통계적으로 확정된 이상치 기준이 아니라,
초기 운영 단계에서 명백하게 큰 변화만 별도 검토하기 위한 안전장치이다.

정상적인 변화라고 판단되면 승인하고,
데이터 누락이나 일회성 특이사항 때문이라면 기존 baseline을 유지한다.

QA는 A-2에서 실제 QA MD를 직접 측정할 수 없다고 판단했으므로
현재 proxy 값을 실제 QA MD처럼 자동 갱신하지 않는다.
실제 QA Worklog가 확보되기 전까지는 별도로 관리한다.


#### 4. 이미 통지한 일정은 자동으로 덮어쓰지 않는다

baseline이 변경되면 새로운 기준으로 이후 일정을 다시 계산한다.

이미 담당자에게 통지된 일정의 기획 착수일이 변경된다면
기존 일정을 조용히 수정하지 않고 변경 알림을 다시 보낸다.

알림에는 다음 내용을 포함한다.

- 기존 기획 착수일
- 변경된 기획 착수일
- 변경된 영업일 수
- baseline 변경 Version

재계산 결과 일정이 변하지 않았다면 추가 알림은 보내지 않는다.


#### 전체 흐름

`Version Close`

→ `Actual MD 계산`

→ `버전별 실적 저장`

→ `최근 3개 Version 중앙값으로 baseline 후보 계산`

→ `파트 리더 검토 및 승인`

→ `승인된 baseline 적용`

→ `향후 일정 재계산`

→ `기존 통지 일정이 변경된 경우 변경 알림`

### B-9. Jira 변경으로 인한 잘못된 계산 방지

Jira의 필드나 Workflow가 변경되었을 때 가장 위험한 경우는
시스템이 오류 없이 계속 동작하면서 잘못된 MD를 만드는 것이다.

따라서 Jira 변경을 단순히 사후 대응하는 것이 아니라,
**계산에 사용되는 데이터의 구조와 의미가 기존 규칙과 같은지 먼저 검증하고,
확인되지 않은 변경이 있으면 계산을 중단하는 방식**으로 처리한다.


#### 1. 계산 전에 Jira 구조 변경을 확인한다

동기화 시 Jira Field Metadata와 상태 정보를 조회하여
직전 정상 실행 시점의 정보와 비교한다.

특히 다음 항목을 확인한다.

- Size / Category / Story Point 등 계산에 사용하는 Field가 존재하는지
- Field ID가 변경되지 않았는지
- 값의 데이터 타입이 달라지지 않았는지
- 기존에 없던 Status가 추가되지 않았는지
- 기존 Status가 삭제되거나 이름이 변경되지 않았는지

계산에 사용하지 않는 필드의 추가는 기록만 남기고 정상 처리한다.


#### 2. 알 수 없는 값은 임의로 변환하지 않는다

다음과 같은 경우에는 기본값이나 NULL로 임의 처리하여
MD 계산을 계속하지 않는다.

- Size Field Mapping을 찾을 수 없음
- Category Field Mapping을 찾을 수 없음
- 예상과 다른 데이터 타입이 들어옴
- 정의되지 않은 Workflow Status가 등장함
- Worklog 작성자를 공정에 매핑할 수 없음

이 항목들은 MD 또는 작업기간 계산 결과를 직접 바꿀 수 있기 때문에
**허용 건수는 0건**으로 둔다.

한 건이라도 발견되면 Raw 데이터 적재는 계속하지만
영향받는 정제 및 집계 결과 생성을 중단한다.


#### 3. "정상처럼 보이는 잘못된 값"을 검증한다

단순히 프로그램 오류가 발생했는지만 확인하지 않고
정제 결과 자체도 검증한다.

예를 들어 다음 조건을 검사한다.

- 원본 Issue 수와 정제 Issue 수가 예상 없이 감소하지 않았는지
- Size / Category의 UNKNOWN 비율이 갑자기 증가하지 않았는지
- 새로운 Status가 기존 상태로 임의 분류되지 않았는지
- Worklog는 존재하지만 공정이 UNCLASSIFIED인 데이터가 생기지 않았는지
- 기존에는 값이 있던 핵심 Field가 갑자기 대부분 NULL이 되지 않았는지

이 검증을 통과하지 못하면 새로운 MD나 baseline을 확정하지 않고
직전 정상 결과를 유지한다.


#### 4. 이상 감지 후 처리 순서

계산에 영향을 주는 변경이 발견되면 다음 순서로 처리한다.

1. Jira Raw 데이터는 그대로 저장한다.
2. 영향을 받는 MD / 일정 계산을 중단한다.
3. 변경된 Field 또는 Status와 영향 범위를 기록하고 알림을 보낸다.
4. 담당자가 Jira에서 변경된 의미를 확인한다.
5. Field Mapping / Status Mapping / 변환 규칙을 수정한다.
6. B-5에서 저장한 Raw 데이터를 새로운 규칙으로 다시 처리한다.
7. 데이터 검증을 통과하면 정상 계산을 재개한다.

이때 확인되지 않은 값을 임의로 기존 상태나 기본값에 연결하지 않는다.


#### 결론

Raw 데이터 수집은 계속하되,
MD나 일정 계산에 사용하는 필드와 상태의 의미가 확인되지 않으면
해당 결과를 생성하거나 baseline에 반영하지 않는다.

### B-10. DB 값이 Jira와 일치하는지 상시 확인

Jira 데이터를 정상적으로 수집했더라도
API 누락, ETL 오류, 잘못된 Mapping 등으로 DB 값이 Jira와 달라질 수 있다.

따라서 다음 검증을 정기적으로 수행한다.

| 검증 항목 | 비교 내용 | 주기 | 허용 차이 | 차이가 발생하면 |
|---|---|---|---:|---|
| Issue 동기화 | Jira에서 변경된 Issue Key 목록과 DB에 반영된 Issue 목록 | 00시 / 12시 동기화 후 | 0% | 해당 동기화 실패 처리 후 다시 수집 |
| 핵심 Issue 값 | status, assignee, Fix Version, Category, Size 등 Jira 현재값과 DB 값 | 매 동기화 후 변경된 Issue 전체 | 0% | 해당 데이터의 MD 계산 중단 후 재적재 |
| Worklog | Jira Worklog 건수와 `timeSpentSeconds` 합계 vs DB 건수와 합계 | 매 동기화 후, Version Close 시 전체 재검증 | 0% | 해당 Issue 재수집, 불일치가 남으면 Version MD 확정 중단 |
| Jira 화면 표본 확인 | Jira 화면과 DB의 상태, 담당자, Version, Worklog 합계 직접 비교 | 주 1회 | 불일치 0건 | 1건이라도 발견되면 같은 유형 전체 데이터 재검증 |

#### 1. Issue 동기화 검증

증분 동기화가 끝나면
해당 수집 구간에서 Jira가 반환한 Issue Key와
DB에 실제 반영된 Issue Key를 비교한다.

예를 들어 Jira에서 변경 Issue가 8건 조회됐다면
DB에도 동일한 8건이 반영되어 있어야 한다.

단순 건수뿐 아니라 Issue Key 자체를 비교하여
한 건이 빠지고 다른 한 건이 중복된 경우도 탐지한다.


#### 2. 핵심 필드 검증

변경된 Issue에 대해서는 MD와 일정 계산에 직접 사용되는 다음 값을
Jira 원본과 DB에서 비교한다.

- Status
- Assignee
- Fix Version
- Category
- Size

이 값들은 동일한 원본을 옮기는 과정이므로
허용 오차는 0%로 둔다.

불일치가 발견되면 해당 Issue의 계산 결과를 사용하지 않고
Raw 데이터부터 다시 처리한다.


#### 3. Worklog 검증

Actual MD의 원천은 Worklog이므로
다음 두 값을 Jira와 DB에서 비교한다.

- Worklog 건수
- `timeSpentSeconds` 합계

두 값 중 하나라도 다르면 MD 자체가 달라질 수 있으므로
허용 차이는 0%로 한다.

평소에는 변경된 Issue를 대상으로 확인하고,
Version Close 시에는 해당 Version 전체 Worklog를 다시 검증한다.

검증을 통과한 경우에만 해당 Version의 Actual MD를 확정하고
baseline 갱신 대상으로 사용한다.


#### 4. Jira 화면과 정기 표본 비교

API와 DB끼리만 비교하면
잘못된 Mapping 규칙이 양쪽 처리 과정에서 계속 사용되는 문제를
놓칠 수 있다.

따라서 주 1회 일부 Issue를 선택하여
Jira 화면에서 보이는 값과 DB 값을 직접 비교한다.

확인 항목은 다음과 같다.

- 현재 상태
- 담당자
- Fix Version
- Worklog 총 시간

표본에서 1건이라도 차이가 발견되면
해당 건만 수정하고 끝내지 않고
같은 필드 또는 변환 규칙을 사용하는 전체 데이터를 다시 확인한다.


#### Version Close 시 최종 검증

Version의 Actual MD를 확정하기 전에는 다음 순서로 최종 검증한다.

`Issue 목록 확인`
→ `핵심 필드 확인`
→ `Worklog 건수 및 시간 합계 확인`
→ `모두 일치하면 MD 확정`
→ `baseline 후보 계산`

하나라도 일치하지 않으면
해당 Version의 MD와 baseline 갱신을 보류한다.