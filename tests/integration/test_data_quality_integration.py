"""
Data quality integration tests.

These tests verify data integrity, constraints, and relationships
in the actual database schema.
"""

import pytest
import json
from typing import Dict, Any

from utils.db import KonfluxDevLakeConnection
from tools.devlake.incident_tools import IncidentTools
from tools.devlake.deployment_tools import DeploymentTools


@pytest.mark.integration
@pytest.mark.asyncio
class TestDataQualityIntegration:
    """Integration tests for data quality and integrity."""

    async def test_incident_data_integrity(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test that incident data maintains integrity constraints."""
        # Query incidents
        result = await integration_db_connection.execute_query(
            "SELECT * FROM incidents WHERE incident_key = 'INC-2024-001'"
        )
        
        assert result["success"] is True
        assert len(result["data"]) == 1
        
        incident = result["data"][0]
        
        # Check required fields are present
        assert incident["incident_key"] is not None
        assert incident["title"] is not None
        assert incident["status"] is not None
        assert incident["created_date"] is not None
        
        # Check status is valid
        valid_statuses = ["OPEN", "IN_PROGRESS", "DONE", "CLOSED"]
        assert incident["status"] in valid_statuses

    async def test_deployment_data_integrity(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test that deployment data maintains integrity constraints."""
        # Query deployments
        result = await integration_db_connection.execute_query(
            "SELECT * FROM cicd_deployments WHERE deployment_id = 'deploy-api-prod-001'"
        )
        
        assert result["success"] is True
        assert len(result["data"]) == 1
        
        deployment = result["data"][0]
        
        # Check required fields are present
        assert deployment["deployment_id"] is not None
        assert deployment["display_title"] is not None
        assert deployment["environment"] is not None
        assert deployment["result"] is not None
        
        # Check environment is valid
        valid_environments = ["PRODUCTION", "STAGING", "DEVELOPMENT"]
        assert deployment["environment"] in valid_environments
        
        # Check result is valid
        valid_results = ["SUCCESS", "FAILURE", "ABORTED", "UNSTABLE"]
        assert deployment["result"] in valid_results

    async def test_deployment_commit_relationship(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test that deployments and deployment commits have proper relationships."""
        # Get a deployment
        deployment_result = await integration_db_connection.execute_query(
            "SELECT deployment_id FROM cicd_deployments LIMIT 1"
        )
        
        assert deployment_result["success"] is True
        assert len(deployment_result["data"]) > 0
        
        deployment_id = deployment_result["data"][0]["deployment_id"]
        
        # Check that corresponding deployment commit exists
        commit_result = await integration_db_connection.execute_query(
            f"SELECT * FROM cicd_deployment_commits WHERE deployment_id = '{deployment_id}'"
        )
        
        assert commit_result["success"] is True
        assert len(commit_result["data"]) > 0

    async def test_project_mapping_integrity(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test that project mapping data maintains integrity."""
        # Query project mappings
        result = await integration_db_connection.execute_query(
            "SELECT * FROM project_mapping"
        )
        
        assert result["success"] is True
        assert len(result["data"]) > 0
        
        for mapping in result["data"]:
            # Check required fields are present
            assert mapping["project_name"] is not None
            assert mapping["table"] is not None
            assert mapping["row_id"] is not None

    async def test_incident_date_consistency(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test that incident dates are consistent (created < updated < resolved)."""
        incident_tools = IncidentTools(integration_db_connection)
        
        result_json = await incident_tools.call_tool("get_incidents", {
            "status": "DONE"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        
        for incident in result["incidents"]:
            if incident.get("resolution_date"):
                # If resolved, created_date should be before resolution_date
                assert incident["created_date"] <= incident["resolution_date"]

    async def test_deployment_date_consistency(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test that deployment dates are consistent."""
        deployment_tools = DeploymentTools(integration_db_connection)
        
        result_json = await deployment_tools.call_tool("get_deployments", {
            "environment": "PRODUCTION"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        
        for deployment in result["deployments"]:
            if deployment.get("finished_date") and deployment.get("created_date"):
                # finished_date should be after created_date
                assert deployment["created_date"] <= deployment["finished_date"]

    async def test_unique_incident_keys(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test that incident keys are unique."""
        result = await integration_db_connection.execute_query(
            "SELECT incident_key, COUNT(*) as count FROM incidents GROUP BY incident_key"
        )
        
        assert result["success"] is True
        
        # Each incident_key should appear exactly once
        for row in result["data"]:
            assert row["count"] == 1

    async def test_unique_deployment_ids(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test that deployment IDs are unique."""
        result = await integration_db_connection.execute_query(
            "SELECT deployment_id, COUNT(*) as count FROM cicd_deployments GROUP BY deployment_id"
        )
        
        assert result["success"] is True
        
        # Each deployment_id should appear exactly once
        for row in result["data"]:
            assert row["count"] == 1

    async def test_incident_labels_json_format(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test that incident labels are properly formatted as JSON."""
        result = await integration_db_connection.execute_query(
            "SELECT incident_key, labels FROM incidents WHERE labels IS NOT NULL"
        )
        
        assert result["success"] is True
        
        for row in result["data"]:
            if row.get("labels"):
                # Labels should be valid JSON string or already parsed
                labels = row["labels"]
                if isinstance(labels, str):
                    # If string, should be valid JSON
                    try:
                        json.loads(labels)
                    except json.JSONDecodeError:
                        pytest.fail(f"Invalid JSON in labels: {labels}")

    async def test_null_handling_in_incidents(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test that NULL values are properly handled in incident queries."""
        incident_tools = IncidentTools(integration_db_connection)
        
        result_json = await incident_tools.call_tool("get_incidents", {})
        result = json.loads(result_json)
        
        assert result["success"] is True
        
        # Check that NULL fields don't cause issues
        for incident in result["incidents"]:
            # These fields might be NULL
            incident.get("assignee")
            incident.get("resolution_date")
            incident.get("description")
            # Should not raise KeyError

    async def test_null_handling_in_deployments(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test that NULL values are properly handled in deployment queries."""
        deployment_tools = DeploymentTools(integration_db_connection)
        
        result_json = await deployment_tools.call_tool("get_deployments", {})
        result = json.loads(result_json)
        
        assert result["success"] is True
        
        # Check that NULL fields don't cause issues
        for deployment in result["deployments"]:
            # These fields might be NULL
            deployment.get("branch")
            deployment.get("duration_sec")
            # Should not raise KeyError

    async def test_data_count_consistency(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test that data counts are consistent across related tables."""
        # Count deployments
        deployment_count_result = await integration_db_connection.execute_query(
            "SELECT COUNT(*) as count FROM cicd_deployments"
        )
        
        assert deployment_count_result["success"] is True
        deployment_count = deployment_count_result["data"][0]["count"]
        
        # Count deployment commits
        commit_count_result = await integration_db_connection.execute_query(
            "SELECT COUNT(*) as count FROM cicd_deployment_commits"
        )
        
        assert commit_count_result["success"] is True
        commit_count = commit_count_result["data"][0]["count"]
        
        # Should have at least as many commits as deployments
        # (each deployment should have at least one commit)
        assert commit_count >= deployment_count

