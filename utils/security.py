#!/usr/bin/env python3
"""
Konflux DevLake MCP Server - Security Utility
"""

import hashlib
import hmac
import logging
import re
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from utils.logger import get_logger


class KonfluxDevLakeSecurityManager:
    """Konflux DevLake Security Manager"""
    
    def __init__(self, config):
        self.config = config
        self.logger = get_logger(f"{__name__}.KonfluxDevLakeSecurityManager")
        self.allowed_ips = getattr(config, 'allowed_ips', [])
        self.api_keys = getattr(config, 'api_keys', {})
        self.session_tokens = {}
        self.rate_limits = {}
        
    def validate_sql_query(self, query: str) -> Tuple[bool, str]:
        """Validate SQL query for security - ALLOWS ALL SELECT QUERIES"""
        try:
            # Convert to lowercase for easier checking
            query_lower = query.lower().strip()
            
            # Check if it's a SELECT query - ALLOW ALL SELECT QUERIES
            if query_lower.startswith('select'):
                self.logger.info("SELECT query detected - allowing all SELECT operations")
                return True, "SELECT query allowed"
            
            # Check for dangerous operations (only for non-SELECT queries)
            dangerous_keywords = [
                'drop', 'delete', 'truncate', 'alter', 'create', 'insert', 'update',
                'grant', 'revoke', 'backup', 'restore', 'shutdown', 'kill'
            ]
            
            # Check for dangerous patterns (only for non-SELECT queries)
            dangerous_patterns = [
                r';\s*$',  # Multiple statements
                r'--',     # SQL comments
                r'/\*.*?\*/',  # Multi-line comments
                r'union\s+select',  # UNION attacks
                r'exec\s*\(',  # Command execution
                r'xp_cmdshell',  # SQL Server command shell
            ]
            
            # Check for dangerous keywords (only for non-SELECT queries)
            for keyword in dangerous_keywords:
                if keyword in query_lower:
                    self.logger.warning(f"Potentially dangerous SQL keyword detected: {keyword}")
                    return False, f"Dangerous SQL keyword detected: {keyword}"
            
            # Check for dangerous patterns (only for non-SELECT queries)
            for pattern in dangerous_patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    self.logger.warning(f"Potentially dangerous SQL pattern detected: {pattern}")
                    return False, f"Dangerous SQL pattern detected"
            
            # Check for balanced parentheses
            if query_lower.count('(') != query_lower.count(')'):
                self.logger.warning("Unbalanced parentheses in SQL query")
                return False, "Unbalanced parentheses in SQL query"
            
            # Check for reasonable query length
            if len(query) > 10000:  # 10KB limit
                self.logger.warning("SQL query too long")
                return False, "SQL query too long"
            
            return True, "Query validation passed"
            
        except Exception as e:
            self.logger.error(f"Error validating SQL query: {e}")
            return False, f"Error validating SQL query: {str(e)}"
    
    def sanitize_input(self, input_str: str) -> str:
        """Sanitize user input"""
        if not input_str:
            return ""
        
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '|', '`', '$', '(', ')', '{', '}']
        sanitized = input_str
        
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        # Remove multiple spaces
        sanitized = ' '.join(sanitized.split())
        
        return sanitized
    
    def validate_database_name(self, db_name: str) -> Tuple[bool, str]:
        """Validate database name"""
        if not db_name:
            return False, "Database name cannot be empty"
        
        # Check for valid characters
        if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
            return False, "Database name contains invalid characters"
        
        # Check length
        if len(db_name) > 64:
            return False, "Database name too long"
        
        # Check for reserved words
        reserved_words = [
            'information_schema', 'mysql', 'performance_schema', 'sys',
            'test', 'tmp', 'temp'
        ]
        
        if db_name.lower() in reserved_words:
            return False, f"Database name '{db_name}' is reserved"
        
        return True, "Database name validation passed"
    
    def validate_table_name(self, table_name: str) -> Tuple[bool, str]:
        """Validate table name"""
        if not table_name:
            return False, "Table name cannot be empty"
        
        # Check for valid characters
        if not re.match(r'^[a-zA-Z0-9_]+$', table_name):
            return False, "Table name contains invalid characters"
        
        # Check length
        if len(table_name) > 64:
            return False, "Table name too long"
        
        return True, "Table name validation passed"
    
    def generate_api_key(self, user_id: str) -> str:
        """Generate API key for user"""
        # Generate a random key
        key = secrets.token_urlsafe(32)
        
        # Store the key
        self.api_keys[user_id] = {
            'key': key,
            'created': datetime.now(),
            'last_used': None
        }
        
        self.logger.info(f"Generated API key for user: {user_id}")
        return key
    
    def validate_api_key(self, api_key: str) -> Tuple[bool, str]:
        """Validate API key"""
        if not api_key:
            return False, "API key is required"
        
        # Check if key exists
        for user_id, key_info in self.api_keys.items():
            if key_info['key'] == api_key:
                # Update last used time
                key_info['last_used'] = datetime.now()
                return True, f"Valid API key for user: {user_id}"
        
        return False, "Invalid API key"
    
    def generate_session_token(self, user_id: str) -> str:
        """Generate session token"""
        token = secrets.token_urlsafe(32)
        expiry = datetime.now() + timedelta(hours=24)
        
        self.session_tokens[token] = {
            'user_id': user_id,
            'created': datetime.now(),
            'expires': expiry
        }
        
        self.logger.info(f"Generated session token for user: {user_id}")
        return token
    
    def validate_session_token(self, token: str) -> Tuple[bool, str]:
        """Validate session token"""
        if not token:
            return False, "Session token is required"
        
        if token not in self.session_tokens:
            return False, "Invalid session token"
        
        token_info = self.session_tokens[token]
        
        # Check if token has expired
        if datetime.now() > token_info['expires']:
            del self.session_tokens[token]
            return False, "Session token has expired"
        
        return True, f"Valid session token for user: {token_info['user_id']}"
    
    def check_rate_limit(self, user_id: str, operation: str) -> Tuple[bool, str]:
        """Check rate limit for user operation"""
        current_time = datetime.now()
        key = f"{user_id}:{operation}"
        
        if key not in self.rate_limits:
            self.rate_limits[key] = []
        
        # Remove old entries (older than 1 minute)
        self.rate_limits[key] = [
            time for time in self.rate_limits[key]
            if current_time - time < timedelta(minutes=1)
        ]
        
        # Check if rate limit exceeded (max 100 operations per minute)
        if len(self.rate_limits[key]) >= 100:
            return False, "Rate limit exceeded"
        
        # Add current operation
        self.rate_limits[key].append(current_time)
        
        return True, "Rate limit check passed"
    
    def validate_ip_address(self, ip_address: str) -> bool:
        """Validate IP address"""
        if not self.allowed_ips:
            return True  # No restrictions
        
        return ip_address in self.allowed_ips
    
    def log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security event"""
        self.logger.warning(f"Security event - {event_type}: {details}")
    
    def cleanup_expired_tokens(self):
        """Clean up expired session tokens"""
        current_time = datetime.now()
        expired_tokens = []
        
        for token, token_info in self.session_tokens.items():
            if current_time > token_info['expires']:
                expired_tokens.append(token)
        
        for token in expired_tokens:
            del self.session_tokens[token]
        
        if expired_tokens:
            self.logger.info(f"Cleaned up {len(expired_tokens)} expired session tokens")
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics"""
        return {
            'active_api_keys': len(self.api_keys),
            'active_session_tokens': len(self.session_tokens),
            'rate_limit_entries': len(self.rate_limits),
            'allowed_ips': len(self.allowed_ips)
        }


class SQLInjectionDetector:
    """SQL Injection Detection Utility - ALLOWS ALL SELECT QUERIES"""
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.SQLInjectionDetector")
        
        # Common SQL injection patterns (excluding SELECT patterns)
        self.injection_patterns = [
            r"(\b(insert|update|delete|drop|create|alter|exec|execute)\b)",
            r"(--|\#|\/\*|\*\/)",
            r"(\b(and|or)\b\s+\d+\s*=\s*\d+)",
            r"(\b(and|or)\b\s+['\"][^'\"]*['\"])",
            r"(\b(and|or)\b\s+\d+\s*=\s*['\"][^'\"]*['\"])",
            r"(\b(union)\b\s+\b(all|distinct)\b)",
            r"(\b(union)\b\s+\b(into)\b)",
            r"(\b(union)\b\s+\b(where|group|order|having|limit)\b)",
            r"(\b(union)\b\s+\b(and|or|not)\b)",
            r"(\b(union)\b\s+\b(like|in|between|exists)\b)",
            r"(\b(union)\b\s+\b(count|sum|avg|min|max)\b)",
            r"(\b(union)\b\s+\b(distinct|top|limit|offset)\b)",
            r"(\b(union)\b\s+\b(case|when|then|else|end)\b)",
            r"(\b(union)\b\s+\b(if|elseif|else|endif)\b)",
            r"(\b(union)\b\s+\b(while|for|loop|repeat|until)\b)",
            r"(\b(union)\b\s+\b(break|continue|return|exit)\b)",
            r"(\b(union)\b\s+\b(declare|set|begin|end)\b)",
            r"(\b(union)\b\s+\b(procedure|function|trigger|event)\b)",
            r"(\b(union)\b\s+\b(transaction|commit|rollback)\b)",
            r"(\b(union)\b\s+\b(lock|unlock|grant|revoke)\b)",
        ]
    
    def detect_sql_injection(self, query: str) -> Tuple[bool, List[str]]:
        """Detect potential SQL injection in query - ALLOWS ALL SELECT QUERIES"""
        if not query:
            return False, []
        
        # Allow all SELECT queries
        query_lower = query.lower().strip()
        if query_lower.startswith('select'):
            self.logger.info("SELECT query detected - allowing all SELECT operations")
            return False, []
        
        detected_patterns = []
        
        for pattern in self.injection_patterns:
            matches = re.findall(pattern, query_lower, re.IGNORECASE)
            if matches:
                detected_patterns.extend(matches)
        
        if detected_patterns:
            self.logger.warning(f"Potential SQL injection detected: {detected_patterns}")
            return True, detected_patterns
        
        return False, []
    
    def is_safe_query(self, query: str) -> bool:
        """Check if query is safe - ALLOWS ALL SELECT QUERIES"""
        # Allow all SELECT queries
        if query.lower().strip().startswith('select'):
            return True
        
        is_injection, _ = self.detect_sql_injection(query)
        return not is_injection


class DataMasking:
    """Data Masking Utility"""
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.DataMasking")
        
        # Sensitive data patterns
        self.sensitive_patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'credit_card': r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
            'ip_address': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
        }
    
    def mask_sensitive_data(self, data: str) -> str:
        """Mask sensitive data in string"""
        if not data:
            return data
        
        masked_data = data
        
        # Mask email addresses
        masked_data = re.sub(
            self.sensitive_patterns['email'],
            lambda m: m.group(0)[:3] + '***@' + m.group(0).split('@')[1],
            masked_data
        )
        
        # Mask phone numbers
        masked_data = re.sub(
            self.sensitive_patterns['phone'],
            '***-***-****',
            masked_data
        )
        
        # Mask SSN
        masked_data = re.sub(
            self.sensitive_patterns['ssn'],
            '***-**-****',
            masked_data
        )
        
        # Mask credit card numbers
        masked_data = re.sub(
            self.sensitive_patterns['credit_card'],
            '****-****-****-****',
            masked_data
        )
        
        # Mask IP addresses
        masked_data = re.sub(
            self.sensitive_patterns['ip_address'],
            '***.***.***.***',
            masked_data
        )
        
        return masked_data
    
    def mask_database_result(self, result: Any) -> Any:
        """Mask sensitive data in database result.
        Supports dict, list, and primitive values.
        """
        if result is None:
            return result

        # If the whole result is a list, mask each element
        if isinstance(result, list):
            return [
                self.mask_database_result(item) if isinstance(item, (dict, list))
                else self.mask_sensitive_data(item) if isinstance(item, str)
                else item
                for item in result
            ]

        # If the whole result is a dict, mask per key
        if isinstance(result, dict):
            masked_result: Dict[str, Any] = {}
            for key, value in result.items():
                if isinstance(value, str):
                    masked_result[key] = self.mask_sensitive_data(value)
                elif isinstance(value, (dict, list)):
                    masked_result[key] = self.mask_database_result(value)
                else:
                    masked_result[key] = value
            return masked_result

        # Primitive: return masked if string else as-is
        if isinstance(result, str):
            return self.mask_sensitive_data(result)
        return result