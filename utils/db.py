#!/usr/bin/env python3
"""
Konflux DevLake MCP Server - Database Connection Utility
"""

import json
import logging
from datetime import datetime, date
from typing import Any, Dict, Optional

import pymysql
from pymysql.cursors import DictCursor

from database_mcp_server.utils.logger import get_logger, log_database_operation


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects"""
    
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def serialize_datetime_objects(data):
    """Recursively serialize datetime objects in data structures"""
    if isinstance(data, dict):
        return {key: serialize_datetime_objects(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [serialize_datetime_objects(item) for item in data]
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    else:
        return data


class KonfluxDevLakeConnection:
    """Konflux DevLake Connection Manager"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connection = None
        self.logger = get_logger(f"{__name__}.KonfluxDevLakeConnection")
    
    async def connect(self) -> Dict[str, Any]:
        """Connect to the database"""
        try:
            self.logger.info(f"Connecting to database at {self.config['host']}:{self.config['port']}")
            
            self.connection = pymysql.connect(
                host=self.config['host'],
                port=self.config['port'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config.get('database'),
                charset='utf8mb4',
                cursorclass=DictCursor
            )
            
            # Test the connection
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT VERSION() as version")
                result = cursor.fetchone()
                
            self.logger.info("Database connection established successfully")
            log_database_operation("connect", success=True)
            
            return {
                "success": True,
                "message": "Database connected successfully",
                "version": result['version'] if result else "Unknown",
                "connection_info": {
                    "host": self.config['host'],
                    "port": self.config['port'],
                    "user": self.config['user'],
                    "database": self.config.get('database')
                }
            }
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            log_database_operation("connect", success=False, error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    async def execute_query(self, query: str, limit: int = 100) -> Dict[str, Any]:
        """Execute a SQL query"""
        try:
            if not self.connection:
                self.logger.info("No active connection, establishing connection...")
                await self.connect()
            
            self.logger.debug(f"Executing query: {query[:100]}...")
            
            with self.connection.cursor() as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                
            # Serialize datetime objects to prevent JSON serialization issues
            serialized_results = serialize_datetime_objects(results[:limit])
                
            self.logger.info(f"Query executed successfully, returned {len(results)} rows")
            log_database_operation("execute_query", query=query, success=True)
            
            return {
                "success": True,
                "query": query,
                "row_count": len(results),
                "data": serialized_results
            }
        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            log_database_operation("execute_query", query=query, success=False, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    async def close(self):
        """Close database connection"""
        if self.connection:
            self.logger.info("Closing database connection...")
            self.connection.close()
            self.logger.info("Database connection closed")
    
    async def test_connection(self) -> bool:
        """Test if the connection is still valid"""
        try:
            if not self.connection:
                self.logger.debug("No active connection to test")
                return False
            
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            self.logger.debug("Connection test successful")
            return True
        except Exception as e:
            self.logger.warning(f"Connection test failed: {e}")
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information"""
        return {
            "host": self.config['host'],
            "port": self.config['port'],
            "user": self.config['user'],
            "database": self.config.get('database'),
            "connected": self.connection is not None
        } 