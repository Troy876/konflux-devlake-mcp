#!/usr/bin/env python3
"""
Konflux DevLake MCP Server - Tools Manager

Manages database tools and natural language query generation.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from mcp.types import Tool

from database_mcp_server.utils.logger import get_logger, log_tool_call, log_database_operation
from database_mcp_server.utils.db import DateTimeEncoder


class KonfluxDevLakeToolsManager:
    """Konflux DevLake Tools Manager"""
    
    def __init__(self, db_connection):
        self.db_connection = db_connection
        self.logger = get_logger(f"{__name__}.KonfluxDevLakeToolsManager")
    
    async def list_tools(self) -> List[Tool]:
        """List all available tools"""
        tools = [
            Tool(
                name="connect_database",
                description="🔌 **Database Connection Tool** - Establishes and verifies connection to the Konflux DevLake database. Use this tool to test connectivity before running other database operations. Returns connection status and database information. This is typically the first tool you should call to ensure the database is accessible.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="list_databases",
                description="📊 **Database Discovery Tool** - Lists all available databases in the Konflux DevLake system. This tool shows you what data sources are available, including the main 'lake' database containing incidents, deployments, and other Konflux operational data. Use this to explore what data is available before diving into specific tables.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="list_tables",
                description="📋 **Table Explorer Tool** - Lists all tables within a specific database. This tool helps you discover what data is available in each database. For the 'lake' database, you'll find tables like 'incidents', 'cicd_deployments', 'cicd_deployment_commits', and 'project_mapping'. Use this to understand the data structure before querying specific tables.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database": {"type": "string", "description": "Database name to explore. Common options: 'lake' (main DevLake data), 'information_schema' (MySQL system tables), 'test_db' (test database)"}
                    },
                    "required": ["database"]
                }
            ),
            Tool(
                name="get_table_schema",
                description="🔍 **Schema Inspector Tool** - Provides detailed schema information for a specific table, including column names, data types, constraints, and descriptions. This tool is essential for understanding the structure of tables before writing queries. For example, the 'incidents' table contains fields like 'incident_key', 'title', 'status', 'created_date', and 'lead_time_minutes'.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database": {"type": "string", "description": "Database name containing the table. Use 'lake' for main DevLake tables like incidents, deployments, etc."},
                        "table": {"type": "string", "description": "Table name to inspect. Common tables: 'incidents', 'cicd_deployments', 'cicd_deployment_commits', 'project_mapping'"}
                    },
                    "required": ["database", "table"]
                }
            ),
            Tool(
                name="execute_query",
                description="⚡ **Custom SQL Query Tool** - Executes custom SQL queries against the Konflux DevLake database. This powerful tool allows you to write complex queries to analyze incidents, deployments, and other operational data. Supports SELECT queries with filtering, aggregation, joins, and advanced SQL features. Use this for custom analysis, reporting, and data exploration. Example queries: 'SELECT * FROM lake.incidents WHERE status = \"DONE\"', 'SELECT COUNT(*) FROM lake.cicd_deployments WHERE environment = \"PRODUCTION\"'.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "SQL query to execute (e.g., 'SELECT * FROM lake.incidents LIMIT 10')"},
                        "limit": {"type": "integer", "description": "Maximum number of rows to return (default: 100, max: 1000)"}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="get_unique_incidents",
                description="🚨 **Incident Analysis Tool** - Retrieves all unique incidents from the Konflux DevLake database, automatically deduplicated by incident_key to show only the most recent version of each incident. This tool provides comprehensive incident data including incident_key, title, description, status, created_date, resolution_date, lead_time_minutes, component, and URL. Perfect for incident analysis, reporting, and understanding operational issues. Returns incidents sorted by creation date (newest first).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Maximum number of incidents to return (default: 100, max: 500)"}
                    },
                    "required": []
                }
            ),
            Tool(
                name="get_deployment_list",
                description="🚀 **Deployment Analytics Tool** - Retrieves deployment data from the Konflux DevLake database with advanced filtering capabilities. This tool provides comprehensive deployment information including deployment_id, display_title, url, result, environment, finished_date, and project details. Supports filtering by project (e.g., 'redhat-appstudio/infra-deployments'), environment (e.g., 'PRODUCTION'), time range (days_back), and result limits. Perfect for deployment frequency analysis, release tracking, and operational reporting. Returns deployments sorted by finished_date (newest first).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project name to filter by (default: 'redhat-appstudio/infra-deployments')"},
                        "environment": {"type": "string", "description": "Environment to filter by (default: 'PRODUCTION', options: 'PRODUCTION', 'STAGING', 'DEVELOPMENT')"},
                        "limit": {"type": "integer", "description": "Maximum number of deployments to return (default: 50, max: 200)"},
                        "days_back": {"type": "integer", "description": "Number of days back to include in results (default: 30, max: 365)"}
                    },
                    "required": []
                }
            )
        ]

        return tools
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool by name"""
        try:
            # Log tool call
            log_tool_call(name, arguments, success=True)
            
            if name == "connect_database":
                result = await self._connect_database_tool()
            elif name == "list_databases":
                result = await self._list_databases_tool()
            elif name == "list_tables":
                result = await self._list_tables_tool(arguments)
            elif name == "get_table_schema":
                result = await self._get_table_schema_tool(arguments)
            elif name == "execute_query":
                result = await self._execute_query_tool(arguments)
            elif name == "get_unique_incidents":
                result = await self._get_unique_incidents_tool(arguments)
            elif name == "get_deployment_list":
                result = await self._get_deployment_list_tool(arguments)
            else:
                result = {
                    "success": False,
                    "error": f"Unknown tool: {name}"
                }
            
            return json.dumps(result, indent=2, cls=DateTimeEncoder)
        
        except Exception as e:
            self.logger.error(f"Tool call failed: {e}")
            log_tool_call(name, arguments, success=False, error=str(e))
            error_result = {
                "success": False,
                "error": str(e),
                "tool_name": name,
                "arguments": arguments
            }
            return json.dumps(error_result, indent=2, cls=DateTimeEncoder)
    
    async def _connect_database_tool(self) -> Dict[str, Any]:
        """Connect to database tool"""
        self.logger.info("Connecting to database...")
        result = await self.db_connection.connect()
        log_database_operation("connect", success=result.get("success", False), error=result.get("error"))
        return result
    
    async def _list_databases_tool(self) -> Dict[str, Any]:
        """List databases tool"""
        self.logger.info("Listing databases...")
        result = await self.db_connection.execute_query("SHOW DATABASES")
        if result["success"]:
            log_database_operation("list_databases", success=True)
            return {
                "success": True,
                "databases": [db['Database'] for db in result["data"]]
            }
        log_database_operation("list_databases", success=False, error=result.get("error"))
        return result
    
    async def _list_tables_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List tables tool"""
        database = arguments.get("database")
        self.logger.info(f"Listing tables in database: {database}")
        result = await self.db_connection.execute_query(f"SHOW TABLES FROM `{database}`")
        if result["success"]:
            log_database_operation("list_tables", success=True)
            return {
                "success": True,
                "database": database,
                "tables": [list(table.values())[0] for table in result["data"]]
            }
        log_database_operation("list_tables", success=False, error=result.get("error"))
        return result
    
    async def _get_table_schema_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get table schema tool"""
        database = arguments.get("database")
        table = arguments.get("table")
        self.logger.info(f"Getting schema for table: {database}.{table}")
        
        # Get table schema
        schema_result = await self.db_connection.execute_query(f"DESCRIBE `{database}`.`{table}`")
        if not schema_result["success"]:
            log_database_operation("get_table_schema", success=False, error=schema_result.get("error"))
            return schema_result
        
        # Get row count
        count_result = await self.db_connection.execute_query(f"SELECT COUNT(*) as row_count FROM `{database}`.`{table}`")
        
        log_database_operation("get_table_schema", success=True)
        return {
            "success": True,
            "database": database,
            "table": table,
            "row_count": count_result["data"][0]["row_count"] if count_result["success"] else 0,
            "columns": schema_result["data"]
        }
    
    async def _execute_query_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute query tool"""
        query = arguments.get("query")
        limit = arguments.get("limit", 100)
        self.logger.info(f"Executing query with limit: {limit}")
        result = await self.db_connection.execute_query(query, limit)
        log_database_operation("execute_query", query=query, success=result.get("success", False), error=result.get("error"))
        return result
    
    async def _get_unique_incidents_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get all unique incidents from lake.incidents, deduplicated by incident_key (most recent only)"""
        limit = arguments.get("limit", 100)
        query = (
            "SELECT t1.* FROM lake.incidents t1 "
            "INNER JOIN (SELECT incident_key, MAX(id) AS max_id FROM lake.incidents GROUP BY incident_key) t2 "
            "ON t1.incident_key = t2.incident_key AND t1.id = t2.max_id "
            "ORDER BY t1.incident_key "
            f"LIMIT {limit}"
        )
        result = await self.db_connection.execute_query(query, limit)
        return result
    
    async def _get_deployment_list_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get deployment list with filtering by project, environment, and time range"""
        project = arguments.get("project", "redhat-appstudio/infra-deployments")
        environment = arguments.get("environment", "PRODUCTION")
        limit = arguments.get("limit", 50)
        days_back = arguments.get("days_back", 30)
        
        self.logger.info(f"Getting deployment list for project: {project}, environment: {environment}, days back: {days_back}, limit: {limit}")
        
        # Calculate the start date for the time range
        start_date = datetime.now() - timedelta(days=days_back)
        start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
        
        # Use the exact query structure provided by the user
        query = f"""
        WITH _deployment_commit_rank AS (
            SELECT
                pm.project_name,
                IF(cdc._raw_data_table != '', cdc._raw_data_table, cdc.cicd_scope_id) as _raw_data_table,
                cdc.id,
                cdc.display_title,
                cdc.url,
                cdc.cicd_deployment_id,
                cdc.cicd_scope_id,
                cdc.result,
                cdc.environment,
                cdc.finished_date,
                ROW_NUMBER() OVER(PARTITION BY cdc.cicd_deployment_id ORDER BY cdc.finished_date DESC) as _deployment_commit_rank
            FROM lake.cicd_deployment_commits cdc
            LEFT JOIN lake.project_mapping pm ON cdc.cicd_scope_id = pm.row_id AND pm.`table` = 'cicd_scopes'
            WHERE
                pm.project_name IN ('{project}')
                AND cdc.result = 'SUCCESS'
                AND cdc.environment = '{environment}'
                AND cdc.finished_date >= '{start_date_str}'
        )
        SELECT 
            project_name, 
            cicd_deployment_id as deployment_id,
            CASE WHEN display_title = '' THEN 'N/A' ELSE display_title END as display_title,
            url,
            url as metric_hidden,
            result,
            environment,
            finished_date
        FROM _deployment_commit_rank
        WHERE 
            _deployment_commit_rank = 1
            AND finished_date >= '{start_date_str}'
        ORDER BY finished_date DESC
        LIMIT {limit}
        """
        
        result = await self.db_connection.execute_query(query, limit)
        log_database_operation("get_deployment_list", query=query, success=result.get("success", False), error=result.get("error"))
        
        if result["success"]:
            return {
                "success": True,
                "project": project,
                "environment": environment,
                "days_back": days_back,
                "limit": limit,
                "query": query,
                "deployments": result["data"]
            }
        return result 