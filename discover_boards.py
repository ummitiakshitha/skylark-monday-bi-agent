import os
import requests
import sys
from dotenv import load_dotenv

# Load env variables from a local .env file if it exists
load_dotenv()

def discover_boards():
    token = os.getenv("MONDAY_API_TOKEN")
    if not token:
        print("Error: MONDAY_API_TOKEN environment variable not set.")
        print("Please set it in your environment or in a .env file.")
        sys.exit(1)
        
    url = "https://api.monday.com/v2"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "API-Version": "2023-10"
    }
    
    query = """
    query {
      boards (limit: 50) {
        id
        name
        type
        state
      }
    }
    """
    
    payload = {"query": query}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            print("GraphQL Errors returned from Monday.com:")
            for err in data["errors"]:
                print(f"- {err.get('message')}")
            sys.exit(1)
            
        boards = data.get("data", {}).get("boards", [])
        if not boards:
            print("No boards found on this account.")
            return
            
        print("Successfully connected to Monday.com!")
        print(f"Found {len(boards)} boards:")
        print("-" * 60)
        print(f"{'Board ID':<15} | {'Board Name':<35} | {'Type':<10}")
        print("-" * 60)
        for board in boards:
            print(f"{board['id']:<15} | {board['name'][:35]:<35} | {board['type']:<10}")
        print("-" * 60)
        
    except requests.exceptions.RequestException as e:
        print(f"HTTP Connection Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    discover_boards()
