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


# A-2에서 정의한 Category × Process별 Size 기준
# 최초 예상 공수(orig_estimate)를 시간 단위로 환산하여 적용한다.
#
# PLAN / DEV:
#   과거 orig_estimate 분포의 1/3, 2/3 지점을 기준으로 산정
#
# ART:
#   현재 데이터만으로 충분한 경계를 구하기 어려워
#   A-2에서 baseline 대표값의 중간점을 초기 기준으로 사용
SIZE_RULES = {
    ("CONTENT", "PLAN"): {
        "S_MAX": 32,
        "M_MAX": 56,
    },
    ("CONTENT", "DEV"): {
        "S_MAX": 32,
        "M_MAX": 88,
    },
    ("SYSTEM", "PLAN"): {
        "S_MAX": 72,
        "M_MAX": 136,
    },
    ("SYSTEM", "DEV"): {
        "S_MAX": 72,
        "M_MAX": 192,
    },

    # CONTENT ART
    # S <= 7MD, M <= 18MD
    # 1MD = 8h
    ("CONTENT", "ART"): {
        "S_MAX": 56,
        "M_MAX": 144,
    },

    # SYSTEM ART
    # S <= 4MD, M <= 9MD
    ("SYSTEM", "ART"): {
        "S_MAX": 32,
        "M_MAX": 72,
    },
}


VERSION_SCHEDULE = {
    "v1.3": (
        "2024-09-05",
        "2024-09-11",
        "2024-09-19",
    ),
    "v1.4": (
        "2024-11-07",
        "2024-11-07",
        "2024-11-15",
    ),
    "v1.5": (
        "2025-01-16",
        "2025-01-31",
        "2025-02-04",
    ),
    "v1.6": (
        "2025-03-13",
        "2025-03-18",
        "2025-03-18",
    ),
    "v1.7": (
        "2025-05-15",
        "2025-05-23",
        "2025-05-30",
    ),
    "v1.8": (
        "2025-09-04",
        "2025-09-15",
        "2025-10-10",
    ),
    "v1.9": (
        "2025-11-06",
        "2025-11-17",
        "2025-11-17",
    ),
    "v2.0": (
        "2026-01-08",
        "2026-01-19",
        "2026-02-06",
    ),
    "v2.1": (
        "2026-03-12",
        None,
        None,
    ),
}


def estimate_to_seconds(value):
    """
    orig_estimate의 h / d 단위를 초 단위로 변환한다.

    예:
    8h -> 28,800초
    1d -> 28,800초

    본 과제에서는 1d = 8h로 정의한다.
    """
    if pd.isna(value):
        return None

    value = str(value).strip().lower()

    if value.endswith("h"):
        return int(
            float(value[:-1])
            * 3600
        )

    if value.endswith("d"):
        return int(
            float(value[:-1])
            * 8
            * 3600
        )

    return None


def worklog_to_seconds(time_spent, unit):
    """
    Worklog의 time_spent를 초 단위로 통일한다.
    """
    if unit == "d":
        return int(
            float(time_spent)
            * 8
            * 3600
        )

    return int(
        float(time_spent)
        * 3600
    )


def classify_size(
    category_type,
    process,
    orig_estimate,
):
    """
    A-2에서 정의한 객관적 Size 기준을 적용한다.

    Jira에 기존 입력된 size_label을 사용하지 않고,
    Category × Process × orig_estimate 기준으로
    S / M / L을 다시 계산한다.

    기준을 적용할 수 없는 경우에는 None을 반환하며,
    조회 단계에서 UNCLASSIFIED로 별도 표시한다.
    """
    estimate_seconds = estimate_to_seconds(
        orig_estimate
    )

    if estimate_seconds is None:
        return None

    if process is None:
        return None

    if pd.isna(category_type):
        return None

    category_type = str(
        category_type
    ).strip().upper()

    rule = SIZE_RULES.get(
        (
            category_type,
            process,
        )
    )

    if rule is None:
        return None

    estimate_hours = (
        estimate_seconds
        / 3600
    )

    if estimate_hours <= rule["S_MAX"]:
        return "S"

    if estimate_hours <= rule["M_MAX"]:
        return "M"

    return "L"


# --------------------------------------------------
# DB 초기화
# --------------------------------------------------

DB_PATH.parent.mkdir(
    parents=True,
    exist_ok=True,
)

# B-7 실행 결과를 항상 재현할 수 있도록
# 기존 DB가 있으면 삭제 후 새로 생성한다.
if DB_PATH.exists():
    DB_PATH.unlink()


conn = sqlite3.connect(
    DB_PATH
)

with SCHEMA_PATH.open(
    encoding="utf-8"
) as f:
    conn.executescript(
        f.read()
    )


# --------------------------------------------------
# CSV 읽기
# --------------------------------------------------

issues = pd.read_csv(
    DATA_DIR / "jira_issues.csv"
)

worklogs = pd.read_csv(
    DATA_DIR / "jira_worklog.csv"
)

people = pd.read_csv(
    DATA_DIR / "people.csv"
)

calendar = pd.read_csv(
    DATA_DIR / "calendar.csv"
)


# --------------------------------------------------
# 담당자 → Process Mapping
# --------------------------------------------------

person_process_map = {
    row["person"]:
        ROLE_TO_PROCESS.get(
            row["role"]
        )
    for _, row in people.iterrows()
}


# --------------------------------------------------
# person
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

            # 제공 CSV에는 Jira accountId가 없으므로
            # 현재 적재 테스트에서는 NULL
            None,

            row["role"],

            ROLE_TO_PROCESS.get(
                row["role"]
            ),

            row["part"],
            row["leader"],

            (
                None
                if pd.isna(
                    row["availability"]
                )
                else float(
                    row["availability"]
                )
            ),

            row["employment"],
        ),
    )


# --------------------------------------------------
# version
# --------------------------------------------------

for (
    version_name,
    dates,
) in VERSION_SCHEDULE.items():

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

            # 제공 CSV에는 Jira Version ID가 없으므로
            # 현재 적재 테스트에서는 NULL
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

    assignee = (
        None
        if pd.isna(
            row["assignee"]
        )
        else row["assignee"]
    )

    process = (
        person_process_map.get(
            assignee
        )
    )

    # Jira의 기존 size_label이 아니라
    # A-2 기준으로 객관적 Size를 다시 계산
    size_class = classify_size(
        row["category_type"],
        process,
        row["orig_estimate"],
    )

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

            # 제공 CSV에는 Jira Issue ID가 없으므로
            # 현재 적재 테스트에서는 NULL
            None,

            row["type"],
            row["summary"],

            (
                None
                if pd.isna(
                    row["epic_link"]
                )
                else row["epic_link"]
            ),

            row["category_type"],

            # Jira에 기존 입력된 주관적 Size
            row["size_label"],

            # A-2 기준으로 다시 계산한 Size
            size_class,

            assignee,

            row["status"],
            row["created"],

            (
                None
                if pd.isna(
                    row["started"]
                )
                else row["started"]
            ),

            (
                None
                if pd.isna(
                    row["resolved"]
                )
                else row["resolved"]
            ),

            estimate_to_seconds(
                row["orig_estimate"]
            ),

            (
                None
                if pd.isna(
                    row["story_points"]
                )
                else float(
                    row["story_points"]
                )
            ),

            int(
                row["reopen_cnt"]
            ),
        ),
    )

    versions = [
        value.strip()
        for value in str(
            row["fix_version"]
        ).split(",")
        if (
            value.strip()
            and value.strip() != "nan"
        )
    ]

    # 복수 Fix Version은 제공 CSV만으로
    # 어느 Version에 실제 공수를 귀속할지 확정할 수 없다.
    #
    # 동일 Worklog가 여러 Version에 중복 집계되는 것을 막기 위해
    # B-7에서는 복수 Version 관계를 Actual MD 집계에서 제외한다.
    include_in_md = (
        1
        if len(versions) == 1
        else 0
    )

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

    # 제공 CSV에는 Jira Worklog ID가 없으므로
    # 적재 테스트용 deterministic ID 생성
    worklog_id = (
        f"csv-{index + 1}"
    )

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


# --------------------------------------------------
# Commit
# --------------------------------------------------

conn.commit()


# --------------------------------------------------
# 적재 결과 확인
# --------------------------------------------------

classified_count = conn.execute(
    """
    SELECT COUNT(*)
    FROM issue
    WHERE size_class IS NOT NULL
    """
).fetchone()[0]

unclassified_count = conn.execute(
    """
    SELECT COUNT(*)
    FROM issue
    WHERE size_class IS NULL
    """
).fetchone()[0]


print("DB 적재 완료")
print(f"issue: {len(issues)}")
print(f"worklog: {len(worklogs)}")
print(f"people: {len(people)}")
print(
    "size_class 분류 완료: "
    f"{classified_count}"
)
print(
    "size_class 미분류: "
    f"{unclassified_count}"
)
print(f"DB: {DB_PATH}")


conn.close()