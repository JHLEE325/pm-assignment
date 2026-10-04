from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path("data/source")

AS_OF = pd.Timestamp("2026-01-26")

VERSIONS = [
    "v1.3",
    "v1.4",
    "v1.5",
    "v1.6",
    "v1.7",
    "v1.8",
    "v1.9",
    "v2.0",
]

SCHEDULE = {
    "v1.3": ("2024-09-05", "2024-09-11", "2024-09-19"),
    "v1.4": ("2024-11-07", "2024-11-07", "2024-11-15"),
    "v1.5": ("2025-01-16", "2025-01-31", "2025-02-04"),
    "v1.6": ("2025-03-13", "2025-03-18", "2025-03-18"),
    "v1.7": ("2025-05-15", "2025-05-23", "2025-05-30"),
    "v1.8": ("2025-09-04", "2025-09-15", "2025-10-10"),
    "v1.9": ("2025-11-06", "2025-11-17", "2025-11-17"),
    "v2.0": ("2026-01-08", "2026-01-19", "2026-02-06"),
}


# 1. 데이터 읽기
issues = pd.read_csv(DATA_DIR / "jira_issues.csv")
worklog = pd.read_csv(DATA_DIR / "jira_worklog.csv")


# 2. worklog 시간 단위 통일
worklog["date"] = pd.to_datetime(worklog["date"])

worklog["hours"] = np.where(
    worklog["unit"].eq("d"),
    worklog["time_spent"] * 8,
    worklog["time_spent"],
)


# 3. 이슈의 fix_version을 worklog에 연결
version_map = issues.set_index("issue_key")["fix_version"]

worklog["fix_version"] = worklog["issue_key"].map(version_map)


# 4. 버전별 추세 계산
rows = []

for version in VERSIONS:

    planned, actual, close = [
        pd.Timestamp(x)
        for x in SCHEDULE[version]
    ]

    # 기준일보다 Jira Close가 뒤라면 기준일까지의 값만 사용
    cutoff = min(close, AS_OF)

    # 복수 Version 이슈는 A-1에서 귀속이 모호하다고 판단했으므로
    # 정확히 하나의 Version에 속한 이슈만 사용
    version_issues = issues[
        issues["fix_version"].eq(version)
    ].copy()

    version_worklog = worklog[
        worklog["fix_version"].eq(version)
        & (worklog["date"] <= cutoff)
    ].copy()

    logged_issue_keys = set(
        version_worklog["issue_key"].unique()
    )

    issue_count = len(version_issues)

    with_worklog = (
        version_issues["issue_key"]
        .isin(logged_issue_keys)
        .sum()
    )

    rows.append({
        "version": version,
        "issue_count": issue_count,
        "worklog_coverage": with_worklog / issue_count,
        "recorded_md": version_worklog["hours"].sum() / 8,
        "release_delay_days": (actual - planned).days,
        "jira_close_delay_days": (close - actual).days,
        "status": (
            "final"
            if close <= AS_OF
            else "provisional"
        ),
    })


trend = pd.DataFrame(rows)

print("\n=== 버전별 추세 ===")

print(
    trend.to_string(
        index=False,
        formatters={
            "worklog_coverage": lambda x: f"{x:.1%}",
            "recorded_md": lambda x: f"{x:.1f}",
        }
    )
)