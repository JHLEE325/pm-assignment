WITH RECURSIVE dates(day) AS (

    SELECT date(:from_date)

    UNION ALL

    SELECT date(day, '+1 day')
    FROM dates
    WHERE day < date(:to_date)
),

daily_count AS (

    SELECT
        d.day,

        COUNT(
            DISTINCT i.issue_key
        ) AS concurrent_issue_count

    FROM dates d

    LEFT JOIN issue i
        ON i.assignee_person_key = :person_key
       AND date(i.started_at) <= d.day
       AND date(
            COALESCE(
                i.resolved_at,
                :to_date
            )
       ) >= d.day

    GROUP BY d.day
)

SELECT
    day,
    concurrent_issue_count,

    MAX(concurrent_issue_count) OVER ()
        AS max_concurrent_issue_count

FROM daily_count

ORDER BY day;