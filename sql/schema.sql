PRAGMA foreign_keys = ON;


-- =========================================================
-- RAW
-- =========================================================

CREATE TABLE raw_jira_payload (
    raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    source_key TEXT,
    collected_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX idx_raw_jira_payload_collected
ON raw_jira_payload(entity_type, collected_at);


-- =========================================================
-- REFINED / DIMENSION
-- =========================================================

CREATE TABLE person (
    person_key TEXT PRIMARY KEY,
    jira_account_id TEXT UNIQUE,

    role TEXT NOT NULL,
    process TEXT,

    part TEXT,
    leader TEXT,

    availability REAL,
    employment TEXT,

    CHECK (
        process IS NULL
        OR process IN ('PLAN', 'DEV', 'ART')
    ),

    CHECK (
        availability IS NULL
        OR availability BETWEEN 0 AND 1
    )
);


CREATE TABLE version (
    version_name TEXT PRIMARY KEY,
    jira_version_id TEXT UNIQUE,

    planned_release_date TEXT,
    actual_release_date TEXT,
    jira_closed_at TEXT
);


CREATE TABLE calendar_day (
    date TEXT NOT NULL,
    target TEXT NOT NULL,
    type TEXT NOT NULL,

    PRIMARY KEY (date, target, type)
);


-- Jira Custom Field ID를 코드에 직접 고정하지 않기 위한 매핑
CREATE TABLE jira_field_map (
    semantic_key TEXT PRIMARY KEY,
    jira_field_id TEXT NOT NULL,

    expected_type TEXT,
    active INTEGER NOT NULL DEFAULT 1,

    updated_at TEXT
);


-- =========================================================
-- REFINED / ISSUE
-- =========================================================

CREATE TABLE issue (
    issue_key TEXT PRIMARY KEY,
    jira_issue_id TEXT UNIQUE,

    issue_type TEXT,
    summary TEXT,

    parent_key TEXT,

    category_type TEXT,

    -- Jira 원본에서 받은 주관적 Size
    size_label_raw TEXT,

    -- A-2 기준으로 다시 계산한 Size
    size_class TEXT,

    assignee_person_key TEXT,

    status TEXT,

    created_at TEXT,
    started_at TEXT,
    resolved_at TEXT,

    original_estimate_seconds INTEGER,
    story_points REAL,
    reopen_count INTEGER DEFAULT 0,

    FOREIGN KEY (assignee_person_key)
        REFERENCES person(person_key),

    CHECK (
        category_type IS NULL
        OR category_type IN ('SYSTEM', 'CONTENT')
    ),

    CHECK (
        size_class IS NULL
        OR size_class IN ('S', 'M', 'L')
    )
);


CREATE TABLE issue_version (
    issue_key TEXT NOT NULL,
    version_name TEXT NOT NULL,

    -- 실제 Version MD 집계에 사용할 관계인지 여부
    include_in_md INTEGER NOT NULL DEFAULT 1,

    PRIMARY KEY (issue_key, version_name),

    FOREIGN KEY (issue_key)
        REFERENCES issue(issue_key),

    FOREIGN KEY (version_name)
        REFERENCES version(version_name),

    CHECK (include_in_md IN (0, 1))
);


CREATE INDEX idx_issue_version_version
ON issue_version(version_name, issue_key);


CREATE INDEX idx_issue_assignee_period
ON issue(
    assignee_person_key,
    started_at,
    resolved_at
);


-- =========================================================
-- REFINED / WORKLOG
-- =========================================================

CREATE TABLE worklog (
    worklog_id TEXT PRIMARY KEY,

    issue_key TEXT NOT NULL,
    author_person_key TEXT,

    started_at TEXT NOT NULL,
    time_spent_seconds INTEGER NOT NULL,

    FOREIGN KEY (issue_key)
        REFERENCES issue(issue_key),

    FOREIGN KEY (author_person_key)
        REFERENCES person(person_key),

    CHECK (time_spent_seconds >= 0)
);


CREATE INDEX idx_worklog_issue
ON worklog(issue_key);


CREATE INDEX idx_worklog_author_time
ON worklog(author_person_key, started_at);


-- =========================================================
-- REFINED / STATUS HISTORY
-- =========================================================

CREATE TABLE issue_status_history (
    issue_key TEXT NOT NULL,
    history_id TEXT NOT NULL,

    changed_at TEXT NOT NULL,

    from_status TEXT,
    to_status TEXT,

    PRIMARY KEY (issue_key, history_id),

    FOREIGN KEY (issue_key)
        REFERENCES issue(issue_key)
);


CREATE INDEX idx_status_history_issue_time
ON issue_status_history(
    issue_key,
    changed_at
);


-- =========================================================
-- SUMMARY VIEW
-- =========================================================

CREATE VIEW vw_version_category_size_md AS

SELECT
    iv.version_name,
    i.category_type,
    i.size_class,
    p.process,

    ROUND(
        SUM(w.time_spent_seconds) / 28800.0,
        2
    ) AS actual_md

FROM worklog w

JOIN issue i
    ON i.issue_key = w.issue_key

JOIN issue_version iv
    ON iv.issue_key = i.issue_key
   AND iv.include_in_md = 1

LEFT JOIN person p
    ON p.person_key = w.author_person_key

GROUP BY
    iv.version_name,
    i.category_type,
    i.size_class,
    p.process;