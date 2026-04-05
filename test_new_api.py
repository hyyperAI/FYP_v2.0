"""
test_new_api.py

Script to test the new FastAPI endpoints.
"""

import httpx
import time
import json

BASE_URL = "http://localhost:8000"

def test_api():
    print("Testing Upwork Scraping API...")
    
    with httpx.Client() as client:
        # 1. Start Scrape
        print("\n1. Starting scrape task...")
        response = client.post(f"{BASE_URL}/api/upwork/start_scrape", json={
            "query": "n8n",
            "page": 1,
            "jobs_per_page": 10,
            "headless": True,
            "fast": True
        })
        print(f"Status Code: {response.status_code}")
        result = response.json()
        task_id = result.get('task_id')
        print(f"Task ID: {task_id}")
        
        # 2. Poll for Status
        print("\n2. Polling for completion...")
        while True:
            status_response = client.get(f"{BASE_URL}/api/upwork/scraping_status/{task_id}")
            status = status_response.json()
            print(f"Current Status: {status['status']}")
            
            if status['status'] == 'completed':
                print(f"Success! Found {status.get('job_count')} jobs.")
                break
            elif status['status'] == 'failed':
                print(f"Failed: {status.get('error_message')}")
                return
            
            time.sleep(2)
            
        # 3. Get Results
        print("\n3. Getting results...")
        results_response = client.get(f"{BASE_URL}/api/upwork/get_scraping_results/{task_id}")
        results = results_response.json()
        print(f"Total jobs in DB for task: {results['total_jobs']}")
        if results['jobs']:
            print(f"First job title: {results['jobs'][0]['title']}")
            
        # 4. Get Recent Jobs
        print("\n4. Getting recent jobs...")
        recent_response = client.get(f"{BASE_URL}/api/upwork/most_recent_jobs?query=n8n")
        recent = recent_response.json()
        print(f"Found {recent['count']} recent jobs matching 'n8n'")

if __name__ == "__main__":
    test_api()
