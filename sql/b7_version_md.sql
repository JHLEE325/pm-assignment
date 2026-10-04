SELECT
    iv.version_name,
    i.category_type,
    COALESCE(i.size_class, i.size_label_raw) AS size,

    ROUND(
        SUM(w.time_spent_seconds) / 28800.0,
        3
    ) AS actual_md

FROM worklog w

JOIN issue i
    ON i.issue_key = w.issue_key

JOIN issue_version iv
    ON iv.issue_key = i.issue_key
   AND iv.include_in_md = 1

JOIN version v
    ON v.version_name = iv.version_name

WHERE date(w.started_at) <= date(
    CASE
        WHEN v.jira_closed_at IS NOT NULL
         AND date(v.jira_closed_at) <= date('2026-01-26')
        THEN v.jira_closed_at
        ELSE '2026-01-26'
    END
)

GROUP BY
    iv.version_name,
    i.category_type,
    COALESCE(i.size_class, i.size_label_raw)

ORDER BY
    iv.version_name,
    i.category_type,
    size;