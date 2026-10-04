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

ROLE_TO_PROCESS = {
    "planner": "PLAN",
    "server": "DEV",
    "client": "DEV",
    "art": "ART",
}


def to_hours(value):
    """orig_estimate를 시간 단위로 변환"""
    if pd.isna(value):
        return np.nan

    value = str(value).strip().lower()

    if value.endswith("h"):
        return float(value[:-1])

    if value.endswith("d"):
        return float(value[:-1]) * 8

    return np.nan


# 1. 데이터 읽기
issues = pd.read_csv(DATA_DIR / "jira_issues.csv")
people = pd.read_csv(DATA_DIR / "people.csv")


# 2. assignee의 role을 이용해 공정 구분
person_role = people.set_index("person")["role"]

issues["role"] = issues["assignee"].map(person_role)
issues["process"] = issues["role"].map(ROLE_TO_PROCESS)


# 3. 최초 예상 공수를 시간으로 변환
issues["orig_hours"] = issues["orig_estimate"].map(to_hours)


# 4. 기준일 현재 종료된 버전의 완료 이슈만 사용
#    "v1.8,v1.9" 같은 복수 버전 이슈는 자동 제외됨
target = issues[
    issues["fix_version"].isin(CLOSED_VERSIONS)
    & issues["status"].eq("Done")
    & issues["process"].notna()
].copy()


# 5. category × process별 orig_estimate 분포 확인
summary = (
    target
    .groupby(["category_type", "process"])
    .agg(
        issue_count=("issue_key", "count"),
        estimate_count=("orig_hours", "count"),
        unique_estimate=("orig_hours", "nunique"),
        q33=("orig_hours", lambda x: x.dropna().quantile(1 / 3)),
        median=("orig_hours", "median"),
        q67=("orig_hours", lambda x: x.dropna().quantile(2 / 3)),
    )
    .reset_index()
)


# 6. 1MD = 8시간이므로 경계를 8시간 단위로 정리
summary["S_max_hours"] = (
    (summary["q33"] / 8).round() * 8
)

summary["M_max_hours"] = (
    (summary["q67"] / 8).round() * 8
)


print(summary.to_string(index=False))


# 필요하면 결과 저장
output_dir = Path("output/a_analysis")
output_dir.mkdir(parents=True, exist_ok=True)

summary.to_csv(
    output_dir / "a2_size_thresholds.csv",
    index=False,
)