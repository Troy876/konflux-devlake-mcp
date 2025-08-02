#!/usr/bin/env python3
"""
Konflux DevLake MCP Server - Configuration Utility
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = ""


@dataclass
class ServerConfig:
    """Server configuration"""
    transport: str = "stdio"
    host: str = "0.0.0.0"
    port: int = 3000


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class KonfluxDevLakeConfig:
    """Konflux DevLake MCP Server Configuration"""
    
    def __init__(self):
        self.database = DatabaseConfig()
        self.server = ServerConfig()
        self.logging = LoggingConfig()
        self._load_from_env()
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        # Database configuration
        self.database.host = os.getenv("DB_HOST", self.database.host)
        self.database.port = int(os.getenv("DB_PORT", str(self.database.port)))
        self.database.user = os.getenv("DB_USER", self.database.user)
        self.database.password = os.getenv("DB_PASSWORD", self.database.password)
        self.database.database = os.getenv("DB_DATABASE", self.database.database)
        
        # Server configuration
        self.server.transport = os.getenv("TRANSPORT", self.server.transport)
        self.server.host = os.getenv("SERVER_HOST", self.server.host)
        self.server.port = int(os.getenv("SERVER_PORT", str(self.server.port)))
        
        # Logging configuration
        self.logging.level = os.getenv("LOG_LEVEL", self.logging.level)
    
    def get_database_config(self) -> dict:
        """Get database configuration as dictionary"""
        return {
            "host": self.database.host,
            "port": self.database.port,
            "user": self.database.user,
            "password": self.database.password,
            "database": self.database.database
        }
    
    def get_server_config(self) -> dict:
        """Get server configuration as dictionary"""
        return {
            "transport": self.server.transport,
            "host": self.server.host,
            "port": self.server.port
        }
    
    def validate(self) -> bool:
        """Validate configuration"""
        if not self.database.host:
            return False
        if not self.database.user:
            return False
        if self.database.port <= 0 or self.database.port > 65535:
            return False
        if self.server.port <= 0 or self.server.port > 65535:
            return False
        return True
    
    def __str__(self) -> str:
        """String representation of configuration"""
        return f"""
Konflux DevLake MCP Server Configuration:
  Database:
    Host: {self.database.host}
    Port: {self.database.port}
    User: {self.database.user}
    Database: {self.database.database}
  Server:
    Transport: {self.server.transport}
    Host: {self.server.host}
    Port: {self.server.port}
  Logging:
    Level: {self.logging.level}
        """ 