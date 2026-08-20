"""
LLM API cost tracking.
"""

from typing import Dict, Any


class LLMCostTracker:
    """Tracks LLM API usage and calculates costs."""
    
    # Pricing per 1K tokens (as of 2024, update as needed)
    # Prices in USD
    MODEL_PRICING = {
        "gpt-3.5-turbo": {
            "input": 0.0005,   # $0.50 per 1M tokens
            "output": 0.0015   # $1.50 per 1M tokens
        },
        "gpt-4": {
            "input": 0.03,      # $30 per 1M tokens
            "output": 0.06      # $60 per 1M tokens
        },
        "gpt-4-turbo": {
            "input": 0.01,      # $10 per 1M tokens
            "output": 0.03      # $30 per 1M tokens
        },
        "gpt-4o": {
            "input": 0.0025,    # $2.50 per 1M tokens
            "output": 0.01      # $10 per 1M tokens
        }
    }
    
    def __init__(self):
        """Initialize cost tracker."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_calls = 0
        self.model_used = None
    
    def record_usage(self, model: str, input_tokens: int, output_tokens: int):
        """
        Record API usage.
        
        Args:
            model: Model name used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        if self.model_used is None:
            self.model_used = model
        elif self.model_used != model:
            # If different models used, use the first one for cost calculation
            pass
        
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.api_calls += 1
    
    def calculate_cost(self):
        """
        Calculate total cost based on token usage.

        Returns:
            Total cost in USD, or None if the model has no entry in
            MODEL_PRICING. Returning None rather than silently billing an
            unknown model at gpt-3.5-turbo rates keeps the daily report from
            presenting a fabricated number as fact - swap the model and the
            report says "unpriced" until MODEL_PRICING is updated.
        """
        if not self.model_used or self.model_used not in self.MODEL_PRICING:
            return None

        pricing = self.MODEL_PRICING[self.model_used]
        input_cost = (self.total_input_tokens / 1000) * pricing["input"]
        output_cost = (self.total_output_tokens / 1000) * pricing["output"]

        return input_cost + output_cost

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of API usage and costs.

        Returns:
            Dictionary with usage statistics
        """
        cost = self.calculate_cost()
        return {
            "model": self.model_used or "N/A",
            "api_calls": self.api_calls,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "cost_usd": cost,
            "priced": cost is not None,
        }
    
    def reset(self):
        """Reset tracking counters."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_calls = 0
        self.model_used = None
