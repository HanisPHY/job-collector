"""
Company database for tracking big tech, public companies, and unicorns.
"""

import os
import csv
import json
from datetime import datetime
from typing import Set

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class CompanyDatabase:
    """Dynamic company database that loads from multiple sources."""
    
    CACHE_FILE = "company_database_cache.json"
    CACHE_EXPIRY_DAYS = 30  # Refresh cache every 30 days
    
    # Well-known Big Tech companies (fallback if database fails to load)
    FALLBACK_COMPANIES = {
        'google', 'alphabet', 'microsoft', 'apple', 'amazon', 'meta', 'facebook',
        'netflix', 'nvidia', 'oracle', 'salesforce', 'adobe', 'intel', 'ibm',
        'cisco', 'qualcomm', 'paypal', 'uber', 'lyft', 'airbnb', 'tesla',
        'twitter', 'x.com', 'snapchat', 'spotify', 'zoom', 'slack', 'dropbox'
    }
    
    def __init__(self, cache_file: str = None):
        """
        Initialize company database.
        
        Args:
            cache_file: Path to cache file (default: company_database_cache.json)
        """
        self.cache_file = cache_file or self.CACHE_FILE
        self.companies: Set[str] = set()
        self._load_database()
    
    def _load_database(self):
        """Load company database from cache or build it."""
        # Try to load from cache first
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    cache_date = datetime.fromisoformat(cache_data.get('last_updated', '2000-01-01'))
                    days_old = (datetime.now() - cache_date).days
                    
                    if days_old < self.CACHE_EXPIRY_DAYS:
                        self.companies = set(cache_data.get('companies', []))
                        print(f"Loaded {len(self.companies)} companies from cache ({days_old} days old)")
                        return
                    else:
                        print(f"Cache expired ({days_old} days old), rebuilding...")
            except Exception as e:
                print(f"Error loading cache: {e}, rebuilding...")
        
        # Build database from sources
        self._build_database()
    
    def _build_database(self):
        """Build company database from multiple sources."""
        print("Building company database from multiple sources...")
        companies = set()
        
        # 1. Add fallback companies
        companies.update(self.FALLBACK_COMPANIES)
        
        # 2. Load from GitHub tech companies CSV (if available)
        companies.update(self._load_github_tech_companies())
        
        # 3. Load Fortune 500 companies (if CSV available)
        companies.update(self._load_fortune_500())
        
        # 4. Load unicorn companies (if CSV available)
        companies.update(self._load_unicorn_companies())
        
        # 5. Fetch public companies from SEC EDGAR (optional, can be slow)
        # Uncomment if you want to fetch from SEC API
        # companies.update(self._fetch_sec_companies())
        
        self.companies = companies
        
        # Save to cache
        self._save_cache()
        print(f"Database built with {len(self.companies)} companies")
    
    def _load_github_tech_companies(self) -> Set[str]:
        """Load tech companies from GitHub CSV."""
        companies = set()
        url = "https://raw.githubusercontent.com/connor11528/tech-companies-and-startups/master/companies.csv"
        
        if not REQUESTS_AVAILABLE:
            print("  requests library not available, skipping GitHub tech companies")
            return companies
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                content = response.text
                reader = csv.DictReader(content.splitlines())
                for row in reader:
                    # Try common column names
                    company_name = row.get('company', '') or row.get('name', '') or row.get('Company', '') or row.get('Name', '')
                    if company_name:
                        companies.add(company_name.lower().strip())
                print(f"  Loaded {len(companies)} companies from GitHub tech companies list")
        except Exception as e:
            print(f"  Error loading GitHub tech companies: {e}")
        
        return companies
    
    def _load_fortune_500(self) -> Set[str]:
        """Load Fortune 500 companies from local CSV or download."""
        companies = set()
        fortune_file = "fortune_500_companies.csv"
        
        # Try to load from local file first
        if os.path.exists(fortune_file):
            try:
                with open(fortune_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Try common column names
                        company_name = (row.get('company', '') or row.get('name', '') or 
                                       row.get('Company', '') or row.get('Name', '') or
                                       row.get('Company Name', ''))
                        if company_name:
                            companies.add(company_name.lower().strip())
                print(f"  Loaded {len(companies)} companies from local Fortune 500 file")
            except Exception as e:
                print(f"  Error loading local Fortune 500 file: {e}")
        
        return companies
    
    def _load_unicorn_companies(self) -> Set[str]:
        """Load unicorn companies from local CSV."""
        companies = set()
        unicorn_file = "unicorn_companies.csv"
        
        # Try to load from local file
        if os.path.exists(unicorn_file):
            try:
                with open(unicorn_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Try common column names
                        company_name = (row.get('company', '') or row.get('name', '') or 
                                       row.get('Company', '') or row.get('Name', '') or
                                       row.get('Company Name', ''))
                        if company_name:
                            companies.add(company_name.lower().strip())
                print(f"  Loaded {len(companies)} companies from local unicorn file")
            except Exception as e:
                print(f"  Error loading local unicorn file: {e}")
        
        return companies
    
    def _fetch_sec_companies(self) -> Set[str]:
        """Fetch public companies from SEC EDGAR API (slow, optional)."""
        companies = set()
        
        if not REQUESTS_AVAILABLE:
            print("  requests library not available, skipping SEC companies")
            return companies
        
        try:
            # SEC requires User-Agent header
            headers = {
                'User-Agent': 'Job Classifier (contact@example.com)',
                'Accept': 'application/json'
            }
            
            # Get list of all companies (this is a large file)
            url = "https://www.sec.gov/files/company_tickers.json"
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                for ticker_info in data.values():
                    company_name = ticker_info.get('title', '')
                    if company_name:
                        companies.add(company_name.lower().strip())
                print(f"  Loaded {len(companies)} companies from SEC EDGAR")
        except Exception as e:
            print(f"  Error fetching SEC companies: {e}")
        
        return companies
    
    def _save_cache(self):
        """Save company database to cache file."""
        try:
            cache_data = {
                'last_updated': datetime.now().isoformat(),
                'companies': list(self.companies)
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving cache: {e}")
    
    def is_big_tech_or_public(self, company_name: str) -> bool:
        """
        Check if company name matches any company in the database.
        Uses case-insensitive matching with improved logic.
        
        Args:
            company_name: Company name to check
            
        Returns:
            True if company matches, False otherwise
        """
        if not company_name:
            return False
        
        # Normalize input: lowercase and strip
        company_lower = company_name.lower().strip()
        if not company_lower:
            return False
        
        # Normalize: remove common suffixes/prefixes for better matching
        # Remove common corporate suffixes
        normalized_input = company_lower
        for suffix in [' inc', ' inc.', ' llc', ' llc.', ' corp', ' corp.', 
                       ' corporation', ' ltd', ' ltd.', ' limited', ' company', ' co', ' co.']:
            if normalized_input.endswith(suffix):
                normalized_input = normalized_input[:-len(suffix)].strip()
        
        # Check exact match first (fastest)
        if company_lower in self.companies or normalized_input in self.companies:
            return True
        
        # Check if any database company is a substring of the input
        # This handles cases like "Microsoft Corporation" matching "microsoft"
        for db_company in self.companies:
            # Normalize database company name too
            normalized_db = db_company
            for suffix in [' inc', ' inc.', ' llc', ' llc.', ' corp', ' corp.', 
                           ' corporation', ' ltd', ' ltd.', ' limited', ' company', ' co', ' co.']:
                if normalized_db.endswith(suffix):
                    normalized_db = normalized_db[:-len(suffix)].strip()
            
            # Check if database company (or normalized) is in input
            if (db_company in company_lower or 
                normalized_db in company_lower or
                normalized_db in normalized_input):
                return True
            
            # Check if input (or normalized) is in database company (for exact matches)
            # Only if input is substantial (at least 3 chars) to avoid false positives
            if len(company_lower) >= 3:
                if (company_lower in db_company or 
                    normalized_input in db_company or
                    normalized_input in normalized_db):
                    return True
        
        return False
    
    def refresh(self):
        """Force refresh of the database."""
        print("Refreshing company database...")
        self._build_database()
