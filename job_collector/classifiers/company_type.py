"""
Company type classifier using database and LLM.
"""

import os
import json
from typing import List, Dict, Optional, Tuple

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from ..database.company_db import CompanyDatabase
from ..tracking.cost_tracker import LLMCostTracker


class CompanyTypeClassifier:
    """Classifies companies into categories using extensible approach."""
    
    def __init__(self, use_llm: bool = True, openai_key: Optional[str] = None, cost_tracker: Optional[LLMCostTracker] = None, company_database: Optional[CompanyDatabase] = None):
        """
        Initialize company type classifier.
        
        Args:
            use_llm: Whether to use LLM for classification when needed
            openai_key: OpenAI API key for LLM classification
            cost_tracker: Optional cost tracker for API usage
            company_database: Optional company database instance (creates new one if not provided)
        """
        self.use_llm = use_llm and OPENAI_AVAILABLE
        self.openai_key = openai_key or os.getenv('OPENAI_API_KEY')
        self.cost_tracker = cost_tracker
        self.company_database = company_database or CompanyDatabase()
        if self.use_llm and self.openai_key:
            openai.api_key = self.openai_key
    
    def classify(self, company_name: str, job_description: str = "", use_llm_immediately: bool = True) -> str:
        """
        Classify company type.
        
        Args:
            company_name: Name of the company
            job_description: Optional job description for context
            use_llm_immediately: If True, use LLM immediately when not in database.
                                If False, return "Others" and skip LLM (for batch processing)
            
        Returns:
            '独角兽/上市公司/Big Tech' or 'Others'
        """
        if not company_name:
            return "Others"
        
        # Step 1: Check if it's in the company database (Big Tech, public companies, unicorns)
        # This uses case-insensitive matching
        if self.company_database.is_big_tech_or_public(company_name):
            return "独角兽/上市公司/Big Tech"
        
        # Step 2: Company not found in database - use LLM as fallback
        # Only use LLM if it's enabled, API key is available, and use_llm_immediately is True
        if use_llm_immediately and self.use_llm and self.openai_key:
            print("Use LLM as fallback")
            try:
                result = self._classify_with_llm(company_name, job_description)
                if result:
                    print(f"LLM classification for {company_name}: {result}")
                    return result
            except Exception as e:
                print(f"LLM classification failed for {company_name}: {e}")
        
        # Step 3: Default to Others if cannot determine
        # (Either LLM not enabled, API key missing, LLM classification failed, or batch mode)
        return "Others"
    
    def batch_classify_with_llm(self, companies_with_context: List[Tuple[str, str]]) -> Dict[str, str]:
        """
        Batch classify multiple companies using LLM in a single API call.
        
        Args:
            companies_with_context: List of tuples (company_name, job_description)
            
        Returns:
            Dictionary mapping company_name to classification result
        """
        if not self.use_llm or not self.openai_key or not OPENAI_AVAILABLE:
            # Return "Others" for all if LLM not available
            return {company_name: "Others" for company_name, _ in companies_with_context}
        
        if not companies_with_context:
            return {}
        
        # Build batch prompt
        companies_list = []
        for i, (company_name, job_description) in enumerate(companies_with_context, 1):
            desc_preview = job_description[:200] if job_description else "N/A"
            companies_list.append(f"{i}. Company: {company_name}\n   Context: {desc_preview}")
        
        companies_text = "\n\n".join(companies_list)
        
        prompt = f"""Classify each of the following companies into one of these categories:

1. "独角兽/上市公司/Big Tech" - if the company is ANY of the following:
   - A unicorn startup (private valuation ≥ $1B)
   - A publicly listed company
   - A well-known Big Tech company
   - A large, established, and prestigious company or institution,
     even if privately held
     (e.g., quantitative trading firms, hedge funds, major consulting firms,
      global financial institutions, or core tech infrastructure companies)

2. "Others" - small startups, early-stage companies, unknown firms, or local businesses

When in doubt, prefer classifying well-known large companies as "独角兽/上市公司/Big Tech".

Companies to classify:
{companies_text}

Respond with a JSON object mapping each company name to its classification.
Format: {{"Company Name 1": "独角兽/上市公司/Big Tech", "Company Name 2": "Others", ...}}
Only include the JSON object, no other text.
"""
        
        model_name = "gpt-3.5-turbo"
        results = {}
        
        try:
            # Try new API format (openai >= 1.0.0)
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_key)
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a company classification assistant. Respond with only a valid JSON object mapping company names to classifications."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,  # Increased for batch responses
                    temperature=0,
                    response_format={"type": "json_object"} if hasattr(client.chat.completions.create, '__annotations__') else None
                )
                result_text = response.choices[0].message.content.strip()
                
                # Track token usage if cost tracker is available
                if self.cost_tracker:
                    usage = response.usage
                    input_tokens = usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0
                    output_tokens = usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0
                    self.cost_tracker.record_usage(model_name, input_tokens, output_tokens)
                
                # Parse JSON response
                try:
                    results = json.loads(result_text)
                    # Validate and normalize results
                    for company_name, _ in companies_with_context:
                        if company_name in results:
                            classification = results[company_name]
                            if classification not in ["独角兽/上市公司/Big Tech", "Others"]:
                                results[company_name] = "Others"
                        else:
                            # Company not in response, default to Others
                            results[company_name] = "Others"
                except json.JSONDecodeError:
                    print(f"Warning: Failed to parse LLM batch response as JSON. Defaulting to 'Others' for all companies.")
                    results = {company_name: "Others" for company_name, _ in companies_with_context}
                    
            except (ImportError, AttributeError):
                # Fallback to old API format (openai < 1.0.0)
                response = openai.ChatCompletion.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a company classification assistant. Respond with only a valid JSON object mapping company names to classifications."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0
                )
                result_text = response.choices[0].message.content.strip()
                
                # Track token usage if cost tracker is available
                if self.cost_tracker:
                    usage = response.usage
                    input_tokens = usage.get('prompt_tokens', 0) if isinstance(usage, dict) else (usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0)
                    output_tokens = usage.get('completion_tokens', 0) if isinstance(usage, dict) else (usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0)
                    self.cost_tracker.record_usage(model_name, input_tokens, output_tokens)
                
                # Parse JSON response
                try:
                    results = json.loads(result_text)
                    # Validate and normalize results
                    for company_name, _ in companies_with_context:
                        if company_name in results:
                            classification = results[company_name]
                            if classification not in ["独角兽/上市公司/Big Tech", "Others"]:
                                results[company_name] = "Others"
                        else:
                            results[company_name] = "Others"
                except json.JSONDecodeError:
                    print(f"Warning: Failed to parse LLM batch response as JSON. Defaulting to 'Others' for all companies.")
                    results = {company_name: "Others" for company_name, _ in companies_with_context}
        
        except Exception as e:
            print(f"Batch LLM classification error: {e}")
            # Default to "Others" for all companies on error
            results = {company_name: "Others" for company_name, _ in companies_with_context}
        
        return results
    
    def _classify_with_llm(self, company_name: str, job_description: str) -> Optional[str]:
        """
        Use LLM to classify company type.
        
        Args:
            company_name: Name of the company
            job_description: Job description for context
            
        Returns:
            Classification result or None
        """
        if not OPENAI_AVAILABLE:
            return None
        
        prompt = f"""Classify the following company into one of these categories:

1. "独角兽/上市公司/Big Tech" - if the company is ANY of the following:
   - A unicorn startup (private valuation ≥ $1B)
   - A publicly listed company
   - A well-known Big Tech company
   - A large, established, and prestigious company or institution,
     even if privately held
     (e.g., quantitative trading firms, hedge funds, major consulting firms,
      global financial institutions, or core tech infrastructure companies)

2. "Others" - small startups, early-stage companies, unknown firms, or local businesses

When in doubt, prefer classifying well-known large companies as
"独角兽/上市公司/Big Tech".

Company name: {company_name}
Job description context: {job_description[:500] if job_description else "N/A"}

Respond with ONLY one of: "独角兽/上市公司/Big Tech" or "Others"

"""
        
        model_name = "gpt-3.5-turbo"
        try:
            # Try new API format (openai >= 1.0.0)
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_key)
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a company classification assistant. Respond with only the category name."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=20,
                    temperature=0
                )
                result = response.choices[0].message.content.strip()
                
                # Track token usage if cost tracker is available
                if self.cost_tracker:
                    usage = response.usage
                    input_tokens = usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0
                    output_tokens = usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0
                    self.cost_tracker.record_usage(model_name, input_tokens, output_tokens)
            except (ImportError, AttributeError):
                # Fallback to old API format (openai < 1.0.0)
                response = openai.ChatCompletion.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a company classification assistant. Respond with only the category name."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=20,
                    temperature=0
                )
                result = response.choices[0].message.content.strip()
                
                # Track token usage if cost tracker is available
                if self.cost_tracker:
                    usage = response.usage
                    input_tokens = usage.get('prompt_tokens', 0) if isinstance(usage, dict) else (usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0)
                    output_tokens = usage.get('completion_tokens', 0) if isinstance(usage, dict) else (usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0)
                    self.cost_tracker.record_usage(model_name, input_tokens, output_tokens)
            
            if result in ["独角兽/上市公司/Big Tech", "Others"]:
                return result
        except Exception as e:
            print(f"OpenAI API error: {e}")
        
        return None
