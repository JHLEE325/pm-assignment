from pathlib import Path
import sqlite3

import pandas as pd


DATA_DIR = Path("data/source")
DB_PATH = Path("output/horang_pm.db")
SCHEMA_PATH = Path("sql/schema.sql")


ROLE_TO_PROCESS = {
    "planner": "PLAN",
    "server": "DEV",
    "client": "DEV",
    "art": "ART",
}


VERSION_SCHEDULE = {
    "v1.3": ("2024-09-05", "2024-09-11", "2024-09-19"),
    "v1.4": ("2024-11-07", "2024-11-07", "2024-11-15"),
    "v1.5": ("2025-01-16", "2025-01-31", "2025-02-04"),
    "v1.6": ("2025-03-13", "2025-03-18", "2025-03-18"),
    "v1.7": ("2025-05-15", "2025-05-23", "2025-05-30"),
    "v1.8": ("2025-09-04", "2025-09-15", "2025-10-10"),
    "v1.9": ("2025-11-06", "2025-11-17", "2025-11-17"),
    "v2.0": ("2026-01-08", "2026-01-19", "2026-02-06"),
    "v2.1": ("2026-03-12", None, None),
}


def estimate_to_seconds(value):
    if pd.isna(value):
        return None

    value = str(value).strip().lower()

    if value.endswith("h"):
        return int(float(value[:-1]) * 3600)

    if value.endswith("d"):
        return int(float(value[:-1]) * 8 * 3600)

    return None


def worklog_to_seconds(time_spent, unit):
    if unit == "d":
        return int(float(time_spent) * 8 * 3600)

    return int(float(time_spent) * 3600)


DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# 재현성을 위해 B-7 실행 시 DB를 새로 생성
if DB_PATH.exists():
    DB_PATH.unlink()

conn = sqlite3.connect(DB_PATH)

with SCHEMA_PATH.open(encoding="utf-8") as f:
    conn.executescript(f.read())


issues = pd.read_csv(DATA_DIR / "jira_issues.csv")
worklogs = pd.read_csv(DATA_DIR / "jira_worklog.csv")
people = pd.read_csv(DATA_DIR / "people.csv")
calendar = pd.read_csv(DATA_DIR / "calendar.csv")


# --------------------------------------------------
# people
# --------------------------------------------------

for _, row in people.iterrows():
    conn.execute(
        """
        INSERT INTO person (
            person_key,
            jira_account_id,
            role,
            process,
            part,
            leader,
            availability,
            employment
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["person"],
            None,
            row["role"],
            ROLE_TO_PROCESS.get(row["role"]),
            row["part"],
            row["leader"],
            None if pd.isna(row["availability"])
            else float(row["availability"]),
            row["employment"],
        ),
    )


# --------------------------------------------------
# version
# --------------------------------------------------

for version_name, dates in VERSION_SCHEDULE.items():
    planned, actual, closed = dates

    conn.execute(
        """
        INSERT INTO version (
            version_name,
            jira_version_id,
            planned_release_date,
            actual_release_date,
            jira_closed_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            version_name,
            None,
            planned,
            actual,
            closed,
        ),
    )


# --------------------------------------------------
# issue + issue_version
# --------------------------------------------------

for _, row in issues.iterrows():

    conn.execute(
        """
        INSERT INTO issue (
            issue_key,
            jira_issue_id,
            issue_type,
            summary,
            parent_key,
            category_type,
            size_label_raw,
            size_class,
            assignee_person_key,
            status,
            created_at,
            started_at,
            resolved_at,
            original_estimate_seconds,
            story_points,
            reopen_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["issue_key"],
            None,
            row["type"],
            row["summary"],
            None if pd.isna(row["epic_link"])
            else row["epic_link"],
            row["category_type"],
            row["size_label"],

            # 제공 CSV에는 A-2에서 다시 계산한 size_class가
            # 별도 컬럼으로 존재하지 않으므로 현재는 NULL
            None,

            None if pd.isna(row["assignee"])
            else row["assignee"],
            row["status"],
            row["created"],
            None if pd.isna(row["started"])
            else row["started"],
            None if pd.isna(row["resolved"])
            else row["resolved"],
            estimate_to_seconds(row["orig_estimate"]),
            None if pd.isna(row["story_points"])
            else float(row["story_points"]),
            int(row["reopen_cnt"]),
        ),
    )

    versions = [
        value.strip()
        for value in str(row["fix_version"]).split(",")
        if value.strip() and value.strip() != "nan"
    ]

    # 복수 Fix Version은 어느 버전에 귀속할지 확정할 수 없으므로
    # MD 집계에서는 제외
    include_in_md = 1 if len(versions) == 1 else 0

    for version_name in versions:
        conn.execute(
            """
            INSERT INTO issue_version (
                issue_key,
                version_name,
                include_in_md
            )
            VALUES (?, ?, ?)
            """,
            (
                row["issue_key"],
                version_name,
                include_in_md,
            ),
        )


# --------------------------------------------------
# worklog
# --------------------------------------------------

for index, row in worklogs.iterrows():

    # 제공 CSV에는 Jira worklog_id가 없으므로
    # 적재 테스트용 deterministic ID 생성
    worklog_id = f"csv-{index + 1}"

    conn.execute(
        """
        INSERT INTO worklog (
            worklog_id,
            issue_key,
            author_person_key,
            started_at,
            time_spent_seconds
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            worklog_id,
            row["issue_key"],
            row["author"],
            row["date"],
            worklog_to_seconds(
                row["time_spent"],
                row["unit"],
            ),
        ),
    )


# --------------------------------------------------
# calendar
# --------------------------------------------------

for _, row in calendar.iterrows():
    conn.execute(
        """
        INSERT INTO calendar_day (
            date,
            target,
            type
        )
        VALUES (?, ?, ?)
        """,
        (
            row["date"],
            row["target"],
            row["type"],
        ),
    )


conn.commit()


print("DB 적재 완료")
print(f"issue: {len(issues)}")
print(f"worklog: {len(worklogs)}")
print(f"people: {len(people)}")
print(f"DB: {DB_PATH}")

conn.close()