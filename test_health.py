#!/usr/bin/env python3
"""
Quick smoke test for the Flask service /health endpoint.
"""
import urllib.request
import json

try:
    with urllib.request.urlopen("http://127.0.0.1:8000/health") as response:
        data = json.loads(response.read().decode())
        status = response.status
        
        print(f"HTTP Status: {status}")
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if status == 200 and data.get("ok") is True:
            print("\n✓ PASS: Health check successful")
            exit(0)
        else:
            print("\n✗ FAIL: Unexpected response")
            exit(1)
            
except Exception as e:
    print(f"✗ FAIL: {e}")
    exit(1)
