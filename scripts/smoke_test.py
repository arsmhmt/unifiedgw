#!/usr/bin/env python
"""
Smoke test script for PayCrypt Unified Gateway.
Day 3: Production readiness checks.

Usage:
    python scripts/smoke_test.py

Environment variables:
    UNIFIEDGW_BASE_URL - Base URL of the API (default: http://localhost:5000)
    UNIFIEDGW_API_KEY - API key for testing (required)
"""
import os
import sys
import requests
import time
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.END}\n")


def print_test(name, passed, details=None):
    """Print test result."""
    status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
    print(f"{status} {name}")
    if details:
        print(f"    {details}")


def check_health(base_url):
    """Check API health endpoint."""
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        return response.status_code == 200, response.status_code
    except Exception as e:
        return False, str(e)


def check_request_id_header(base_url):
    """Check that X-Request-ID header is present."""
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
        has_header = 'X-Request-ID' in response.headers
        request_id = response.headers.get('X-Request-ID', 'missing')
        return has_header, request_id
    except Exception as e:
        return False, str(e)


def check_error_format(base_url, api_key):
    """Check standardized error format."""
    try:
        # Make invalid request to trigger error
        response = requests.post(
            f"{base_url}/api/v1/payments",
            json={'invalid': 'data'},
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=5
        )
        
        if response.status_code != 400:
            return False, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        
        # Check error structure
        if 'error' not in data:
            return False, "Missing 'error' key"
        
        error = data['error']
        required_keys = ['code', 'message']
        missing = [k for k in required_keys if k not in error]
        
        if missing:
            return False, f"Missing keys: {missing}"
        
        # Check for request_id (Day 1)
        has_request_id = 'request_id' in error
        
        return True, f"request_id present: {has_request_id}"
    except Exception as e:
        return False, str(e)


def check_api_authentication(base_url, api_key):
    """Check API authentication."""
    try:
        # Valid key
        response = requests.get(
            f"{base_url}/api/v1/payments",
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=5
        )
        
        if response.status_code not in [200, 404]:
            return False, f"Valid key returned {response.status_code}"
        
        # Invalid key
        response = requests.get(
            f"{base_url}/api/v1/payments",
            headers={'Authorization': 'Bearer invalid_key_12345'},
            timeout=5
        )
        
        if response.status_code != 401:
            return False, f"Invalid key returned {response.status_code}, expected 401"
        
        return True, "Auth working correctly"
    except Exception as e:
        return False, str(e)


def check_payment_creation(base_url, api_key):
    """Check payment creation endpoint."""
    try:
        payload = {
            'amount': 10.00,
            'currency': 'USD',
            'method': 'crypto',
            'type': 'deposit',
            'crypto_currency': 'USDT',
            'description': f'Smoke test {datetime.now().isoformat()}'
        }
        
        response = requests.post(
            f"{base_url}/api/v1/payments",
            json=payload,
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=5
        )
        
        if response.status_code != 201:
            return False, f"Expected 201, got {response.status_code}: {response.text[:100]}"
        
        data = response.json()
        required_keys = ['id', 'transaction_id', 'status']
        missing = [k for k in required_keys if k not in data]
        
        if missing:
            return False, f"Missing keys: {missing}"
        
        return True, f"Created payment #{data['id']}"
    except Exception as e:
        return False, str(e)


def check_webhook_dispatcher(base_url):
    """Check if webhook dispatcher script exists."""
    script_path = os.path.join(os.path.dirname(__file__), 'dispatch_webhooks.py')
    exists = os.path.exists(script_path)
    return exists, script_path if exists else "Script not found"


def run_smoke_tests():
    """Run all smoke tests."""
    print_header("PayCrypt Unified Gateway - Smoke Tests")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Get configuration
    base_url = os.getenv('UNIFIEDGW_BASE_URL', 'http://localhost:5000')
    api_key = os.getenv('UNIFIEDGW_API_KEY')
    
    print(f"Base URL: {base_url}")
    print(f"API Key: {'*' * 20 if api_key else 'NOT SET'}")
    
    if not api_key:
        print(f"\n{Colors.RED}ERROR: UNIFIEDGW_API_KEY environment variable not set{Colors.END}")
        print("Set it with: export UNIFIEDGW_API_KEY=your_api_key")
        sys.exit(1)
    
    results = []
    
    # Day 1: Wire Diagnostics
    print_header("Day 1: Wire Diagnostics")
    
    passed, details = check_health(base_url)
    print_test("Health endpoint responds", passed, details)
    results.append(passed)
    
    passed, details = check_request_id_header(base_url)
    print_test("X-Request-ID header present", passed, details)
    results.append(passed)
    
    passed, details = check_error_format(base_url, api_key)
    print_test("Standardized error format", passed, details)
    results.append(passed)
    
    # API Tests
    print_header("API Functionality")
    
    passed, details = check_api_authentication(base_url, api_key)
    print_test("API authentication", passed, details)
    results.append(passed)
    
    passed, details = check_payment_creation(base_url, api_key)
    print_test("Payment creation", passed, details)
    results.append(passed)
    
    # Infrastructure
    print_header("Infrastructure")
    
    passed, details = check_webhook_dispatcher(base_url)
    print_test("Webhook dispatcher script exists", passed, details)
    results.append(passed)
    
    # Summary
    print_header("Summary")
    total = len(results)
    passed_count = sum(results)
    failed_count = total - passed_count
    
    print(f"Total tests: {total}")
    print(f"{Colors.GREEN}Passed: {passed_count}{Colors.END}")
    if failed_count > 0:
        print(f"{Colors.RED}Failed: {failed_count}{Colors.END}")
    
    success_rate = (passed_count / total * 100) if total > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    if failed_count > 0:
        print(f"\n{Colors.RED}Some tests failed. Please review the output above.{Colors.END}")
        sys.exit(1)
    else:
        print(f"\n{Colors.GREEN}All tests passed! System is ready.{Colors.END}")
        sys.exit(0)


if __name__ == '__main__':
    try:
        run_smoke_tests()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.END}")
        sys.exit(1)
