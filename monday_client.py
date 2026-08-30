import requests
import pandas as pd
import logging
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)

MONDAY_API_URL = "https://api.monday.com/v2"

class MondayAPIError(Exception):
    """Custom exception for Monday.com API failures."""
    pass

class MondayClient:
    """Client to interface with monday.com GraphQL API."""
    def __init__(self, api_token: str):
        if not api_token:
            raise ValueError("Monday.com API token must be provided.")
        self.api_token = api_token
        self.headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
            "API-Version": "2023-10"
        }

    def _execute_query(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against monday.com."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
            
        try:
            response = requests.post(MONDAY_API_URL, json=payload, headers=self.headers, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request to Monday.com failed: {e}")
            raise MondayAPIError(f"Failed to connect to Monday.com: {e}")

        result = response.json()
        
        # Check for GraphQL errors in the response
        if "errors" in result:
            errors = result["errors"]
            err_msg = "; ".join([err.get("message", "Unknown error") for err in errors])
            logger.error(f"Monday.com GraphQL errors: {err_msg}")
            raise MondayAPIError(f"Monday.com API returned errors: {err_msg}")

        return result

    def get_board_columns(self, board_id: str) -> Dict[str, str]:
        """
        Fetches the column definitions for a board.
        Returns a dictionary mapping column_id -> column_title.
        """
        query = """
        query ($boardId: [ID!]) {
          boards (ids: $boardId) {
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
        result = self._execute_query(query, variables)
        
        boards = result.get("data", {}).get("boards", [])
        if not boards:
            raise MondayAPIError(f"Board with ID {board_id} not found or inaccessible.")
            
        columns = boards[0].get("columns", [])
        column_map = {col["id"]: col["title"] for col in columns}
        # Explicitly map name to 'name'
        column_map["name"] = "Name"
        return column_map

    def fetch_board_items(self, board_id: str) -> Tuple[str, pd.DataFrame]:
        """
        Fetches all items from the board, parsing column values.
        Returns a tuple of (board_name, dataframe).
        """
        # 1. Get column mapping
        column_map = self.get_board_columns(board_id)
        
        # 2. Query items page-by-page
        items = []
        cursor = None
        board_name = "Unknown Board"
        
        query_first_page = """
        query ($boardId: [ID!]) {
          boards (ids: $boardId) {
            name
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
                result = self._execute_query(query_first_page, variables)
                boards = result.get("data", {}).get("boards", [])
                if not boards:
                    raise MondayAPIError(f"Board with ID {board_id} is empty or not found.")
                board_name = boards[0].get("name", "Unknown Board")
                items_page = boards[0].get("items_page", {})
            else:
                variables = {"cursor": cursor}
                result = self._execute_query(query_next_page, variables)
                # Next page query boards structure can be different, it might return a list of boards
                boards = result.get("data", {}).get("boards", [])
                if boards:
                    items_page = boards[0].get("items_page", {})
                else:
                    # In some API versions, items_page is returned at data.boards[0] or directly
                    items_page = result.get("data", {}).get("items_page", {})
                    
            page_items = items_page.get("items", [])
            items.extend(page_items)
            
            cursor = items_page.get("cursor")
            if not cursor:
                break

        if not items:
            return board_name, pd.DataFrame()

        # 3. Parse items to a structured list of dicts
        parsed_records = []
        for item in items:
            record = {
                "item_id": item["id"],
                "Item Name": item["name"] # This is usually mapped to 'Deal Name' or primary column
            }
            
            # Map column values
            for val in item.get("column_values", []):
                col_id = val["id"]
                col_title = column_map.get(col_id, col_id)
                col_text = val.get("text")
                record[col_title] = col_text
                
            parsed_records.append(record)
            
        df = pd.DataFrame(parsed_records)
        return board_name, df
