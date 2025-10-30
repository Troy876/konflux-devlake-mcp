#!/usr/bin/env python3
"""
Unit Tests for Deployment Tools

Tests the DeploymentTools class functionality including:
- Tool registration and listing
- Deployment data retrieval with filtering
- Parameter validation
- Environment and project filtering
"""

import pytest
import json

from tools.devlake.deployment_tools import DeploymentTools
from mcp.types import Tool


@pytest.mark.unit
class TestDeploymentTools:
    """Test suite for DeploymentTools class."""

    @pytest.fixture
    def deployment_tools(self, mock_db_connection):
        """Create DeploymentTools instance with mock connection."""
        return DeploymentTools(mock_db_connection)

    def test_get_tools_returns_deployment_tools(self, deployment_tools):
        """Test that get_tools returns the deployment analytics tool."""
        tools = deployment_tools.get_tools()
        
        assert len(tools) == 1
        assert isinstance(tools[0], Tool)
        assert tools[0].name == "get_deployments"
        assert "Comprehensive Deployment Analytics Tool" in tools[0].description

    def test_get_tool_names(self, deployment_tools):
        """Test get_tool_names method."""
        tool_names = deployment_tools.get_tool_names()
        assert "get_deployments" in tool_names

    def test_validate_tool_exists(self, deployment_tools):
        """Test tool existence validation."""
        assert deployment_tools.validate_tool_exists("get_deployments") is True
        assert deployment_tools.validate_tool_exists("nonexistent_tool") is False

    @pytest.mark.asyncio
    async def test_get_deployments_no_filters(self, deployment_tools, mock_db_connection, sample_deployment_data):
        """Test getting deployments without any filters (uses defaults)."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "WITH _deployment_commit_rank AS (...) SELECT ...",
            "row_count": 2,
            "data": sample_deployment_data
        }
        
        result_json = await deployment_tools.call_tool("get_deployments", {})
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert "filters" in result
        assert "deployments" in result
        assert len(result["deployments"]) == 2
        
        filters = result["filters"]
        assert filters["project"] == "all"
        assert filters["environment"] == "all"
        assert filters["date_field"] == "finished_date"
        assert filters["limit"] == 50

    @pytest.mark.asyncio
    async def test_get_deployments_with_project_filter(self, deployment_tools, mock_db_connection, sample_deployment_data):
        """Test getting deployments with project filter."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "WITH _deployment_commit_rank AS (...) WHERE pm.project_name IN ('Konflux_Pilot_Team')",
            "row_count": 2,
            "data": sample_deployment_data
        }
        
        result_json = await deployment_tools.call_tool("get_deployments", {"project": "Konflux_Pilot_Team"})
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert result["filters"]["project"] == "Konflux_Pilot_Team"
        assert len(result["deployments"]) == 2

    @pytest.mark.asyncio
    async def test_get_deployments_with_environment_filter(self, deployment_tools, mock_db_connection, sample_deployment_data):
        """Test getting deployments with environment filter."""
        production_data = [dep for dep in sample_deployment_data if dep["environment"] == "PRODUCTION"]
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "WITH _deployment_commit_rank AS (...) WHERE environment = 'PRODUCTION'",
            "row_count": 2,
            "data": production_data
        }
        
        result_json = await deployment_tools.call_tool("get_deployments", {"environment": "PRODUCTION"})
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert result["filters"]["environment"] == "PRODUCTION"
        assert all(dep["environment"] == "PRODUCTION" for dep in result["deployments"])

    @pytest.mark.asyncio
    async def test_get_deployments_with_days_back_filter(self, deployment_tools, mock_db_connection, sample_deployment_data):
        """Test getting deployments with days_back filter."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "WITH _deployment_commit_rank AS (...) WHERE finished_date >= '2024-01-01 00:00:00'",
            "row_count": 2,
            "data": sample_deployment_data
        }
        
        result_json = await deployment_tools.call_tool("get_deployments", {"days_back": 30})
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert result["filters"]["days_back"] == 30
        assert len(result["deployments"]) == 2

    @pytest.mark.asyncio
    async def test_get_deployments_with_date_range(self, deployment_tools, mock_db_connection, sample_deployment_data):
        """Test getting deployments with explicit date range."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "WITH _deployment_commit_rank AS (...) WHERE finished_date >= '2024-01-15 00:00:00' AND finished_date <= '2024-01-16 23:59:59'",
            "row_count": 2,
            "data": sample_deployment_data
        }
        
        result_json = await deployment_tools.call_tool("get_deployments", {
            "start_date": "2024-01-15",
            "end_date": "2024-01-16"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert "2024-01-15" in result["filters"]["start_date"]
        assert "2024-01-16" in result["filters"]["end_date"]

    @pytest.mark.asyncio
    async def test_get_deployments_with_datetime_range(self, deployment_tools, mock_db_connection, sample_deployment_data):
        """Test getting deployments with full datetime range."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "WITH _deployment_commit_rank AS (...) WHERE finished_date >= '2024-01-15 10:00:00' AND finished_date <= '2024-01-16 12:00:00'",
            "row_count": 2,
            "data": sample_deployment_data
        }
        
        result_json = await deployment_tools.call_tool("get_deployments", {
            "start_date": "2024-01-15 10:00:00",
            "end_date": "2024-01-16 12:00:00"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert result["filters"]["start_date"] == "2024-01-15 10:00:00"
        assert result["filters"]["end_date"] == "2024-01-16 12:00:00"

    @pytest.mark.asyncio
    async def test_get_deployments_with_different_date_fields(self, deployment_tools, mock_db_connection, sample_deployment_data):
        """Test getting deployments with different date field options."""
        for date_field in ["finished_date", "created_date", "updated_date"]:
            mock_db_connection.execute_query.return_value = {
                "success": True,
                "query": f"WITH _deployment_commit_rank AS (...) ORDER BY {date_field} DESC",
                "row_count": 2,
                "data": sample_deployment_data
            }
            
            result_json = await deployment_tools.call_tool("get_deployments", {"date_field": date_field})
            result = json.loads(result_json)
            
            assert result["success"] is True
            assert result["filters"]["date_field"] == date_field

    @pytest.mark.asyncio
    async def test_get_deployments_invalid_date_field(self, deployment_tools):
        """Test getting deployments with invalid date field."""
        result_json = await deployment_tools.call_tool("get_deployments", {"date_field": "invalid_field"})
        result = json.loads(result_json)
        
        assert result["success"] is False
        assert "Invalid date_field 'invalid_field'" in result["error"]

    @pytest.mark.asyncio
    async def test_get_deployments_with_limit(self, deployment_tools, mock_db_connection, sample_deployment_data):
        """Test getting deployments with custom limit."""
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "WITH _deployment_commit_rank AS (...) LIMIT 25",
            "row_count": 2,
            "data": sample_deployment_data
        }
        
        result_json = await deployment_tools.call_tool("get_deployments", {"limit": 25})
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert result["filters"]["limit"] == 25

    @pytest.mark.asyncio
    async def test_get_deployments_combined_filters(self, deployment_tools, mock_db_connection, sample_deployment_data):
        """Test getting deployments with multiple filters combined."""
        filtered_data = [dep for dep in sample_deployment_data 
                        if dep["project_name"] == "Konflux_Pilot_Team" and dep["environment"] == "PRODUCTION"]
        
        mock_db_connection.execute_query.return_value = {
            "success": True,
            "query": "WITH _deployment_commit_rank AS (...) WHERE pm.project_name IN ('Konflux_Pilot_Team') AND environment = 'PRODUCTION'",
            "row_count": 2,
            "data": filtered_data
        }
        
        result_json = await deployment_tools.call_tool("get_deployments", {
            "project": "Konflux_Pilot_Team",
            "environment": "PRODUCTION",
            "limit": 100
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert result["filters"]["project"] == "Konflux_Pilot_Team"
        assert result["filters"]["environment"] == "PRODUCTION"
        assert result["filters"]["limit"] == 100

    @pytest.mark.asyncio
    async def test_get_deployments_excludes_github_pages(self, deployment_tools, mock_db_connection):
        """Test that deployments exclude github_pages by default."""
        await deployment_tools.call_tool("get_deployments", {})
        
        mock_db_connection.execute_query.assert_called_once()
        call_args = mock_db_connection.execute_query.call_args[0]
        query = call_args[0]

        assert "github_pages" in query.lower()
        assert "not like" in query.lower()

    @pytest.mark.asyncio
    async def test_get_deployments_database_error(self, deployment_tools, mock_db_connection):
        """Test handling of database errors."""
        mock_db_connection.execute_query.return_value = {
            "success": False,
            "error": "Database connection failed"
        }
        
        result_json = await deployment_tools.call_tool("get_deployments", {})
        result = json.loads(result_json)
        
        assert result["success"] is False
        assert "Database connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_get_deployments_exception_handling(self, deployment_tools, mock_db_connection):
        """Test exception handling in deployment tools."""
        mock_db_connection.execute_query.side_effect = Exception("Unexpected error")
        
        result_json = await deployment_tools.call_tool("get_deployments", {})
        result = json.loads(result_json)
        
        assert result["success"] is False
        assert "Unexpected error" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_tool_call(self, deployment_tools):
        """Test calling an unknown tool."""
        result_json = await deployment_tools.call_tool("unknown_tool", {})
        result = json.loads(result_json)
        
        assert result["success"] is False
        assert "Unknown deployment tool: unknown_tool" in result["error"]

    def test_deployment_tool_input_schema(self, deployment_tools):
        """Test that the deployment tool has proper input schema."""
        tools = deployment_tools.get_tools()
        get_deployments_tool = tools[0]
        
        schema = get_deployments_tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert schema["required"] == []
        
        properties = schema["properties"]
        expected_properties = [
            "project", "environment", "days_back", "start_date", 
            "end_date", "date_field", "limit"
        ]
        
        for prop in expected_properties:
            assert prop in properties
            assert "description" in properties[prop]

    def test_deployment_data_structure_validation(self, sample_deployment_data):
        """Test that sample deployment data has expected structure."""
        for deployment in sample_deployment_data:
            required_fields = [
                "project_name", "deployment_id", "display_title", "url", 
                "result", "environment", "finished_date"
            ]
            
            for field in required_fields:
                assert field in deployment
            
            assert isinstance(deployment["project_name"], str)
            assert isinstance(deployment["deployment_id"], str)
            assert isinstance(deployment["display_title"], str)
            assert isinstance(deployment["url"], str)
            assert isinstance(deployment["result"], str)
            assert isinstance(deployment["environment"], str)

    def test_deployment_environment_values(self, sample_deployment_data):
        """Test that deployment environments have valid values."""
        valid_environments = ["PRODUCTION", "STAGING", "DEVELOPMENT"]
        
        for deployment in sample_deployment_data:
            assert deployment["environment"] in valid_environments

    def test_deployment_result_values(self, sample_deployment_data):
        """Test that deployment results have valid values."""
        valid_results = ["SUCCESS", "FAILED", "CANCELLED", "RUNNING"]
        
        for deployment in sample_deployment_data:
            assert deployment["result"] in valid_results
