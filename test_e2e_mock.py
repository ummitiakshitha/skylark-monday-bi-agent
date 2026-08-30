import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import json
import datetime

# Import modules to test
import data_cleaner
import agent_core

class TestE2EMockAgent(unittest.TestCase):
    def setUp(self):
        # Load local excel data
        self.df_deals, self.df_wo = data_cleaner.load_and_clean_local_data()
        
    @patch('openai.resources.chat.completions.Completions.create')
    def test_energy_pipeline_query(self, mock_create):
        """Test 'How is Energy pipeline looking this quarter?' query."""
        # 1. Setup mock responses
        # First turn: LLM decides to call get_pipeline_summary
        mock_response_1 = MagicMock()
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "get_pipeline_summary"
        mock_tool_call.function.arguments = json.dumps({
            "sector": "Renewables",  # Excel has Renewables (representing solar/wind energy)
            "time_expression": "this quarter"
        })
        mock_response_1.choices = [
            MagicMock(message=MagicMock(tool_calls=[mock_tool_call], content=None))
        ]
        
        # Second turn: LLM synthesizes final answer after tool execution
        mock_response_2 = MagicMock()
        mock_response_2.choices = [
            MagicMock(message=MagicMock(
                tool_calls=[],
                content="## Energy Pipeline — Q3 2026\n\n**$15.2M open pipeline across 8 deals**\n\n### Key metrics\n- Total pipeline: $15.2M\n- Weighted pipeline: $9.8M\n\n### What stands out\n- Strong representation in solar deals.\n\n### Risks / Caveats\n- 2 deals are missing a Close Date.\n\n### Management Attention\n- Follow up on deal 'Sasuke'."
            ))
        ]
        
        mock_create.side_effect = [mock_response_1, mock_response_2]
        
        # 2. Run the agent
        agent = agent_core.AgentCore(provider="openai", api_key="mock_key")
        conversation = [{"role": "user", "content": "How is Energy pipeline looking this quarter?"}]
        
        response = agent.run_agent_turn(conversation, self.df_deals, self.df_wo)
        
        # 3. Assertions
        self.assertIn("Energy Pipeline", response)
        self.assertIn("open pipeline", response)
        self.assertEqual(mock_create.call_count, 2)
        
        # Verify first call arguments
        first_call_args = mock_create.call_args_list[0][1]
        self.assertEqual(first_call_args["messages"][1]["content"], "How is Energy pipeline looking this quarter?")
        self.assertGreater(len(first_call_args["tools"]), 0)

    @patch('openai.resources.chat.completions.Completions.create')
    def test_delayed_work_orders_query(self, mock_create):
        """Test 'Which work orders are delayed?' query."""
        # 1. Setup mock responses
        mock_response_1 = MagicMock()
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_456"
        mock_tool_call.function.name = "get_delayed_work_orders"
        mock_tool_call.function.arguments = json.dumps({})
        mock_response_1.choices = [
            MagicMock(message=MagicMock(tool_calls=[mock_tool_call], content=None))
        ]
        
        mock_response_2 = MagicMock()
        mock_response_2.choices = [
            MagicMock(message=MagicMock(
                tool_calls=[],
                content="## Delayed Work Orders\n\n**5 work orders are currently flagged as delayed**\n\n### Key metrics\n- Total delayed receivable: $450K\n\n### What stands out\n- Two projects in Mining have been paused."
            ))
        ]
        
        mock_create.side_effect = [mock_response_1, mock_response_2]
        
        # 2. Run agent
        agent = agent_core.AgentCore(provider="openai", api_key="mock_key")
        conversation = [{"role": "user", "content": "Which work orders are delayed?"}]
        
        response = agent.run_agent_turn(conversation, self.df_deals, self.df_wo)
        
        # 3. Verify
        self.assertIn("Delayed Work Orders", response)
        self.assertEqual(mock_create.call_count, 2)

    @patch('openai.resources.chat.completions.Completions.create')
    def test_ambiguous_pipeline_query(self, mock_create):
        """Test query 'show me the pipeline' triggers clarification question."""
        # Setup mock response asking for clarification directly
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(
                tool_calls=[],
                content="Do you want the overall current pipeline, a specific sector, or a stage breakdown?"
            ))
        ]
        mock_create.return_value = mock_response
        
        agent = agent_core.AgentCore(provider="openai", api_key="mock_key")
        conversation = [{"role": "user", "content": "show me the pipeline"}]
        
        response = agent.run_agent_turn(conversation, self.df_deals, self.df_wo)
        
        self.assertEqual(response, "Do you want the overall current pipeline, a specific sector, or a stage breakdown?")
        # Should not have called any tool because it was ambiguous
        self.assertEqual(mock_create.call_count, 1)

if __name__ == "__main__":
    unittest.main()
