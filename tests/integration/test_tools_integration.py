"""
Tools integration tests.

These tests verify that the MCP tools work correctly
against a real database with actual data.
"""

import pytest
import json
from typing import Dict, Any

from tools.devlake.incident_tools import IncidentTools
from tools.devlake.deployment_tools import DeploymentTools
from utils.db import KonfluxDevLakeConnection


@pytest.mark.integration
@pytest.mark.asyncio
class TestIncidentToolsIntegration:
    """Integration tests for incident tools."""

    async def test_get_incidents_no_filters(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test getting incidents without filters."""
        incident_tools = IncidentTools(integration_db_connection)
        
        result_json = await incident_tools.call_tool("get_incidents", {})
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert "incidents" in result
        assert "filters" in result
        
        # Should have the test data incidents
        incidents = result["incidents"]
        assert len(incidents) >= 3  # We have 3 test incidents
        
        # Check incident structure
        for incident in incidents:
            assert "incident_key" in incident
            assert "title" in incident
            assert "status" in incident
            assert "created_date" in incident

    async def test_get_incidents_with_status_filter(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test getting incidents with status filter."""
        incident_tools = IncidentTools(integration_db_connection)
        
        result_json = await incident_tools.call_tool("get_incidents", {
            "status": "DONE"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert result["filters"]["status"] == "DONE"
        
        # All returned incidents should have DONE status
        incidents = result["incidents"]
        for incident in incidents:
            assert incident["status"] == "DONE"

    async def test_get_incidents_with_component_filter(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test getting incidents with component filter."""
        incident_tools = IncidentTools(integration_db_connection)
        
        result_json = await incident_tools.call_tool("get_incidents", {
            "component": "api-service"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert result["filters"]["component"] == "api-service"
        
        # All returned incidents should be for api-service
        incidents = result["incidents"]
        for incident in incidents:
            assert incident["component"] == "api-service"

    async def test_get_incidents_with_date_range(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test getting incidents with date range."""
        incident_tools = IncidentTools(integration_db_connection)
        
        result_json = await incident_tools.call_tool("get_incidents", {
            "start_date": "2024-01-15",
            "end_date": "2024-01-16"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert "2024-01-15" in result["filters"]["start_date"]
        assert "2024-01-16" in result["filters"]["end_date"]

    async def test_insert_and_query_test_incident(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database,
        sample_test_incident: Dict[str, Any]
    ):
        """Test inserting a test incident and querying it."""
        # Insert test incident
        insert_query = """
        INSERT INTO incidents (incident_key, title, description, status, severity, component, assignee, reporter, labels)
        VALUES (%(incident_key)s, %(title)s, %(description)s, %(status)s, %(severity)s, %(component)s, %(assignee)s, %(reporter)s, %(labels)s)
        """
        
        # Format the query with actual values since execute_query doesn't support params
        formatted_query = insert_query % {
            'incident_key': f"'{sample_test_incident['incident_key']}'",
            'title': f"'{sample_test_incident['title']}'", 
            'description': f"'{sample_test_incident['description']}'",
            'status': f"'{sample_test_incident['status']}'",
            'severity': f"'{sample_test_incident['severity']}'",
            'component': f"'{sample_test_incident['component']}'",
            'assignee': f"'{sample_test_incident['assignee']}'",
            'reporter': f"'{sample_test_incident['reporter']}'",
            'labels': f"'{sample_test_incident['labels']}'"
        }
        result = await integration_db_connection.execute_query(formatted_query)
        assert result["success"] is True
        
        # Query for the incident
        incident_tools = IncidentTools(integration_db_connection)
        result_json = await incident_tools.call_tool("get_incidents", {
            "component": "test-service"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        incidents = result["incidents"]
        
        # Should find our test incident
        test_incident = next((inc for inc in incidents if inc["incident_key"] == "TEST-INT-001"), None)
        assert test_incident is not None
        assert test_incident["title"] == "Integration Test Incident"
        assert test_incident["status"] == "OPEN"


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeploymentToolsIntegration:
    """Integration tests for deployment tools."""

    async def test_get_deployments_no_filters(
        self,
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test getting deployments without filters (should default to PRODUCTION + Konflux_Pilot_Team)."""
        deployment_tools = DeploymentTools(integration_db_connection)
    
        result_json = await deployment_tools.call_tool("get_deployments", {})
        result = json.loads(result_json)
    
        assert result["success"] is True
        assert "deployments" in result
        assert "filters" in result
    
        # Should have the PRODUCTION deployments from Konflux_Pilot_Team (2 deployments)
        deployments = result["deployments"]
        assert len(deployments) == 2  # Only PRODUCTION deployments from Konflux_Pilot_Team
        
        # All deployments should be PRODUCTION and from Konflux_Pilot_Team
        for deployment in deployments:
            assert deployment["environment"] == "PRODUCTION"
        
        # Check deployment structure
        for deployment in deployments:
            assert "deployment_id" in deployment
            assert "display_title" in deployment
            assert "result" in deployment
            assert "environment" in deployment

    async def test_get_deployments_with_environment_filter(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test getting deployments with environment filter."""
        deployment_tools = DeploymentTools(integration_db_connection)
        
        result_json = await deployment_tools.call_tool("get_deployments", {
            "environment": "PRODUCTION"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert result["filters"]["environment"] == "PRODUCTION"
        
        # All returned deployments should be PRODUCTION
        deployments = result["deployments"]
        for deployment in deployments:
            assert deployment["environment"] == "PRODUCTION"

    async def test_get_deployments_with_project_filter(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test getting deployments with project filter."""
        deployment_tools = DeploymentTools(integration_db_connection)
        
        result_json = await deployment_tools.call_tool("get_deployments", {
            "project": "Konflux_Pilot_Team"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert result["filters"]["project"] == "Konflux_Pilot_Team"
        
        # All returned deployments should be for Konflux_Pilot_Team
        deployments = result["deployments"]
        for deployment in deployments:
            assert deployment["project_name"] == "Konflux_Pilot_Team"
            assert deployment["environment"] == "PRODUCTION"  # Should still be PRODUCTION by default

    async def test_insert_and_query_test_deployment(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database,
        sample_test_deployment: Dict[str, Any]
    ):
        """Test inserting a test deployment and querying it."""
        # Insert test deployment into both tables
        insert_deployment_query = """
        INSERT INTO cicd_deployments (deployment_id, display_title, url, result, status, environment, project, commit_sha, branch)
        VALUES (%(deployment_id)s, %(display_title)s, %(url)s, %(result)s, %(status)s, %(environment)s, %(project)s, %(commit_sha)s, %(branch)s)
        """
        
        # Format the query with actual values since execute_query doesn't support params
        formatted_deployment_query = insert_deployment_query % {
            'deployment_id': f"'{sample_test_deployment['deployment_id']}'",
            'display_title': f"'{sample_test_deployment['display_title']}'",
            'url': f"'{sample_test_deployment['url']}'",
            'result': f"'{sample_test_deployment['result']}'",
            'status': f"'{sample_test_deployment['status']}'",
            'environment': f"'PRODUCTION'",  # Change to PRODUCTION so it can be found by the tool
            'project': f"'Konflux_Pilot_Team'",  # Change to Konflux_Pilot_Team so it can be found by the tool
            'commit_sha': f"'{sample_test_deployment['commit_sha']}'",
            'branch': f"'{sample_test_deployment['branch']}'"
        }
        result = await integration_db_connection.execute_query(formatted_deployment_query)
        assert result["success"] is True
        
        # Insert corresponding deployment commit record
        insert_commit_query = """
        INSERT INTO cicd_deployment_commits (
            deployment_id, cicd_deployment_id, cicd_scope_id, display_title, url, result, environment, finished_date,
            commit_sha, commit_message, commit_author, commit_date, _raw_data_table
        ) VALUES (
            '%s', '%s', 'test-scope-001', '%s', '%s', '%s', 'PRODUCTION', NOW(),
            '%s', 'Integration test deployment', 'test@example.com', NOW(), 'raw_deployments'
        )
        """ % (
            sample_test_deployment['deployment_id'], sample_test_deployment['deployment_id'],
            sample_test_deployment['display_title'], sample_test_deployment['url'], 
            sample_test_deployment['result'], sample_test_deployment['commit_sha']
        )
        
        result = await integration_db_connection.execute_query(insert_commit_query)
        assert result["success"] is True
        
        # Insert project mapping for the test (use Konflux_Pilot_Team to match the tool's default)
        insert_mapping_query = """
        INSERT INTO project_mapping (project_name, `table`, row_id, raw_data_table, params)
        VALUES ('Konflux_Pilot_Team', 'cicd_scopes', 'test-scope-001', 'raw_deployments', '{"source": "test"}')
        """
        
        result = await integration_db_connection.execute_query(insert_mapping_query)
        assert result["success"] is True
        
        # Query for the deployment (use defaults since we inserted with default values)
        deployment_tools = DeploymentTools(integration_db_connection)
        result_json = await deployment_tools.call_tool("get_deployments", {})
        result = json.loads(result_json)
        
        assert result["success"] is True
        deployments = result["deployments"]
        
        # Should find our test deployment
        test_deployment = next((dep for dep in deployments if dep["deployment_id"] == "test-deploy-001"), None)
        assert test_deployment is not None
        assert test_deployment["display_title"] == "Integration Test Deployment"
        assert test_deployment["result"] == "SUCCESS"

    async def test_deployment_date_filtering(
        self, 
        integration_db_connection: KonfluxDevLakeConnection,
        clean_database
    ):
        """Test deployment date filtering."""
        deployment_tools = DeploymentTools(integration_db_connection)
        
        result_json = await deployment_tools.call_tool("get_deployments", {
            "start_date": "2024-01-15",
            "end_date": "2024-01-17"
        })
        result = json.loads(result_json)
        
        assert result["success"] is True
        assert "2024-01-15" in result["filters"]["start_date"]
        assert "2024-01-17" in result["filters"]["end_date"]
        
        # Should have deployments within the date range
        deployments = result["deployments"]
        assert len(deployments) > 0
