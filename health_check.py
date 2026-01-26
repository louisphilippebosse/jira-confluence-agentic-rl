#!/usr/bin/env python3
"""
Health check script for the application.
Can be used for monitoring and deployment verification.
"""

import sys
import requests
from typing import Tuple


def check_health(base_url: str = "http://localhost:8000") -> Tuple[bool, str]:
    """
    Check if the application is healthy.
    
    Returns:
        Tuple of (is_healthy, message)
    """
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return True, f"Application is healthy. Status: {data.get('status')}"
        else:
            return False, f"Health check failed with status code: {response.status_code}"
    
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to the application"
    except requests.exceptions.Timeout:
        return False, "Health check timed out"
    except Exception as e:
        return False, f"Health check failed: {str(e)}"


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    is_healthy, message = check_health(url)
    
    print(message)
    sys.exit(0 if is_healthy else 1)
