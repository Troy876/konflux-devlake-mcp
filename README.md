# Konflux DevLake MCP Server

A MCP server that enables natural language querying of Konflux DevLake databases. This server acts as a bridge between AI assistants and your DevLake database, allowing you to ask questions in plain language and get structured data back.

## 🚀 Quick Start

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Start the server**:
```bash
python run_server.py --transport http --host 0.0.0.0 --port 3000 --db-host localhost --db-port 3306 --db-user root --db-password password --db-database lake
```

## 🔧 Configuration

### Command Line Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--transport` | Transport protocol (stdio/http) | `--transport http` |
| `--host` | Server host | `--host 0.0.0.0` |
| `--port` | Server port | `--port 3000` |
| `--db-host` | Database host | `--db-host localhost` |
| `--db-port` | Database port | `--db-port 3306` |
| `--db-user` | Database username | `--db-user root` |
| `--db-password` | Database password | `--db-password your_password` |
| `--db-database` | Database name | `--db-database lake` |
| `--log-level` | Logging level | `--log-level INFO` |

### Environment Variables (Alternative)

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=your_password
export DB_DATABASE=lake
export TRANSPORT=http
export SERVER_HOST=0.0.0.0
export SERVER_PORT=3000
export LOG_LEVEL=INFO
```

Then run:
```bash
python run_server.py
```

### Help Command
```bash
python run_server.py --help
```

## 🛠️ Available Tools

This server provides several specialized tools for working with your DevLake data:

- **Database Tools**: Connect to your database, list available databases and tables, execute custom SQL queries, and get detailed table schemas
- **Incident Analysis**: Get unique incidents with automatic deduplication, analyze incident patterns, and track resolution times
- **Deployment Tracking**: Monitor deployment data with advanced filtering, track deployment frequency, and analyze service distribution

## 📊 Features

- **Natural Language Processing**: Convert plain English questions into SQL queries automatically
- **Security First**: Built-in SQL injection detection and comprehensive query validation to protect your data
- **DevLake Integration**: Specialized tools for analyzing incident and deployment data from Konflux DevLake
- **Flexible Transport**: Support for both HTTP and stdio transport protocols
- **Comprehensive Logging**: Detailed logging with rotation and error tracking for debugging and monitoring

## 🔒 Security

Your data security is our priority:

- **SQL Injection Protection**: Automatic detection and prevention of potential SQL injection attacks
- **Query Validation**: Every query is validated and sanitized before execution
- **Data Masking**: Sensitive information is automatically masked in query results
- **Access Control**: Database-level access control ensures only authorized operations are performed

## 📈 Monitoring

Keep track of your server's health and performance:

- **Application Logs**: `logs/konflux_devlake_mcp_server.log` - General server activity and operations
- **Error Logs**: `logs/konflux_devlake_mcp_server_error.log` - Detailed error information for troubleshooting
- **Health Check**: `GET http://localhost:3000/health` - Monitor server status and connectivity

## 🤝 Contributing

We welcome contributions to improve this project:

1. Fork the repository
2. Create a feature branch for your changes
3. Make your improvements and add tests
4. Submit a pull request with a clear description of your changes

## 💡 Use Cases

This MCP server is particularly useful for:

- **Data Analysts**: Quickly query DevLake data without writing complex SQL
- **DevOps Teams**: Monitor incidents and deployments through natural language queries
- **AI Assistants**: Enable AI tools to access and analyze your DevLake data
- **Business Intelligence**: Generate reports and insights from your DevLake database
- **Development Teams**: Debug and analyze application performance data 