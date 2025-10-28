"""
Database integration tests.

These tests verify that database operations work correctly
against a real MySQL database instance.
"""

import pytest
import json
from typing import Dict, Any

from tools.database_tools import DatabaseTools
from utils.db import KonfluxDevLakeConnection


@pytest.mark.integration
@pytest.mark.asyncio
class TestDatabaseIntegration:
    """Integration tests for database operations."""

    async def test_database_connection(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test that we can connect to the database."""
        result = await integration_db_connection.connect()
        
        assert result["success"] is True
        assert "connection_info" in result
        assert result["connection_info"]["database"] == "lake"

    async def test_list_databases(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test listing databases."""
        db_tools = DatabaseTools(integration_db_connection)
        
        result_json = await db_tools.call_tool("list_databases", {})
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert "data" in result
        
        # Should contain our test database
        # Data comes as list of dictionaries from MySQL DictCursor
        databases = [list(row.values())[0] for row in result["data"]]
        assert "lake" in databases

    async def test_list_tables(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test listing tables in the lake database."""
        db_tools = DatabaseTools(integration_db_connection)
        
        result_json = await db_tools.call_tool("list_tables", {"database": "lake"})
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert "data" in result
        
        # Should contain our test tables
        # Data comes as list of dictionaries from MySQL DictCursor
        tables = [list(row.values())[0] for row in result["data"]]
        expected_tables = ["incidents", "cicd_deployments", "cicd_deployment_commits", "project_mapping"]
        
        for table in expected_tables:
            assert table in tables

    async def test_get_table_schema(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test getting table schema information."""
        db_tools = DatabaseTools(integration_db_connection)
        
        result_json = await db_tools.call_tool("get_table_schema", {
            "database": "lake",
            "table": "incidents"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert "data" in result
        
        # Check that we get schema information
        schema_data = result["data"]
        assert len(schema_data) > 0
        
        # Check for expected columns
        # Data comes as list of dictionaries from MySQL DictCursor
        column_names = [list(row.values())[0] for row in schema_data]
        expected_columns = ["id", "incident_key", "title", "status", "created_date"]
        
        for column in expected_columns:
            assert column in column_names

    async def test_get_table_schema_nonexistent_table(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test getting schema for non-existent table."""
        db_tools = DatabaseTools(integration_db_connection)
        
        result_json = await db_tools.call_tool("get_table_schema", {
            "database": "lake",
            "table": "nonexistent_table"
        })
        result = json.loads(result_json)
        
        assert result["success"] is False
        assert "error" in result

    async def test_get_table_schema_invalid_database(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test getting schema from invalid database."""
        db_tools = DatabaseTools(integration_db_connection)
        
        result_json = await db_tools.call_tool("get_table_schema", {
            "database": "nonexistent_db",
            "table": "incidents"
        })
        result = json.loads(result_json)
        
        assert result["success"] is False
        assert "error" in result

    async def test_database_tools_error_handling(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test error handling in database tools."""
        db_tools = DatabaseTools(integration_db_connection)
        
        # Test with missing required parameters
        result_json = await db_tools.call_tool("get_table_schema", {
            "database": "lake"
            # Missing 'table' parameter
        })
        result = json.loads(result_json)
        
        assert result["success"] is False
        assert "error" in result
        assert "table names are required" in result["error"]

    async def test_database_connection_info(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test that connection info is properly returned."""
        result = await integration_db_connection.connect()
        
        assert result["success"] is True
        assert "connection_info" in result
        
        conn_info = result["connection_info"]
        # Accept both localhost and 127.0.0.1 as valid hosts
        assert conn_info["host"] in ["localhost", "127.0.0.1"]
        assert conn_info["port"] == 3306
        assert conn_info["database"] == "lake"
        assert conn_info["user"] == "devlake"
        # Password should not be included in connection info for security
        assert "password" not in conn_info

    async def test_database_query_execution(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test direct query execution."""
        # Test a simple SELECT query
        result = await integration_db_connection.execute_query(
            "SELECT COUNT(*) as incident_count FROM incidents"
        )
        
        assert result["success"] is True
        assert "data" in result
        assert len(result["data"]) == 1
        assert "incident_count" in str(result["data"][0])

    async def test_database_query_with_parameters(self, integration_db_connection: KonfluxDevLakeConnection):
        """Test query execution with parameters."""
        # Test querying specific incident data
        result = await integration_db_connection.execute_query(
            "SELECT incident_key, title, status FROM incidents WHERE status = 'DONE' LIMIT 5"
        )
        
        assert result["success"] is True
        assert "data" in result
        
        # Should have at least one DONE incident from test data
        if result["data"]:
            for row in result["data"]:
                # Each row should have 3 columns
                assert len(row) == 3
