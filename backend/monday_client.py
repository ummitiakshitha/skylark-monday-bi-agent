import requests
import logging
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger(__name__)

MONDAY_API_URL = "https://api.monday.com/v2"

class MondayAPIError(Exception):
    """Custom exception class for Monday.com GraphQL or connection errors."""
    pass

class MondayClient:
    """Handles read-only connection and data retrieval from Monday.com GraphQL API."""
    def __init__(self, api_token: str):
        if not api_token:
            raise ValueError("Monday.com API token must be configured.")
        self.api_token = api_token
        self.headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
            "API-Version": "2023-10"
        }

    def monday_graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes a GraphQL query against the Monday.com API."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
            
        try:
            response = requests.post(MONDAY_API_URL, json=payload, headers=self.headers, timeout=20)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP connection failure to Monday.com: {e}")
            raise MondayAPIError(f"HTTP request to Monday.com failed: {e}")

        result = response.json()
        
        # Check for GraphQL specific errors
        if "errors" in result:
            errors = result["errors"]
            err_msg = "; ".join([err.get("message", "Unknown GraphQL error") for err in errors])
            logger.error(f"Monday.com GraphQL errors: {err_msg}")
            raise MondayAPIError(f"Monday.com API returned errors: {err_msg}")
            
        return result

    def get_board_metadata(self, board_id: str) -> Dict[str, Any]:
        """Retrieves name and columns definitions for a board."""
        query = """
        query ($boardId: [ID!]) {
          boards (ids: $boardId) {
            id
            name
            columns {
              id
              title
              type
            }
          }
        }
        """
        variables = {"boardId": [str(board_id)]}
        result = self.monday_graphql(query, variables)
        boards = result.get("data", {}).get("boards", [])
        if not boards:
            raise MondayAPIError(f"Board ID {board_id} not found or is inaccessible.")
        return boards[0]

    def get_board_columns(self, board_id: str) -> List[Dict[str, str]]:
        """Returns a list of column definitions for a board, mapping ID, Title, and Type."""
        metadata = self.get_board_metadata(board_id)
        return metadata.get("columns", [])

    def get_all_board_items(self, board_id: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Retrieves all items from a board using cursor-based pagination.
        Returns a tuple of (board_name, list_of_raw_item_records).
        """
        # 1. Get Board Metadata
        metadata = self.get_board_metadata(board_id)
        board_name = metadata.get("name", "Unknown Board")
        
        # 2. Iterate through pages using the GraphQL items_page pagination
        items = []
        cursor = None
        
        query_first_page = """
        query ($boardId: [ID!]) {
          boards (ids: $boardId) {
            items_page (limit: 100) {
              cursor
              items {
                id
                name
                column_values {
                  id
                  text
                  value
                }
              }
            }
          }
        }
        """
        
        query_next_page = """
        query ($cursor: String!) {
          boards {
            items_page (limit: 100, cursor: $cursor) {
              cursor
              items {
                id
                name
                column_values {
                  id
                  text
                  value
                }
              }
            }
          }
        }
        """
        
        while True:
            if not cursor:
                variables = {"boardId": [str(board_id)]}
                result = self.monday_graphql(query_first_page, variables)
                boards = result.get("data", {}).get("boards", [])
                if not boards:
                    raise MondayAPIError(f"Board {board_name} (ID: {board_id}) is empty or missing.")
                items_page = boards[0].get("items_page", {})
            else:
                variables = {"cursor": cursor}
                result = self.monday_graphql(query_next_page, variables)
                boards = result.get("data", {}).get("boards", [])
                if boards:
                    items_page = boards[0].get("items_page", {})
                else:
                    # Alternative structure depending on API query routing
                    items_page = result.get("data", {}).get("items_page", {})
                    
            page_items = items_page.get("items", [])
            items.extend(page_items)
            
            cursor = items_page.get("cursor")
            if not cursor:
                break
                
        return board_name, items
