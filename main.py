#!/usr/bin/env python3
"""
Konflux DevLake MCP Server - Natural Language Database Querying

A streamlined MCP server that connects to databases and provides natural language query capabilities.
Based on the doris_mcp_server architecture but simplified for database-only operations.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# MCP imports with compatibility handling
try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.types import (
        CallToolRequest,
        CallToolResult,
        ListToolsRequest,
        ListToolsResult,
        Tool,
        TextContent,
    )
    MCP_VERSION = "latest"
except ImportError as e:
    print(f"Failed to import MCP components: {e}")
    print("Please install MCP: pip install mcp")
    sys.exit(1)

# Import our modules
from database_mcp_server.tools.tools_manager import KonfluxDevLakeToolsManager
from database_mcp_server.utils.config import KonfluxDevLakeConfig
from database_mcp_server.utils.db import KonfluxDevLakeConnection, DateTimeEncoder
from database_mcp_server.utils.logger import get_logger, log_system_info, shutdown_logging
from database_mcp_server.utils.security import KonfluxDevLakeSecurityManager, SQLInjectionDetector, DataMasking


class KonfluxDevLakeMCPServer:
    """Konflux DevLake MCP Server"""
    
    def __init__(self, config: KonfluxDevLakeConfig):
        self.config = config
        self.server = Server("konflux-devlake-mcp-server")
        self.db_connection = KonfluxDevLakeConnection(config.get_database_config())
        self.security_manager = KonfluxDevLakeSecurityManager(config)
        self.sql_injection_detector = SQLInjectionDetector()
        self.data_masking = DataMasking()
        self.tools_manager = KonfluxDevLakeToolsManager(self.db_connection)
        self.logger = get_logger(f"{__name__}.KonfluxDevLakeMCPServer")
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup MCP protocol handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """Handle tool list request"""
            try:
                self.logger.info("Handling tool list request")
                tools = await self.tools_manager.list_tools()
                self.logger.info(f"Returning {len(tools)} tools")
                return tools
            except Exception as e:
                self.logger.error(f"Failed to handle tool list request: {e}")
                return []
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool call request"""
            try:
                self.logger.info(f"Handling tool call request: {name}")
                
                # Security validation for query-based tools
                if name in ["execute_query", "ask_database"]:
                    query = arguments.get("query", "")
                    if query:
                        # Validate SQL query
                        is_valid, validation_msg = self.security_manager.validate_sql_query(query)
                        if not is_valid:
                            self.logger.warning(f"SQL query validation failed: {validation_msg}")
                            error_result = {
                                "success": False,
                                "error": f"SQL query validation failed: {validation_msg}",
                                "security_check": "failed"
                            }
                            return [TextContent(type="text", text=json.dumps(error_result, indent=2, cls=DateTimeEncoder))]
                        
                        # Check for SQL injection
                        is_injection, patterns = self.sql_injection_detector.detect_sql_injection(query)
                        if is_injection:
                            self.logger.warning(f"Potential SQL injection detected: {patterns}")
                            error_result = {
                                "success": False,
                                "error": "Potential SQL injection detected",
                                "security_check": "failed",
                                "detected_patterns": patterns
                            }
                            return [TextContent(type="text", text=json.dumps(error_result, indent=2, cls=DateTimeEncoder))]
                
                # Validate database and table names
                if name in ["list_tables", "get_table_schema"]:
                    database = arguments.get("database", "")
                    is_valid, validation_msg = self.security_manager.validate_database_name(database)
                    if not is_valid:
                        self.logger.warning(f"Database name validation failed: {validation_msg}")
                        error_result = {
                            "success": False,
                            "error": f"Database name validation failed: {validation_msg}",
                            "security_check": "failed"
                        }
                        return [TextContent(type="text", text=json.dumps(error_result, indent=2, cls=DateTimeEncoder))]
                
                if name == "get_table_schema":
                    table = arguments.get("table", "")
                    is_valid, validation_msg = self.security_manager.validate_table_name(table)
                    if not is_valid:
                        self.logger.warning(f"Table name validation failed: {validation_msg}")
                        error_result = {
                            "success": False,
                            "error": f"Table name validation failed: {validation_msg}",
                            "security_check": "failed"
                        }
                        return [TextContent(type="text", text=json.dumps(error_result, indent=2, cls=DateTimeEncoder))]
                
                # Execute tool
                result = await self.tools_manager.call_tool(name, arguments)
                
                # Mask sensitive data in results
                try:
                    result_dict = json.loads(result)
                    if isinstance(result_dict, dict) and "data" in result_dict:
                        result_dict["data"] = self.data_masking.mask_database_result(result_dict["data"])
                        result = json.dumps(result_dict, indent=2, cls=DateTimeEncoder)
                except:
                    pass  # If result is not JSON, leave as is
                
                return [TextContent(type="text", text=result)]
            except Exception as e:
                self.logger.error(f"Failed to handle tool call request: {e}")
                error_result = json.dumps(
                    {
                        "error": f"Tool call failed: {str(e)}",
                        "tool_name": name,
                        "arguments": arguments,
                    },
                    ensure_ascii=False,
                    indent=2,
                    cls=DateTimeEncoder,
                )
                return [TextContent(type="text", text=error_result)]
    
    async def start_stdio(self):
        """Start stdio transport mode"""
        self.logger.info("Starting Konflux DevLake MCP Server (stdio mode)")
        
        try:
            from mcp.server.stdio import stdio_server
            
            async with stdio_server() as (read_stream, write_stream):
                init_options = InitializationOptions(
                    server_name="simple-db-mcp-server",
                    server_version="1.0.0",
                    capabilities={
                        "tools": {}
                    }
                )
                
                await self.server.run(read_stream, write_stream, init_options)
        
        except Exception as e:
            self.logger.error(f"stdio server startup failed: {e}")
            raise
    
    async def start_http(self, host: str, port: int):
        """Start HTTP transport mode"""
        self.logger.info(f"Starting Konflux DevLake MCP Server (HTTP mode) - {host}:{port}")
        
        try:
            import uvicorn
            from starlette.applications import Starlette
            from starlette.requests import Request
            from starlette.responses import JSONResponse
            from starlette.routing import Route
            from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
            
            # Create session manager
            session_manager = StreamableHTTPSessionManager(
                app=self.server,
                json_response=True,
                stateless=False
            )
            
            # Health check endpoint
            async def health_check(request: Request):
                return JSONResponse({
                    "status": "healthy", 
                    "service": "simple-db-mcp-server",
                    "timestamp": datetime.now().isoformat(),
                    "security_stats": self.security_manager.get_security_stats()
                })
            
            # Security stats endpoint
            async def security_stats(request: Request):
                return JSONResponse({
                    "security_stats": self.security_manager.get_security_stats(),
                    "timestamp": datetime.now().isoformat()
                })
            
            # Create ASGI app
            app = Starlette(routes=[
                Route("/health", health_check, methods=["GET"]),
                Route("/security/stats", security_stats, methods=["GET"]),
            ])
            
            # Custom ASGI app that handles MCP requests
            async def mcp_app(scope, receive, send):
                if scope["type"] == "http":
                    path = scope.get("path", "")
                    
                    if path.startswith("/health") or path.startswith("/security"):
                        await app(scope, receive, send)
                        return
                    
                    if path == "/mcp" or path.startswith("/mcp/"):
                        await session_manager.handle_request(scope, receive, send)
                        return
                    
                    # 404 for other paths
                    from starlette.responses import Response
                    response = Response("Not Found", status_code=404)
                    await response(scope, receive, send)
            
            # Start server
            config = uvicorn.Config(app=mcp_app, host=host, port=port, log_level="info")
            server = uvicorn.Server(config)
            
            async with session_manager.run():
                await server.serve()
        
        except Exception as e:
            self.logger.error(f"HTTP server startup failed: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown server"""
        self.logger.info("Shutting down Konflux DevLake MCP Server")
        try:
            # Cleanup security manager
            self.security_manager.cleanup_expired_tokens()
            
            # Close database connection
            await self.db_connection.close()
            
            self.logger.info("Server shutdown complete")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")


def create_arg_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Konflux DevLake MCP Server - Natural Language Database Querying",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m simple_db_mcp_server --transport stdio --db-host localhost --db-user root --db-password password
  python -m simple_db_mcp_server --transport http --host 0.0.0.0 --port 3000 --db-host localhost --db-user root --db-password password
        """
    )
    
    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol type: stdio (local), http (HTTP server)"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address for HTTP mode"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        help="Port number for HTTP mode"
    )
    
    parser.add_argument(
        "--db-host",
        type=str,
        default="localhost",
        help="Database host address"
    )
    
    parser.add_argument(
        "--db-port",
        type=int,
        default=3306,
        help="Database port number"
    )
    
    parser.add_argument(
        "--db-user",
        type=str,
        default="root",
        help="Database username"
    )
    
    parser.add_argument(
        "--db-password",
        type=str,
        default="",
        help="Database password"
    )
    
    parser.add_argument(
        "--db-database",
        type=str,
        default="",
        help="Default database name"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level"
    )
    
    return parser


async def main():
    """Main function"""
    parser = create_arg_parser()
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Create configuration
    config = KonfluxDevLakeConfig()
    
    # Override with command line arguments
    config.database.host = args.db_host
    config.database.port = args.db_port
    config.database.user = args.db_user
    config.database.password = args.db_password
    config.database.database = args.db_database
    config.server.transport = args.transport
    config.server.host = args.host
    config.server.port = args.port
    config.logging.level = args.log_level
    
    # Validate configuration
    if not config.validate():
        logger = get_logger(__name__)
        logger.error("Invalid configuration")
        logger.info(config)
        return 1
    
    # Log system information
    log_system_info()
    
    logger = get_logger(__name__)
    logger.info("Starting Konflux DevLake MCP Server...")
    logger.info(f"Transport: {args.transport}")
    logger.info(f"Log Level: {config.logging.level}")
    logger.info(config)
    
    # Create server instance
    server = KonfluxDevLakeMCPServer(config)
    
    try:
        if args.transport == "stdio":
            await server.start_stdio()
        elif args.transport == "http":
            await server.start_http(args.host, args.port)
        else:
            logger.error(f"Unsupported transport protocol: {args.transport}")
            return 1
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down server...")
    except Exception as e:
        logger.error(f"Server runtime error: {e}")
        return 1
    finally:
        await server.shutdown()
        shutdown_logging()
    
    return 0


def main_sync():
    """Synchronous main function for entry point"""
    exit_code = asyncio.run(main())
    exit(exit_code)


if __name__ == "__main__":
    main_sync() 