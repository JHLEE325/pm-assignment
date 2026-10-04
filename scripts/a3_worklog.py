from pathlib import Path

import pandas as pd


DATA_DIR = Path("data/source")

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


# 1. 데이터 읽기
issues = pd.read_csv(DATA_DIR / "jira_issues.csv")
worklog = pd.read_csv(DATA_DIR / "jira_worklog.csv")
people = pd.read_csv(DATA_DIR / "people.csv")


# 2. 담당자 role → 공정 연결
role_map = people.set_index("person")["role"]

issues["role"] = issues["assignee"].map(role_map)
issues["process"] = issues["role"].map(ROLE_TO_PROCESS)


# 3. 기준일 현재 Jira Close가 완료된 버전만 사용
# Done과 Won't Do 모두 실제 작업 공수가 발생할 수 있으므로 포함
target = issues[
    issues["fix_version"].isin(CLOSED_VERSIONS)
    & issues["status"].isin(["Done", "Won't Do"])
].copy()


# 4. 이슈별 worklog 존재 여부
worklog_issue_keys = set(worklog["issue_key"])

target["has_worklog"] = (
    target["issue_key"].isin(worklog_issue_keys)
)


# 5. 전체 결측률
total = len(target)
with_worklog = target["has_worklog"].sum()
missing = total - with_worklog
missing_rate = missing / total

print("=== 전체 Worklog 결측 ===")
print(f"대상 이슈: {total}")
print(f"worklog 존재: {with_worklog}")
print(f"worklog 없음: {missing}")
print(f"결측률: {missing_rate:.1%}")


# 6. 공정별 결측률
process_summary = (
    target
    .groupby("process")["has_worklog"]
    .agg(
        total="count",
        with_worklog="sum",
    )
)

process_summary["missing"] = (
    process_summary["total"]
    - process_summary["with_worklog"]
)

process_summary["missing_rate"] = (
    process_summary["missing"]
    / process_summary["total"]
)

print("\n=== 공정별 결측률 ===")
print(process_summary)


# 7. 이슈 유형별 결측률
type_summary = (
    target
    .groupby("type")["has_worklog"]
    .agg(
        total="count",
        with_worklog="sum",
    )
)

type_summary["missing"] = (
    type_summary["total"]
    - type_summary["with_worklog"]
)

type_summary["missing_rate"] = (
    type_summary["missing"]
    / type_summary["total"]
)

print("\n=== 이슈 유형별 결측률 ===")
print(type_summary)


# 8. 버전별 결측률
version_summary = (
    target
    .groupby("fix_version")["has_worklog"]
    .agg(
        total="count",
        with_worklog="sum",
    )
)

version_summary["missing"] = (
    version_summary["total"]
    - version_summary["with_worklog"]
)

version_summary["missing_rate"] = (
    version_summary["missing"]
    / version_summary["total"]
)

print("\n=== 버전별 결측률 ===")
print(version_summary)


# 9. worklog가 없는 이슈 중 orig_estimate가 있는 비율
missing_issues = target[
    ~target["has_worklog"]
].copy()

missing_issues["has_orig_estimate"] = (
    missing_issues["orig_estimate"].notna()
)

estimate_available = (
    missing_issues["has_orig_estimate"].sum()
)

print("\n=== Worklog 결측 이슈의 orig_estimate 존재 여부 ===")
print(f"worklog 없는 이슈: {len(missing_issues)}")
print(f"orig_estimate 존재: {estimate_available}")
print(
    "orig_estimate 존재율: "
    f"{estimate_available / len(missing_issues):.1%}"
)