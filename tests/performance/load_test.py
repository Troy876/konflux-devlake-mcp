#!/usr/bin/env python3
"""
Performance Load Test for Konflux DevLake MCP Server

This script simulates multiple concurrent users making requests to stress test
the connection pool and measure response times, throughput, and error rates.

Usage:
    python tests/performance/load_test.py --url <MCP_SERVER_URL> --users 50 --duration 60
"""

import argparse
import asyncio
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import httpx
except ImportError:
    print("Please install httpx: pip install httpx")
    sys.exit(1)


@dataclass
class RequestResult:
    """Result of a single request."""

    success: bool
    status_code: int
    response_time_ms: float
    error: Optional[str] = None


@dataclass
class LoadTestResults:
    """Aggregated load test results."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_503: int = 0
    error_504: int = 0
    error_other: int = 0
    response_times: List[float] = field(default_factory=list)
    start_time: float = 0
    end_time: float = 0

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time

    @property
    def requests_per_second(self) -> float:
        if self.duration_seconds > 0:
            return self.total_requests / self.duration_seconds
        return 0

    @property
    def success_rate(self) -> float:
        if self.total_requests > 0:
            return (self.successful_requests / self.total_requests) * 100
        return 0

    @property
    def avg_response_time(self) -> float:
        if self.response_times:
            return statistics.mean(self.response_times)
        return 0

    @property
    def p50_response_time(self) -> float:
        if self.response_times:
            return statistics.median(self.response_times)
        return 0

    @property
    def p95_response_time(self) -> float:
        if len(self.response_times) >= 20:
            sorted_times = sorted(self.response_times)
            idx = int(len(sorted_times) * 0.95)
            return sorted_times[idx]
        return max(self.response_times) if self.response_times else 0

    @property
    def p99_response_time(self) -> float:
        if len(self.response_times) >= 100:
            sorted_times = sorted(self.response_times)
            idx = int(len(sorted_times) * 0.99)
            return sorted_times[idx]
        return max(self.response_times) if self.response_times else 0


# Test queries of varying complexity - includes codecov queries
TEST_QUERIES = [
    # Simple query - fast
    "SELECT COUNT(*) as count FROM lake.repos",
    # Medium query - moderate
    "SELECT name, url FROM lake.repos LIMIT 10",
    # Codecov: Get all repos with coverage
    "SELECT * FROM lake._tool_codecov_repos LIMIT 10",
    # Codecov: Current coverage for integration-service
    """
    SELECT repo_id, flag_name, branch, coverage_percentage,
        lines_covered, lines_total, commit_timestamp
    FROM lake._tool_codecov_coverages
    WHERE repo_id LIKE '%integration-service%'
    ORDER BY commit_timestamp DESC
    LIMIT 10
    """,
    # Codecov: Coverage trend for release-service
    """
    SELECT
        DATE(commit_timestamp) as date,
        flag_name,
        ROUND(AVG(coverage_percentage), 2) as avg_coverage,
        SUM(lines_covered) as total_lines_covered,
        SUM(lines_total) as total_lines
    FROM lake._tool_codecov_coverages
    WHERE repo_id LIKE '%release-service%'
    AND commit_timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    GROUP BY DATE(commit_timestamp), flag_name
    ORDER BY date DESC
    """,
    # Codecov: Repos with lowest coverage
    """
    SELECT
        repo_id,
        flag_name,
        ROUND(AVG(coverage_percentage), 2) as avg_coverage,
        COUNT(*) as commit_count
    FROM lake._tool_codecov_coverages
    GROUP BY repo_id, flag_name
    ORDER BY avg_coverage ASC
    LIMIT 15
    """,
    # Codecov: Unit vs E2E coverage comparison
    """
    SELECT
        repo_id,
        MAX(CASE WHEN flag_name LIKE '%unit%' THEN coverage_percentage END) as unit_cov,
        MAX(CASE WHEN flag_name LIKE '%e2e%' THEN coverage_percentage END) as e2e_cov
    FROM lake._tool_codecov_coverages
    WHERE commit_timestamp = (
        SELECT MAX(commit_timestamp) FROM lake._tool_codecov_coverages c2
        WHERE c2.repo_id = _tool_codecov_coverages.repo_id
    )
    GROUP BY repo_id
    """,
    # Codecov: Coverage breakdown by flag for build-service
    """
    SELECT
        flag_name,
        ROUND(AVG(coverage_percentage), 2) as avg_coverage,
        ROUND(MIN(coverage_percentage), 2) as min_coverage,
        ROUND(MAX(coverage_percentage), 2) as max_coverage,
        COUNT(*) as samples
    FROM lake._tool_codecov_coverages
    WHERE repo_id LIKE '%build-service%'
    GROUP BY flag_name
    """,
    # Complex PR query
    """
    SELECT
        DATE(pr.created_date) as date,
        COUNT(*) as pr_count
    FROM lake.pull_requests pr
    WHERE pr.created_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)
    GROUP BY DATE(pr.created_date)
    ORDER BY date
    """,
    # Heavy join query
    """
    SELECT
        r.name as repo,
        COUNT(pr.id) as pr_count
    FROM lake.repos r
    LEFT JOIN lake.pull_requests pr ON r.id = pr.base_repo_id
    GROUP BY r.id, r.name
    ORDER BY pr_count DESC
    LIMIT 20
    """,
]


async def make_mcp_request(
    client: httpx.AsyncClient, url: str, query: str, timeout: float = 300.0
) -> RequestResult:
    """Make a single MCP request and measure response time."""
    start = time.perf_counter()

    # MCP Streamable HTTP JSON-RPC request format
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "execute_query", "arguments": {"query": query}},
    }

    # MCP Streamable HTTP requires these specific headers
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    try:
        response = await client.post(
            url,
            json=payload,
            headers=headers,
            timeout=timeout,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        if response.status_code == 200:
            return RequestResult(
                success=True, status_code=response.status_code, response_time_ms=elapsed_ms
            )
        else:
            return RequestResult(
                success=False,
                status_code=response.status_code,
                response_time_ms=elapsed_ms,
                error=f"HTTP {response.status_code}",
            )

    except httpx.TimeoutException:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return RequestResult(
            success=False, status_code=504, response_time_ms=elapsed_ms, error="Timeout"
        )
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return RequestResult(
            success=False, status_code=0, response_time_ms=elapsed_ms, error=str(e)
        )


async def user_simulation(
    user_id: int,
    url: str,
    duration_seconds: float,
    results: LoadTestResults,
    results_lock: asyncio.Lock,
    think_time: float = 0.5,
) -> None:
    """Simulate a single user making requests."""
    end_time = time.time() + duration_seconds

    async with httpx.AsyncClient() as client:
        request_count = 0
        while time.time() < end_time:
            # Pick a random query
            query = TEST_QUERIES[request_count % len(TEST_QUERIES)]
            result = await make_mcp_request(client, url, query)

            async with results_lock:
                results.total_requests += 1
                if result.success:
                    results.successful_requests += 1
                    results.response_times.append(result.response_time_ms)
                else:
                    results.failed_requests += 1
                    if result.status_code == 503:
                        results.error_503 += 1
                    elif result.status_code == 504:
                        results.error_504 += 1
                    else:
                        results.error_other += 1

            request_count += 1

            # Small think time between requests
            await asyncio.sleep(think_time)


async def run_load_test(
    url: str,
    num_users: int,
    duration_seconds: float,
    ramp_up_seconds: float = 5.0,
) -> LoadTestResults:
    """Run the load test with specified parameters."""
    results = LoadTestResults()
    results_lock = asyncio.Lock()

    print(f"\n{'='*60}")
    print("Konflux DevLake MCP Server - Performance Load Test")
    print(f"{'='*60}")
    print(f"Target URL: {url}")
    print(f"Concurrent Users: {num_users}")
    print(f"Duration: {duration_seconds}s")
    print(f"Ramp-up: {ramp_up_seconds}s")
    print(f"{'='*60}\n")

    # Calculate ramp-up delay per user
    ramp_delay = ramp_up_seconds / num_users if num_users > 1 else 0

    results.start_time = time.time()

    # Create user tasks with staggered start
    tasks = []
    for user_id in range(num_users):
        task = asyncio.create_task(
            delayed_user_start(
                user_id=user_id,
                url=url,
                duration_seconds=duration_seconds,
                results=results,
                results_lock=results_lock,
                delay=user_id * ramp_delay,
            )
        )
        tasks.append(task)

    # Progress reporting
    progress_task = asyncio.create_task(
        report_progress(results, results_lock, duration_seconds + ramp_up_seconds)
    )

    # Wait for all users to complete
    await asyncio.gather(*tasks)
    progress_task.cancel()

    results.end_time = time.time()

    return results


async def delayed_user_start(
    user_id: int,
    url: str,
    duration_seconds: float,
    results: LoadTestResults,
    results_lock: asyncio.Lock,
    delay: float,
) -> None:
    """Start a user simulation after a delay (for ramp-up)."""
    await asyncio.sleep(delay)
    await user_simulation(user_id, url, duration_seconds, results, results_lock)


async def report_progress(
    results: LoadTestResults, results_lock: asyncio.Lock, duration: float
) -> None:
    """Report progress during the test."""
    start = time.time()
    while True:
        await asyncio.sleep(5)
        elapsed = time.time() - start
        async with results_lock:
            print(
                f"[{elapsed:.0f}s] Requests: {results.total_requests} | "
                f"Success: {results.successful_requests} | "
                f"Failed: {results.failed_requests} | "
                f"503s: {results.error_503} | 504s: {results.error_504}"
            )


def print_results(results: LoadTestResults) -> None:
    """Print the load test results."""
    print(f"\n{'='*60}")
    print("LOAD TEST RESULTS")
    print(f"{'='*60}\n")

    print("Request Statistics:")
    print(f"  Total Requests:      {results.total_requests}")
    print(f"  Successful:          {results.successful_requests}")
    print(f"  Failed:              {results.failed_requests}")
    print(f"  Success Rate:        {results.success_rate:.1f}%")
    print(f"  Requests/Second:     {results.requests_per_second:.2f}")

    print("\nError Breakdown:")
    print(f"  503 (Service Unavail): {results.error_503}")
    print(f"  504 (Gateway Timeout): {results.error_504}")
    print(f"  Other Errors:          {results.error_other}")

    if results.response_times:
        print("\nResponse Times (successful requests):")
        print(f"  Average:  {results.avg_response_time:.0f} ms")
        print(f"  Median:   {results.p50_response_time:.0f} ms")
        print(f"  P95:      {results.p95_response_time:.0f} ms")
        print(f"  P99:      {results.p99_response_time:.0f} ms")
        print(f"  Min:      {min(results.response_times):.0f} ms")
        print(f"  Max:      {max(results.response_times):.0f} ms")

    print(f"\nTest Duration: {results.duration_seconds:.1f} seconds")

    # Verdict
    print(f"\n{'='*60}")
    if results.success_rate >= 99:
        print("VERDICT: EXCELLENT - Server handles load well")
    elif results.success_rate >= 95:
        print("VERDICT: GOOD - Minor issues under load")
    elif results.success_rate >= 90:
        print("VERDICT: FAIR - Some degradation under load")
    else:
        print("VERDICT: POOR - Significant issues under load")

    if results.error_503 > 0:
        print(f"  WARNING: {results.error_503} x 503 errors - connection pool may be exhausted")
    if results.error_504 > 0:
        print(f"  WARNING: {results.error_504} x 504 errors - queries timing out")
    print(f"{'='*60}\n")


async def health_check(url: str) -> bool:
    """Check if the server is reachable."""
    health_url = url.replace("/mcp", "/health")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(health_url, timeout=10.0)
            return response.status_code == 200
    except Exception:
        return False


async def main():
    parser = argparse.ArgumentParser(description="Load test the Konflux DevLake MCP Server")
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:3000/mcp",
        help="MCP server URL (default: http://localhost:3000/mcp)",
    )
    parser.add_argument(
        "--users", type=int, default=10, help="Number of concurrent users (default: 10)"
    )
    parser.add_argument(
        "--duration", type=int, default=30, help="Test duration in seconds (default: 30)"
    )
    parser.add_argument(
        "--ramp-up", type=float, default=5.0, help="Ramp-up time in seconds (default: 5)"
    )

    args = parser.parse_args()

    # Health check
    print(f"Checking server health at {args.url}...")
    if not await health_check(args.url):
        print("WARNING: Health check failed. Server may not be reachable.")
        print("Proceeding with load test anyway...\n")

    # Run load test
    results = await run_load_test(
        url=args.url,
        num_users=args.users,
        duration_seconds=args.duration,
        ramp_up_seconds=args.ramp_up,
    )

    # Print results
    print_results(results)

    # Exit code based on success rate
    if results.success_rate >= 95:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
