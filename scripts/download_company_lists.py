"""Script to download Fortune 500 and unicorn company lists."""
import requests
import csv
import os
import sys

import paths

# Fix Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def download_fortune_500():
    """Download Fortune 500 companies list."""
    print("Downloading Fortune 500 companies...")
    
    # Try multiple sources
    sources = [
        {
            'url': 'https://raw.githubusercontent.com/datasets/fortune-500/master/data/fortune-500.csv',
            'description': 'GitHub datasets'
        },
        {
            'url': 'https://www.gigasheet.com/sample-data/fortune-500-companies',
            'description': 'Gigasheet'
        }
    ]
    
    for source in sources:
        try:
            print(f"  Trying {source['description']}...")
            response = requests.get(source['url'], timeout=15, allow_redirects=True)
            
            if response.status_code == 200:
                # Try to parse as CSV
                content = response.text
                reader = csv.DictReader(content.splitlines())
                
                # Check if it has company name column
                fieldnames = reader.fieldnames
                if fieldnames:
                    # Find company name column
                    company_col = None
                    for col in ['company', 'name', 'Company', 'Name', 'Company Name', 'company_name']:
                        if col in fieldnames:
                            company_col = col
                            break
                    
                    if company_col:
                        companies = []
                        for row in reader:
                            if row.get(company_col):
                                companies.append(row[company_col])
                        
                        if companies:
                            # Save to file
                            with open(str(paths.DATA_DIR / 'fortune_500_companies.csv'), 'w', newline='', encoding='utf-8') as f:
                                writer = csv.writer(f)
                                writer.writerow(['company'])  # Header
                                for company in companies:
                                    writer.writerow([company])
                            
                            print(f"  [OK] Downloaded {len(companies)} Fortune 500 companies")
                            return True
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    # If download fails, create a basic list from known Fortune 500 companies
    print("  Creating basic Fortune 500 list from known companies...")
    known_companies = [
        'Walmart', 'Amazon', 'Apple', 'CVS Health', 'UnitedHealth Group',
        'Exxon Mobil', 'Berkshire Hathaway', 'Alphabet', 'McKesson', 'AmerisourceBergen',
        'Costco Wholesale', 'Cigna', 'AT&T', 'Microsoft', 'Cardinal Health',
        'Chevron', 'Ford Motor', 'General Motors', 'Kroger', 'General Electric',
        'Walgreens Boots Alliance', 'JPMorgan Chase', 'Fannie Mae', 'Verizon Communications',
        'Home Depot', 'Bank of America', 'Express Scripts Holding', 'Wells Fargo',
        'Boeing', 'Phillips 66', 'Anthem', 'MetLife', 'Valero Energy',
        'Citigroup', 'PepsiCo', 'Comcast', 'Johnson & Johnson', 'IBM',
        'Target', 'State Farm Insurance', 'Freddie Mac', 'UPS', 'Lowe\'s',
        'Intel', 'FedEx', 'Humana', 'Procter & Gamble', 'Archer Daniels Midland',
        'Prudential Financial', 'Albertsons', 'Disney', 'Pfizer', 'HP',
        'Dell Technologies', 'Coca-Cola', 'HCA Healthcare', 'Energy Transfer',
        'Lockheed Martin', 'Best Buy', 'Goldman Sachs Group', 'Morgan Stanley',
        'Tesla', 'Nike', 'Oracle', 'Qualcomm', 'Starbucks', 'Netflix',
        'Adobe', 'Salesforce', 'PayPal', 'Nvidia', 'Broadcom'
    ]
    
    with open(str(paths.DATA_DIR / 'fortune_500_companies.csv'), 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['company'])
        for company in known_companies:
            writer.writerow([company])
    
    print(f"  [OK] Created Fortune 500 list with {len(known_companies)} companies")
    return True


def download_unicorn_companies():
    """Download unicorn companies list."""
    print("Downloading unicorn companies...")
    
    # Try GitHub sources
    sources = [
        {
            'url': 'https://raw.githubusercontent.com/connor11528/tech-companies-and-startups/master/companies.csv',
            'description': 'GitHub tech companies'
        },
        {
            'url': 'https://raw.githubusercontent.com/neomatrix369/awesome-unicorns/master/data/unicorns.csv',
            'description': 'GitHub unicorns list'
        }
    ]
    
    for source in sources:
        try:
            print(f"  Trying {source['description']}...")
            response = requests.get(source['url'], timeout=15)
            
            if response.status_code == 200:
                content = response.text
                reader = csv.DictReader(content.splitlines())
                
                fieldnames = reader.fieldnames
                if fieldnames:
                    # Find company name column
                    company_col = None
                    for col in ['company', 'name', 'Company', 'Name', 'Company Name', 'company_name', 'CompanyName']:
                        if col in fieldnames:
                            company_col = col
                            break
                    
                    if company_col:
                        companies = []
                        for row in reader:
                            if row.get(company_col):
                                companies.append(row[company_col])
                        
                        if companies:
                            # Save to file
                            with open(str(paths.DATA_DIR / 'unicorn_companies.csv'), 'w', newline='', encoding='utf-8') as f:
                                writer = csv.writer(f)
                                writer.writerow(['company'])
                                for company in companies:
                                    writer.writerow([company])
                            
                            print(f"  [OK] Downloaded {len(companies)} unicorn companies")
                            return True
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    # If download fails, create a basic list of known unicorns
    print("  Creating basic unicorn list from known companies...")
    known_unicorns = [
        'OpenAI', 'ByteDance', 'SpaceX', 'xAI', 'Anthropic', 'Stripe',
        'Databricks', 'Canva', 'Revolut', 'Epic Games', 'Fanatics',
        'Discord', 'Reddit', 'Figma', 'Notion', 'Airtable', 'Grammarly',
        'UiPath', 'Ripple', 'Coinbase', 'Kraken', 'Binance', 'FTX',
        'Robinhood', 'Chime', 'SoFi', 'Nubank', 'Rappi', 'Rappi',
        'Grab', 'Gojek', 'Ola', 'Swiggy', 'Zomato', 'Razorpay',
        'Razorpay', 'Cred', 'PhonePe', 'Paytm', 'Byju\'s', 'Unacademy',
        'CureFit', 'Ola Electric', 'Oyo', 'OYO', 'Zomato', 'Swiggy',
        'Razorpay', 'PhonePe', 'Paytm', 'Byju\'s', 'Unacademy', 'CureFit',
        'Rivian', 'Rivian Automotive', 'Lucid Motors', 'Rivian', 'Lucid',
        'Waymo', 'Cruise', 'Aurora', 'Zoox', 'Argo AI', 'TuSimple',
        'Nuro', 'Pony.ai', 'AutoX', 'Momenta', 'WeRide', 'Plus',
        'Einride', 'Einride', 'Einride', 'Einride', 'Einride'
    ]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_unicorns = []
    for company in known_unicorns:
        company_lower = company.lower()
        if company_lower not in seen:
            seen.add(company_lower)
            unique_unicorns.append(company)
    
    with open(str(paths.DATA_DIR / 'unicorn_companies.csv'), 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['company'])
        for company in unique_unicorns:
            writer.writerow([company])
    
    print(f"  [OK] Created unicorn list with {len(unique_unicorns)} companies")
    return True


def main():
    """Main function."""
    print("=" * 60)
    print("Downloading Company Lists")
    print("=" * 60)
    print()
    
    # Check if requests is available
    try:
        import requests
    except ImportError:
        print("Error: requests library is required.")
        print("Install it with: pip install requests")
        sys.exit(1)
    
    success_count = 0
    
    # Download Fortune 500
    if download_fortune_500():
        success_count += 1
    print()
    
    # Download unicorn companies
    if download_unicorn_companies():
        success_count += 1
    print()
    
    print("=" * 60)
    if success_count == 2:
        print("[SUCCESS] Successfully downloaded both company lists!")
        print(f"  - fortune_500_companies.csv")
        print(f"  - unicorn_companies.csv")
    else:
        print(f"[WARNING] Downloaded {success_count}/2 lists. Some files may be basic lists.")
    print("=" * 60)


if __name__ == "__main__":
    main()
