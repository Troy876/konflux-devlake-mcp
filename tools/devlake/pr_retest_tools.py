#!/usr/bin/env python3
"""
PR Retest Analysis Tools for Konflux DevLake MCP Server

Contains tools for analyzing pull requests that required manual retest commands
(comments containing "/retest") with comprehensive statistics and insights.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

from mcp.types import Tool
from toon_format import encode as toon_encode

from tools.base.base_tool import BaseTool
from utils.logger import get_logger, log_tool_call


class PRRetestTools(BaseTool):
    """
    PR Retest Analysis tools for Konflux DevLake MCP Server.

    This class provides tools for analyzing pull requests that required
    manual retest commands, identifying patterns, and providing actionable insights.
    """

    def __init__(self, db_connection):
        """
        Initialize PR retest tools.

        Args:
            db_connection: Database connection manager
        """
        super().__init__(db_connection)
        self.logger = get_logger(f"{__name__}.PRRetestTools")

    def get_tools(self) -> List[Tool]:
        """
        Get all PR retest analysis tools.

        Returns:
            List of Tool objects for PR retest operations
        """
        return [
            Tool(
                name="analyze_pr_retests",
                description=(
                    "**Comprehensive PR Retest Analysis Tool** - Analyzes all pull requests "
                    "in a repository within a DevLake project that required manual retest "
                    "commands (comments containing '/retest'). Provides detailed statistics "
                    "including: total count of manual retest comments (excluding bot comments), "
                    "number of PRs affected, average retests per PR, top PRs with most retests "
                    "(including PR title, URL, number of retests, PR duration, changes, and "
                    "status), analysis of root causes and failure patterns, breakdown by PR "
                    "category, timeline visualization data, and actionable recommendations. "
                    "Focuses on technical patterns, systemic issues, and actionable insights "
                    "without financial impacts or personal attribution."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_name": {
                            "type": "string",
                            "description": (
                                "Repository name to analyze (e.g., 'integration-service', "
                                "'build-service', 'release-service', 'infra-deployments'). "
                                "Can be partial match from PR URL."
                            ),
                        },
                        "project_name": {
                            "type": "string",
                            "description": (
                                "DevLake project name (e.g., 'Secureflow - Konflux - Global', "
                                "'Konflux_Pilot_Team'). Leave empty to search all projects."
                            ),
                        },
                        "days_back": {
                            "type": "integer",
                            "description": (
                                "Number of days back to analyze (default: 90 for 3 months). "
                                "Leave empty to analyze all available data."
                            ),
                        },
                        "start_date": {
                            "type": "string",
                            "description": (
                                "Start date for analysis (format: YYYY-MM-DD or "
                                "YYYY-MM-DD HH:MM:SS). Leave empty for no start date limit."
                            ),
                        },
                        "end_date": {
                            "type": "string",
                            "description": (
                                "End date for analysis (format: YYYY-MM-DD or "
                                "YYYY-MM-DD HH:MM:SS). Leave empty for no end date limit."
                            ),
                        },
                        "top_n": {
                            "type": "integer",
                            "description": (
                                "Number of top PRs to return in detailed analysis "
                                "(default: 15, max: 50)"
                            ),
                        },
                        "exclude_bots": {
                            "type": "boolean",
                            "description": (
                                "Exclude bot comments from analysis (default: true). "
                                "Bot detection is based on account_id patterns and "
                                "comment characteristics."
                            ),
                        },
                    },
                    "required": [],
                },
            )
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a PR retest tool by name.

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            TOON-encoded string with tool execution result (token-efficient format)
        """
        try:
            # Log tool call
            log_tool_call(name, arguments, success=True)

            # Route to appropriate tool method
            if name == "analyze_pr_retests":
                result = await self._analyze_pr_retests_tool(arguments)
            else:
                result = {"success": False, "error": f"Unknown PR retest tool: {name}"}

            # Use TOON format for token-efficient serialization (30-60% reduction vs JSON)
            return toon_encode(result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

        except Exception as e:
            self.logger.error(f"PR retest tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": name,
                "arguments": arguments,
            }
            # Use TOON format for error responses as well
            return toon_encode(error_result, {"delimiter": ",", "indent": 2, "lengthMarker": ""})

    async def _analyze_pr_retests_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze PR retests with comprehensive statistics and insights.

        Args:
            arguments: Tool arguments containing filters

        Returns:
            Dictionary with comprehensive retest analysis
        """
        try:
            repo_name = arguments.get("repo_name", "")
            project_name = arguments.get("project_name", "")
            days_back = arguments.get("days_back", 90)
            start_date = arguments.get("start_date", "")
            end_date = arguments.get("end_date", "")
            top_n = min(arguments.get("top_n", 15), 50)  # Cap at 50
            exclude_bots = arguments.get("exclude_bots", True)

            # Build date filter
            date_filter = ""
            if start_date or end_date:
                if start_date:
                    if len(start_date) == 10:
                        start_date = f"{start_date} 00:00:00"
                    date_filter += f" AND prc.created_date >= '{start_date}'"

                if end_date:
                    if len(end_date) == 10:
                        end_date = f"{end_date} 23:59:59"
                    date_filter += f" AND prc.created_date <= '{end_date}'"
            elif days_back > 0:
                start_date_calc = datetime.now() - timedelta(days=days_back)
                start_date_str = start_date_calc.strftime("%Y-%m-%d %H:%M:%S")
                date_filter = f" AND prc.created_date >= '{start_date_str}'"

            # Build project filter for main queries (uses pm alias)
            project_filter = ""
            if project_name:
                project_filter = f" AND pm.project_name = '{project_name}'"

            # Build project filter for subqueries (uses pm2 alias)
            project_filter_subquery = ""
            if project_name:
                project_filter_subquery = f" AND pm2.project_name = '{project_name}'"

            # Build repository filter
            repo_filter = ""
            if repo_name:
                repo_filter = (
                    f" AND (r.name LIKE '%{repo_name}%' OR r.url LIKE '%{repo_name}%' "
                    f"OR pr.url LIKE '%{repo_name}%')"
                )

            # Build bot exclusion filter
            bot_filter = ""
            if exclude_bots:
                # Exclude only known bot account patterns
                # Note: We only exclude account_id = 0 (known bot pattern)
                # We include NULL/empty account_id as they might be legitimate retest comments
                # that haven't been properly attributed yet
                bot_filter = """
                    AND prc.account_id != 'github:GithubAccount:1:0'
                """

            # Step 1: Get total count of manual /retest comments
            # Match exact "/retest" comments only (not partial matches)
            # Handle cases where body may be stored with quotes: "/retest" or '/retest'
            total_retests_query = f"""
                SELECT COUNT(*) as total_retests
                FROM lake.pull_request_comments prc
                INNER JOIN lake.pull_requests pr ON prc.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                LEFT JOIN lake.project_mapping pm ON r.id = pm.row_id AND pm.`table` = 'repos'
                WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                    AND prc.body IS NOT NULL
                    AND prc.body != ''
                    {project_filter}
                    {repo_filter}
                    {date_filter}
                    {bot_filter}
            """

            total_result = await self.db_connection.execute_query(total_retests_query, 1)
            # Convert MySQL numeric types (Decimal/string) to int
            total_retests = (
                int(float(total_result["data"][0]["total_retests"]))
                if total_result["success"] and total_result["data"]
                else 0
            )

            # Step 2: Get number of PRs affected
            affected_prs_query = f"""
                SELECT COUNT(DISTINCT prc.pull_request_id) as affected_prs
                FROM lake.pull_request_comments prc
                INNER JOIN lake.pull_requests pr ON prc.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                LEFT JOIN lake.project_mapping pm ON r.id = pm.row_id AND pm.`table` = 'repos'
                WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                    AND prc.body IS NOT NULL
                    AND prc.body != ''
                    {project_filter}
                    {repo_filter}
                    {date_filter}
                    {bot_filter}
            """

            affected_result = await self.db_connection.execute_query(affected_prs_query, 1)
            # Convert MySQL numeric types (Decimal/string) to int
            affected_prs = (
                int(float(affected_result["data"][0]["affected_prs"]))
                if affected_result["success"] and affected_result["data"]
                else 0
            )

            # Step 3: Calculate average retests per PR
            avg_retests = round(total_retests / affected_prs, 2) if affected_prs > 0 else 0

            # Step 4: Get top PRs with most retests
            top_prs_query = f"""
                SELECT
                    pr.id as pr_id,
                    pr.title,
                    pr.url,
                    pr.status,
                    pr.created_date,
                    pr.merged_date,
                    pr.closed_date,
                    pr.additions,
                    pr.deletions,
                    COUNT(prc.id) as retest_count,
                    DATEDIFF(
                        COALESCE(pr.merged_date, pr.closed_date, NOW()),
                        pr.created_date
                    ) as pr_duration_days
                FROM lake.pull_request_comments prc
                INNER JOIN lake.pull_requests pr ON prc.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                LEFT JOIN lake.project_mapping pm ON r.id = pm.row_id AND pm.`table` = 'repos'
                WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                    AND prc.body IS NOT NULL
                    AND prc.body != ''
                    {project_filter}
                    {repo_filter}
                    {date_filter}
                    {bot_filter}
                GROUP BY pr.id, pr.title, pr.url, pr.status, pr.created_date,
                         pr.merged_date, pr.closed_date, pr.additions, pr.deletions
                ORDER BY retest_count DESC
                LIMIT {top_n}
            """

            top_prs_result = await self.db_connection.execute_query(top_prs_query, top_n)
            top_prs = top_prs_result["data"] if top_prs_result["success"] else []

            # Step 5: Get timeline data for visualization
            timeline_query = f"""
                SELECT
                    DATE(prc.created_date) as date,
                    COUNT(*) as retest_count
                FROM lake.pull_request_comments prc
                INNER JOIN lake.pull_requests pr ON prc.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                LEFT JOIN lake.project_mapping pm ON r.id = pm.row_id AND pm.`table` = 'repos'
                WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                    AND prc.body IS NOT NULL
                    AND prc.body != ''
                    {project_filter}
                    {repo_filter}
                    {date_filter}
                    {bot_filter}
                GROUP BY DATE(prc.created_date)
                ORDER BY date ASC
            """

            timeline_result = await self.db_connection.execute_query(timeline_query, 1000)
            timeline_data = timeline_result["data"] if timeline_result["success"] else []

            # Step 6: Get breakdown by PR category (based on title keywords)
            category_query = f"""
                SELECT
                    CASE
                        WHEN LOWER(pr.title) LIKE '%bug%' OR
                             LOWER(pr.title) LIKE '%fix%' THEN 'Bug Fixes'
                        WHEN LOWER(pr.title) LIKE '%feat%' OR
                             LOWER(pr.title) LIKE '%feature%' THEN 'Features'
                        WHEN LOWER(pr.title) LIKE '%dep%' OR
                             LOWER(pr.title) LIKE '%dependenc%' THEN 'Dependencies'
                        WHEN LOWER(pr.title) LIKE '%refactor%' THEN 'Refactoring'
                        WHEN LOWER(pr.title) LIKE '%test%' THEN 'Tests'
                        WHEN LOWER(pr.title) LIKE '%doc%' THEN 'Documentation'
                        WHEN LOWER(pr.title) LIKE '%chore%' THEN 'Chores'
                        ELSE 'Other'
                    END as category,
                    COUNT(DISTINCT pr.id) as pr_count,
                    SUM(retest_counts.retest_count) as total_retests
                FROM (
                    SELECT
                        prc.pull_request_id,
                        COUNT(*) as retest_count
                    FROM lake.pull_request_comments prc
                    INNER JOIN lake.pull_requests pr2 ON prc.pull_request_id = pr2.id
                    INNER JOIN lake.repos r2 ON pr2.base_repo_id = r2.id
                    LEFT JOIN lake.project_mapping pm2
                        ON r2.id = pm2.row_id AND pm2.`table` = 'repos'
                    WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                        AND prc.body IS NOT NULL
                        AND prc.body != ''
                        {project_filter_subquery}
                        {date_filter}
                        {bot_filter}
                    GROUP BY prc.pull_request_id
                ) retest_counts
                INNER JOIN lake.pull_requests pr ON retest_counts.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                LEFT JOIN lake.project_mapping pm ON r.id = pm.row_id AND pm.`table` = 'repos'
                WHERE 1=1 {project_filter} {repo_filter}
                GROUP BY category
                ORDER BY total_retests DESC
            """

            category_result = await self.db_connection.execute_query(category_query, 20)
            category_breakdown = category_result["data"] if category_result["success"] else []

            # Step 7: Analyze root causes and patterns
            # Get PRs with high retest counts and their characteristics
            pattern_query = f"""
                SELECT
                    pr.status,
                    AVG(retest_counts.retest_count) as avg_retests,
                    COUNT(DISTINCT pr.id) as pr_count,
                    AVG(pr.additions + pr.deletions) as avg_changes,
                    AVG(DATEDIFF(
                        COALESCE(pr.merged_date, pr.closed_date, NOW()),
                        pr.created_date
                    )) as avg_duration_days
                FROM (
                    SELECT
                        prc.pull_request_id,
                        COUNT(*) as retest_count
                    FROM lake.pull_request_comments prc
                    INNER JOIN lake.pull_requests pr2 ON prc.pull_request_id = pr2.id
                    INNER JOIN lake.repos r2 ON pr2.base_repo_id = r2.id
                    LEFT JOIN lake.project_mapping pm2
                        ON r2.id = pm2.row_id AND pm2.`table` = 'repos'
                    WHERE LOWER(REPLACE(REPLACE(TRIM(prc.body), '"', ''), '''', '')) = '/retest'
                        AND prc.body IS NOT NULL
                        AND prc.body != ''
                        {project_filter_subquery}
                        {date_filter}
                        {bot_filter}
                    GROUP BY prc.pull_request_id
                ) retest_counts
                INNER JOIN lake.pull_requests pr ON retest_counts.pull_request_id = pr.id
                INNER JOIN lake.repos r ON pr.base_repo_id = r.id
                LEFT JOIN lake.project_mapping pm ON r.id = pm.row_id AND pm.`table` = 'repos'
                WHERE 1=1 {project_filter} {repo_filter}
                GROUP BY pr.status
                ORDER BY avg_retests DESC
            """

            pattern_result = await self.db_connection.execute_query(pattern_query, 10)
            pattern_analysis = pattern_result["data"] if pattern_result["success"] else []

            # Format top PRs for better readability
            # Convert MySQL numeric types (Decimal/string) to proper Python types
            formatted_top_prs = []
            for pr in top_prs:
                additions = int(float(pr.get("additions", 0) or 0))
                deletions = int(float(pr.get("deletions", 0) or 0))
                formatted_pr = {
                    "pr_title": pr.get("title", "N/A"),
                    "pr_url": pr.get("url", "N/A"),
                    "retest_count": int(float(pr.get("retest_count", 0) or 0)),
                    "pr_duration_days": int(float(pr.get("pr_duration_days", 0) or 0)),
                    "changes": {
                        "additions": additions,
                        "deletions": deletions,
                        "total": additions + deletions,
                    },
                    "status": pr.get("status", "UNKNOWN"),
                    "created_date": pr.get("created_date"),
                    "merged_date": pr.get("merged_date"),
                    "closed_date": pr.get("closed_date"),
                }
                formatted_top_prs.append(formatted_pr)

            # Generate recommendations based on patterns
            recommendations = self._generate_recommendations(
                total_retests,
                affected_prs,
                avg_retests,
                category_breakdown,
                pattern_analysis,
                top_prs,
            )

            return {
                "success": True,
                "analysis_period": {
                    "start_date": start_date if start_date else "all_available",
                    "end_date": end_date if end_date else "all_available",
                    "days_back": days_back if days_back > 0 else "all",
                },
                "filters": {
                    "repo_name": repo_name if repo_name else "all_repositories",
                    "project_name": project_name if project_name else "all_projects",
                    "exclude_bots": exclude_bots,
                },
                "executive_summary": {
                    "total_manual_retest_comments": total_retests,
                    "number_of_affected_prs": affected_prs,
                    "average_retests_per_pr": avg_retests,
                    "time_period_analyzed": (
                        f"{days_back} days" if days_back > 0 else "all available data"
                    ),
                },
                "top_prs_by_retests": formatted_top_prs,
                "category_breakdown": category_breakdown,
                "timeline_data": timeline_data,
                "pattern_analysis": {
                    "by_status": pattern_analysis,
                    "insights": self._analyze_patterns(pattern_analysis, category_breakdown),
                },
                "recommendations": recommendations,
            }

        except Exception as e:
            self.logger.error(f"Analyze PR retests failed: {e}")
            return {"success": False, "error": str(e)}

    def _generate_recommendations(
        self,
        total_retests: int,
        affected_prs: int,
        avg_retests: float,
        category_breakdown: List[Dict],
        pattern_analysis: List[Dict],
        top_prs: List[Dict],
    ) -> List[Dict[str, Any]]:
        """
        Generate actionable recommendations based on analysis.

        Args:
            total_retests: Total number of retest comments
            affected_prs: Number of PRs affected
            avg_retests: Average retests per PR
            category_breakdown: Breakdown by PR category
            pattern_analysis: Pattern analysis data
            top_prs: Top PRs with most retests

        Returns:
            List of recommendation dictionaries
        """
        recommendations = []

        # High retest frequency recommendations
        if avg_retests > 3:
            recommendations.append(
                {
                    "priority": "high",
                    "category": "CI/CD Reliability",
                    "issue": f"High average retest frequency ({avg_retests:.2f} retests per PR)",
                    "recommendation": (
                        "Investigate CI/CD pipeline stability. Consider: "
                        "1) Reviewing flaky test patterns, "
                        "2) Improving test environment reliability, "
                        "3) Implementing automatic retry mechanisms for transient failures"
                    ),
                    "impact": "Reduces developer friction and speeds up PR review cycles",
                }
            )

        # Category-specific recommendations
        if category_breakdown:
            max_category = max(
                category_breakdown, key=lambda x: float(x.get("total_retests", 0) or 0)
            )
            max_retests = float(max_category.get("total_retests", 0) or 0)
            if max_retests > total_retests * 0.3:  # More than 30% of retests
                recommendations.append(
                    {
                        "priority": "medium",
                        "category": "Category-Specific Issues",
                        "issue": (
                            f"'{max_category.get('category')}' category accounts for "
                            f"{int(max_retests)} retests"
                        ),
                        "recommendation": (
                            f"Focus improvement efforts on {max_category.get('category')} PRs. "
                            "Review common failure patterns in this category and optimize "
                            "test suites accordingly."
                        ),
                        "impact": "Targeted improvement for highest-impact category",
                    }
                )

        # Status-based recommendations
        if pattern_analysis:
            merged_prs = [p for p in pattern_analysis if p.get("status") == "MERGED"]
            if merged_prs:
                avg_retests_val = float(merged_prs[0].get("avg_retests", 0) or 0)
                if avg_retests_val > 2:
                    recommendations.append(
                        {
                            "priority": "medium",
                            "category": "Pre-merge Testing",
                            "issue": "Merged PRs still require multiple retests",
                            "recommendation": (
                                "Strengthen pre-merge test coverage and ensure all critical "
                                "paths are tested before merge approval. Consider implementing "
                                "mandatory test passes before allowing merge."
                            ),
                            "impact": "Reduces post-merge issues and improves code quality",
                        }
                    )

        # Large change recommendations
        if top_prs:
            large_change_prs = [
                pr
                for pr in top_prs
                if ((pr.get("additions", 0) or 0) + (pr.get("deletions", 0) or 0) > 1000)
            ]
            if large_change_prs:
                recommendations.append(
                    {
                        "priority": "low",
                        "category": "PR Size Management",
                        "issue": (
                            f"{len(large_change_prs)} PRs with >1000 lines changed "
                            "have high retest counts"
                        ),
                        "recommendation": (
                            "Consider breaking large PRs into smaller, more manageable "
                            "chunks. Smaller PRs are easier to test and review, reducing "
                            "retest frequency."
                        ),
                        "impact": "Improves review quality and reduces test complexity",
                    }
                )

        # General recommendations if no specific issues found
        if not recommendations:
            recommendations.append(
                {
                    "priority": "low",
                    "category": "Continuous Improvement",
                    "issue": "Retest frequency is within acceptable range",
                    "recommendation": (
                        "Continue monitoring retest patterns. Consider implementing "
                        "automated test retry mechanisms for known flaky tests."
                    ),
                    "impact": "Maintains current quality levels while reducing manual intervention",
                }
            )

        return recommendations

    def _analyze_patterns(
        self, pattern_analysis: List[Dict], category_breakdown: List[Dict]
    ) -> List[str]:
        """
        Analyze patterns and generate insights.

        Args:
            pattern_analysis: Pattern analysis data
            category_breakdown: Category breakdown data

        Returns:
            List of insight strings
        """
        insights = []

        if pattern_analysis:
            max_status = max(pattern_analysis, key=lambda x: float(x.get("avg_retests", 0) or 0))
            avg_retests_val = float(max_status.get("avg_retests", 0) or 0)
            insights.append(
                f"PRs with status '{max_status.get('status')}' have the highest "
                f"average retest count ({avg_retests_val:.2f} retests per PR)"
            )

        if category_breakdown:
            max_category = max(
                category_breakdown, key=lambda x: float(x.get("total_retests", 0) or 0)
            )
            total_retests_val = float(max_category.get("total_retests", 0) or 0)
            pr_count_val = int(max_category.get("pr_count", 0) or 0)
            insights.append(
                f"'{max_category.get('category')}' category has the most retests "
                f"({int(total_retests_val)} total retests across {pr_count_val} PRs)"
            )

        return insights
