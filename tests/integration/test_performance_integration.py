"""
Performance and Concurrent Operations Integration Tests

These tests verify that the system handles concurrent operations
and edge cases correctly with a real database.
"""

import pytest
import json
import asyncio
from typing import Dict, Any

from tools.devlake.incident_tools import IncidentTools
from tools.devlake.deployment_tools import DeploymentTools
from tools.database_tools import DatabaseTools
from utils.db import KonfluxDevLakeConnection


@pytest.mark.integration
@pytest.mark.asyncio
class TestConcurrentOperations:
    """Test concurrent database operations."""

    async def test_concurrent_incident_queries(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test multiple concurrent incident queries work correctly."""
        incident_tools = IncidentTools(integration_db_connection)
        
        # Execute multiple queries concurrently
        tasks = [
            incident_tools.call_tool("get_incidents", {})
            for _ in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all queries completed successfully
        assert len(results) == 5
        for result_json in results:
            result = json.loads(result_json)
            assert result["success"] is True
            assert "incidents" in result

    async def test_concurrent_deployment_queries(
        self,
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test multiple concurrent deployment queries work correctly."""
        deployment_tools = DeploymentTools(integration_db_connection)
        
        # Execute multiple queries concurrently
        tasks = [
            deployment_tools.call_tool("get_deployments", {})
            for _ in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all queries completed successfully
        assert len(results) == 5
        for result_json in results:
            result = json.loads(result_json)
            assert result["success"] is True
            assert "deployments" in result

    async def test_concurrent_mixed_queries(
        self,
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test concurrent queries of different types."""
        incident_tools = IncidentTools(integration_db_connection)
        deployment_tools = DeploymentTools(integration_db_connection)
        db_tools = DatabaseTools(integration_db_connection)
        
        # Mix different types of queries
        tasks = [
            incident_tools.call_tool("get_incidents", {}),
            deployment_tools.call_tool("get_deployments", {}),
            db_tools.call_tool("list_databases", {}),
            incident_tools.call_tool("get_incidents", {"status": "DONE"}),
            deployment_tools.call_tool("get_deployments", {"environment": "PRODUCTION"}),
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all queries completed
        assert len(results) == 5
        for result_json in results:
            result = json.loads(result_json)
            assert result["success"] is True

    async def test_rapid_sequential_queries(
        self,
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test rapid sequential queries work correctly."""
        incident_tools = IncidentTools(integration_db_connection)
        
        # Make rapid sequential calls
        results = []
        for _ in range(10):
            result_json = await incident_tools.call_tool("get_incidents", {})
            results.append(result_json)
        
        # Verify all calls completed successfully
        assert len(results) == 10
        for result_json in results:
            result = json.loads(result_json)
            assert result["success"] is True


@pytest.mark.integration
@pytest.mark.asyncio
class TestErrorScenarios:
    """Test error handling scenarios with real database."""

    async def test_query_nonexistent_database(
        self,
        integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test querying a database that doesn't exist."""
        db_tools = DatabaseTools(integration_db_connection)
        
        result_json = await db_tools.call_tool("list_tables", {
            "database": "nonexistent_database"
        })
        result = json.loads(result_json)
        
        assert result["success"] is False
        assert "error" in result

    async def test_query_nonexistent_table(
        self,
        integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test querying a table that doesn't exist."""
        result = await integration_db_connection.execute_query(
            "SELECT * FROM nonexistent_table"
        )
        
        assert result["success"] is False
        assert "error" in result

    async def test_invalid_sql_syntax(
        self,
        integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test handling of invalid SQL syntax."""
        result = await integration_db_connection.execute_query(
            "SELECT * FORM incidents"  # typo: FORM instead of FROM
        )
        
        assert result["success"] is False
        assert "error" in result

    async def test_missing_required_parameters(
        self,
        integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test tools handle missing required parameters correctly."""
        db_tools = DatabaseTools(integration_db_connection)
        
        # Call get_table_schema without required 'table' parameter
        result_json = await db_tools.call_tool("get_table_schema", {
            "database": "lake"
            # Missing 'table' parameter
        })
        result = json.loads(result_json)
        
        assert result["success"] is False
        assert "error" in result
        assert "required" in result["error"].lower() or "table" in result["error"].lower()

    async def test_empty_query_results(
        self,
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test handling of queries that return no results."""
        incident_tools = IncidentTools(integration_db_connection)
        
        # Query with filter that matches nothing
        result_json = await incident_tools.call_tool("get_incidents", {
            "component": "nonexistent-component-xyz"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert "incidents" in result
        assert len(result["incidents"]) == 0

    async def test_invalid_filter_values(
        self,
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test handling of invalid filter values."""
        deployment_tools = DeploymentTools(integration_db_connection)
        
        # Try with invalid date format
        result_json = await deployment_tools.call_tool("get_deployments", {
            "start_date": "not-a-valid-date"
        })
        result = json.loads(result_json)
        
        # Should either fail gracefully or ignore invalid date
        assert isinstance(result, dict)
        assert "success" in result


@pytest.mark.integration
@pytest.mark.asyncio
class TestConnectionEdgeCases:
    """Test connection edge cases with real database."""

    async def test_connection_info_correct(
        self,
        integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test connection info is correct and secure."""
        result = await integration_db_connection.connect()
        
        assert result["success"] is True
        assert "connection_info" in result
        
        conn_info = result["connection_info"]
        assert "database" in conn_info
        assert conn_info["database"] == "lake"
        
        # Password should never be in connection info (security)
        assert "password" not in conn_info
        assert "passwd" not in str(conn_info).lower()

    async def test_multiple_connections(
        self,
        integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test multiple connection attempts work correctly."""
        # Connect multiple times
        results = []
        for _ in range(3):
            result = await integration_db_connection.connect()
            results.append(result)
        
        # All connections should succeed
        for result in results:
            assert result["success"] is True

    async def test_query_after_connection(
        self,
        integration_db_connection: KonfluxDevLakeConnection
    ):
        """Test queries work after establishing connection."""
        # Ensure connected
        conn_result = await integration_db_connection.connect()
        assert conn_result["success"] is True
        
        # Execute query
        query_result = await integration_db_connection.execute_query(
            "SELECT 1 as test"
        )
        
        assert query_result["success"] is True
        assert "data" in query_result

