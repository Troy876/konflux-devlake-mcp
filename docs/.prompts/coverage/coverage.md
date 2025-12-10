# Code Coverage Executive Report - Generation Prompt

Use this prompt to generate the same HTML coverage report with fresh data.

---

## Full Prompt

```
Generate an HTML Code Coverage Executive Report for my project with the following specifications:

**PROJECT INFO:**

- Project Name: [PROJECT_NAME]

- Time Period: Last [X] days

- Date Generated: [DATE]

**REPORT STRUCTURE:**

1. **Header** - Title "Code Coverage Report", project name, period, generation date

2. **Executive Summary (Blue gradient banner)** - 4 KPIs in a row:

   - Overall Coverage %

   - Patch Coverage %

   - Total Lines

   - Number of Repositories

3. **Coverage Trends Section** - Two charts side by side:

   - Overall Coverage Trend (line chart, weighted average across all repos)

   - Patch Coverage Trend (line chart, all repos combined)

4. **Repository Cards** - One card per repository containing:

   - Header with repo name, org, and total lines

   - Two charts: Patch Coverage Trend (line) + Coverage by Test Type (doughnut)

   - Metrics row: Unit Test Coverage, E2E Test Coverage

**DESIGN REQUIREMENTS:**

- Clean, professional, executive-friendly light theme

- Max width: 1400px

- Blue gradient (#1e40af → #3b82f6) for headers and executive summary

- Charts use Chart.js

- Fully responsive (tablet/mobile breakpoints)

- Print-ready styling

**IMPORTANT NOTES:**

- Same repo with multiple test types = one card showing all test types

- Don't sum lines across test types (same codebase)

- Charts should not drop to 0 - use null for missing data with spanGaps

- Coverage colors: green (≥70%), yellow (50-70%), red (<50%)

- Each repository card must show Unit Test Coverage and E2E Test Coverage metrics

- Unit test types: any test type containing "unit" (case-insensitive, e.g., "unit", "unit-tests", "unittests", "unit-tests-integration")

- E2E test types: any test type containing "e2e" (case-insensitive, e.g., "e2e", "e2e-tests", "e2e-integration")
```

---

## Quick Prompt (for regenerating with fresh data)

```
Using the MCP server, get fresh Codecov data for project "test" for the last 30 days and regenerate the HTML executive coverage report (Code_Coverage_Report.html) with:

- Executive summary KPIs

- Coverage & Patch trend charts (all repos combined)

- Repository cards with individual patch trends and coverage by test type

- No "Coverage by Test Type" section or "Lines of Code by Repository" chart

- Unit Test Coverage and E2E Test Coverage metrics in each card

- Clean, professional executive design
```

---

## Database Queries

### 1. Overall Stats (for Executive Summary KPIs)

**IMPORTANT**: This query calculates overall coverage correctly by:
- Using MAX(lines_total) per repo (since all test types in the same repo have the same codebase)
- Using MAX(lines_covered) per repo (to get the best coverage per repo)
- Then summing across all repos to get total lines and total covered lines

```sql
SELECT 
  COUNT(DISTINCT repo_id) as total_components,
  SUM(max_lines_total) as total_lines,
  ROUND(SUM(max_lines_covered) * 100.0 / NULLIF(SUM(max_lines_total), 0), 2) as overall_coverage
FROM (
  SELECT 
    repo_id,
    MAX(lines_total) as max_lines_total,
    MAX(lines_covered) as max_lines_covered
  FROM (
    SELECT c.repo_id, c.flag_name, c.lines_covered, c.lines_total
    FROM _tool_codecov_coverages c
    INNER JOIN project_mapping pm ON c.repo_id = pm.row_id AND pm.`table` = '_tool_codecov_repos'
    WHERE pm.project_name = 'test' AND c.lines_total > 0
      AND c.coverage_percentage IS NOT NULL
      AND c.commit_timestamp = (
        SELECT MAX(c2.commit_timestamp) FROM _tool_codecov_coverages c2 
        WHERE c2.repo_id = c.repo_id AND c2.flag_name = c.flag_name 
          AND c2.lines_total > 0 AND c2.coverage_percentage IS NOT NULL
      )
  ) latest
  GROUP BY repo_id
) per_repo
```

### 2. Average Patch Coverage (for Executive Summary)

**IMPORTANT**: This calculates the average patch coverage across all repos and commits in the last 30 days. The patch value represents the percentage of new/changed lines covered by tests.

```sql
SELECT 
  ROUND(AVG(comp.patch), 2) as avg_patch_coverage
FROM _tool_codecov_comparisons comp
INNER JOIN _tool_codecov_commits cm ON comp.connection_id = cm.connection_id 
  AND comp.repo_id = cm.repo_id AND comp.commit_sha = cm.commit_sha
INNER JOIN project_mapping pm ON comp.repo_id = pm.row_id AND pm.`table` = '_tool_codecov_repos'
WHERE pm.project_name = 'test' AND comp.patch IS NOT NULL
  AND cm.commit_timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
```

### 3. Per-Repository Data with All Test Types

```sql
SELECT 
  SUBSTRING_INDEX(repo_id, '/', -1) as component,
  SUBSTRING_INDEX(repo_id, '/', 1) as org,
  c.repo_id,
  c.flag_name as test_type,
  ROUND(c.coverage_percentage, 2) as coverage_percentage,
  c.lines_total as `lines`,
  c.lines_covered as covered,
  (c.lines_total - c.lines_covered) as uncovered,
  c.commit_timestamp as last_updated
FROM _tool_codecov_coverages c
INNER JOIN project_mapping pm ON c.repo_id = pm.row_id AND pm.`table` = '_tool_codecov_repos'
  WHERE pm.project_name = 'test' AND c.lines_total > 0
    AND c.coverage_percentage IS NOT NULL
    AND c.commit_timestamp = (
      SELECT MAX(c2.commit_timestamp) FROM _tool_codecov_coverages c2 
      WHERE c2.repo_id = c.repo_id AND c2.flag_name = c.flag_name 
        AND c2.lines_total > 0 AND c2.coverage_percentage IS NOT NULL
    )
ORDER BY c.repo_id, c.flag_name
```

### 4. Daily Coverage Trend (Overall - All Repos Combined)

**IMPORTANT**: This calculates daily coverage by summing lines_covered and lines_total across all repos per day. For repos with multiple test types, we use MAX(lines_total) per repo per day to avoid double-counting.

```sql
SELECT 
  date,
  ROUND(SUM(max_lines_covered) * 100.0 / NULLIF(SUM(max_lines_total), 0), 2) as daily_coverage
FROM (
  SELECT 
    DATE(c.commit_timestamp) as date,
    c.repo_id,
    MAX(c.lines_total) as max_lines_total,
    MAX(c.lines_covered) as max_lines_covered
  FROM _tool_codecov_coverages c
  INNER JOIN project_mapping pm ON c.repo_id = pm.row_id AND pm.`table` = '_tool_codecov_repos'
  WHERE pm.project_name = 'test' AND c.lines_total > 0
    AND c.coverage_percentage IS NOT NULL
    AND c.commit_timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
  GROUP BY DATE(c.commit_timestamp), c.repo_id
) daily_per_repo
GROUP BY date
ORDER BY date
```

### 5. Daily Patch Trend (Overall - All Repos Combined)

```sql
SELECT 
  DATE(cm.commit_timestamp) as date,
  ROUND(AVG(comp.patch), 2) as daily_patch
FROM _tool_codecov_comparisons comp
INNER JOIN _tool_codecov_commits cm ON comp.connection_id = cm.connection_id 
  AND comp.repo_id = cm.repo_id AND comp.commit_sha = cm.commit_sha
INNER JOIN project_mapping pm ON comp.repo_id = pm.row_id AND pm.`table` = '_tool_codecov_repos'
WHERE pm.project_name = 'test' AND comp.patch IS NOT NULL
  AND cm.commit_timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(cm.commit_timestamp)
ORDER BY date
```

### 6. Per-Repository Patch Trends (for Individual Repository Cards)

```sql
SELECT 
  comp.repo_id,
  DATE(cm.commit_timestamp) as date,
  ROUND(AVG(comp.patch), 2) as daily_patch
FROM _tool_codecov_comparisons comp
INNER JOIN _tool_codecov_commits cm ON comp.connection_id = cm.connection_id 
  AND comp.repo_id = cm.repo_id AND comp.commit_sha = cm.commit_sha
INNER JOIN project_mapping pm ON comp.repo_id = pm.row_id AND pm.`table` = '_tool_codecov_repos'
WHERE pm.project_name = 'test' AND comp.patch IS NOT NULL
  AND cm.commit_timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY comp.repo_id, DATE(cm.commit_timestamp)
ORDER BY comp.repo_id, date
```

### 7. Get Available Projects

```sql
SELECT DISTINCT pm.project_name, COUNT(DISTINCT c.repo_id) as repo_count
FROM _tool_codecov_coverages c
INNER JOIN project_mapping pm ON c.repo_id = pm.row_id AND pm.`table` = '_tool_codecov_repos'
WHERE c.lines_total > 0
GROUP BY pm.project_name
ORDER BY repo_count DESC
```

---

## Data Processing Notes

1. **Repository Organization**: Group query results by `repo_id` to create one card per repository

2. **Test Type Matching**: 
   - Unit tests: match any test type containing "unit" (case-insensitive)
   - E2E tests: match any test type containing "e2e" (case-insensitive)

3. **Total Lines**: Use the maximum `lines_total` per repository (don't sum across test types - same codebase)

4. **Overall Coverage Calculation**:
   - **CRITICAL**: When calculating overall coverage across all repos, we must avoid double-counting lines
   - For each repo: Use MAX(lines_total) and MAX(lines_covered) since all test types share the same codebase
   - Then sum across all repos: SUM(max_lines_covered) / SUM(max_lines_total) * 100
   - This gives us the true weighted average coverage across all repositories

5. **Patch Coverage Calculation**:
   - Average all patch coverage values from `_tool_codecov_comparisons` table
   - Patch coverage represents the percentage of new/changed lines covered by tests
   - This is already a percentage, so we just average across all commits in the time period

6. **Coverage Calculation for Repository Cards**: For each repository card, find the unit test and e2e test coverage separately

7. **Patch Trends**: Group patch trend data by `repo_id` for individual repository charts

8. **Chart Data**: Use `spanGaps: true` in Chart.js to handle missing data points without dropping to 0

---

## Report Generation Steps

1. Execute all 7 queries above based on the project
2. Process query results to organize data by repository
3. Generate HTML with:
   - Executive summary from queries 1 and 2
   - Trend charts from queries 4 and 5
   - Repository cards from queries 3 and 6
4. For each repository card:
   - Extract unit test coverage (from query 3 results)
   - Extract e2e test coverage (from query 3 results)
   - Get patch trend data (from query 6 results)
   - Create charts and display metrics
