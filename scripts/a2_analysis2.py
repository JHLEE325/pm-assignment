from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path("data/source")

# 기준일 2026-01-26 현재 Jira Close가 완료된 버전
CLOSED_VERSIONS = [
    "v1.3",
    "v1.4",
    "v1.5",
    "v1.6",
    "v1.7",
    "v1.8",
    "v1.9",
]


# 6번에서 정한 PLAN Size 기준
PLAN_SIZE_RULES = {
    "CONTENT": {
        "S_MAX": 32,
        "M_MAX": 56,
    },
    "SYSTEM": {
        "S_MAX": 72,
        "M_MAX": 136,
    },
}


def to_hours(value):
    """orig_estimate를 시간으로 변환"""
    if pd.isna(value):
        return np.nan

    value = str(value).strip().lower()

    if value.endswith("h"):
        return float(value[:-1])

    if value.endswith("d"):
        return float(value[:-1]) * 8

    return np.nan


def classify_plan_size(row):
    """6번에서 정한 PLAN Size 적용"""
    hours = row["orig_hours"]

    if pd.isna(hours):
        return np.nan

    rule = PLAN_SIZE_RULES[row["category_type"]]

    if hours <= rule["S_MAX"]:
        return "S"

    if hours <= rule["M_MAX"]:
        return "M"

    return "L"


# --------------------------------------------------
# 1. 데이터 읽기
# --------------------------------------------------

issues = pd.read_csv(DATA_DIR / "jira_issues.csv")
people = pd.read_csv(DATA_DIR / "people.csv")
calendar = pd.read_csv(DATA_DIR / "calendar.csv")

issues["started"] = pd.to_datetime(issues["started"])
issues["resolved"] = pd.to_datetime(issues["resolved"])
calendar["date"] = pd.to_datetime(calendar["date"])


# --------------------------------------------------
# 2. 담당자 role / availability 연결
# --------------------------------------------------

role_map = people.set_index("person")["role"]
availability_map = people.set_index("person")["availability"]

issues["role"] = issues["assignee"].map(role_map)
issues["availability"] = issues["assignee"].map(
    availability_map
)

issues["orig_hours"] = issues["orig_estimate"].map(
    to_hours
)


# --------------------------------------------------
# 3. 분석 대상
# --------------------------------------------------

target = issues[
    issues["fix_version"].isin(CLOSED_VERSIONS)
    & issues["status"].eq("Done")
].copy()


# --------------------------------------------------
# 4. 영업일 계산에 사용할 휴일 / PTO
# --------------------------------------------------

holidays = set(
    calendar.loc[
        calendar["type"].eq("holiday"),
        "date"
    ].dt.date
)

pto = (
    calendar[
        calendar["type"].eq("pto")
    ]
    .groupby("target")["date"]
    .apply(lambda x: set(x.dt.date))
    .to_dict()
)


def count_workdays(start, end, person=None):
    """
    start ~ end를 포함해서 실제 작업 가능한 영업일 계산.
    주말 / 공휴일 / 해당 담당자 PTO 제외.
    """
    if pd.isna(start) or pd.isna(end):
        return np.nan

    days = pd.date_range(start, end)

    person_pto = pto.get(person, set())

    count = 0

    for day in days:
        if day.weekday() >= 5:
            continue

        if day.date() in holidays:
            continue

        if day.date() in person_pto:
            continue

        count += 1

    return count


def business_day_gap(start, end):
    """
    두 날짜 사이의 영업일 차이.
    공휴일과 주말 제외.
    """
    if pd.isna(start) or pd.isna(end):
        return np.nan

    if end < start:
        return -business_day_gap(end, start)

    if start == end:
        return 0

    days = pd.date_range(
        start,
        end - pd.Timedelta(days=1),
    )

    return sum(
        day.weekday() < 5
        and day.date() not in holidays
        for day in days
    )


# ==================================================
# 분석 1.
# 기획 완료 → 개발 착수 기간
# ==================================================

planner = target[
    target["role"].eq("planner")
    & target["epic_link"].notna()
    & target["resolved"].notna()
    & target["orig_hours"].notna()
].copy()

developer = target[
    target["role"].isin(["server", "client"])
    & target["epic_link"].notna()
    & target["started"].notna()
].copy()

planner["size"] = planner.apply(
    classify_plan_size,
    axis=1,
)

review_rows = []

for _, plan_row in planner.iterrows():

    # 같은 버전 + 같은 작업에 연결된 개발 이슈
    dev_rows = developer[
        developer["fix_version"].eq(
            plan_row["fix_version"]
        )
        & developer["epic_link"].eq(
            plan_row["epic_link"]
        )
    ]

    if dev_rows.empty:
        continue

    first_dev_start = dev_rows["started"].min()

    gap = business_day_gap(
        plan_row["resolved"],
        first_dev_start,
    )

    # 개발이 기획 완료 전에 이미 시작된 병행 사례는
    # "기획 완료 후 검수기간" 분석 대상에서 제외
    if gap < 0:
        continue

    review_rows.append({
        "issue_key": plan_row["issue_key"],
        "category_type": plan_row["category_type"],
        "size": plan_row["size"],
        "plan_resolved": plan_row["resolved"],
        "dev_started": first_dev_start,
        "gap_days": gap,
    })


review = pd.DataFrame(review_rows)

review_summary = (
    review
    .groupby("size")["gap_days"]
    .agg(
        count="count",
        median="median",
        p75=lambda x: x.quantile(0.75),
    )
)

print("\n=== 기획 완료 → 개발 착수 ===")
print(review_summary)


# ==================================================
# 분석 2.
# 예상 작업기간 → 실제 경과기간
# ==================================================

planner_duration = target[
    target["role"].eq("planner")
    & target["orig_hours"].notna()
    & target["availability"].notna()
    & target["started"].notna()
    & target["resolved"].notna()
].copy()


# 하루 실제 투입 가능시간
# 예: availability 0.8 → 8h × 0.8 = 6.4h/day
planner_duration["expected_days"] = (
    planner_duration["orig_hours"]
    / (
        8
        * planner_duration["availability"]
    )
)


planner_duration["elapsed_workdays"] = (
    planner_duration.apply(
        lambda row: count_workdays(
            row["started"],
            row["resolved"],
            row["assignee"],
        ),
        axis=1,
    )
)


planner_duration["duration_ratio"] = (
    planner_duration["elapsed_workdays"]
    / planner_duration["expected_days"]
)


ratio = planner_duration["duration_ratio"]

print("\n=== 기획 예상기간 vs 실제 경과기간 ===")

print(f"분석 대상: {len(ratio)}건")
print(f"예상보다 오래 걸린 건: {(ratio > 1).sum()}건")
print(f"예상 이하인 건: {(ratio <= 1).sum()}건")

print(
    f"중앙값: "
    f"{ratio.median():.3f}"
)

print(
    f"75% 지점: "
    f"{ratio.quantile(0.75):.3f}"
)


print("\n=== 주요 확인 컬럼 ===")

print(
    planner_duration[
        [
            "issue_key",
            "assignee",
            "orig_hours",
            "availability",
            "expected_days",
            "elapsed_workdays",
            "duration_ratio",
        ]
    ].to_string(index=False)
)