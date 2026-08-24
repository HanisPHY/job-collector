"""
Seed company list for the ATS registry.

PRE_RESOLVED entries were verified by direct endpoint tests on 2026-08-19.
PROBE_NAMES are known tech employers whose platform/slug is auto-detected on
the first `python ats_direct.py --probe` run (results cached in the registry).
"""

PRE_RESOLVED = [
    # verified 2026-08-19 via curl (HTTP 200 + valid JSON)
    {"name": "Stripe", "platform": "greenhouse", "slug": "stripe", "source": "seed"},
    {"name": "Databricks", "platform": "greenhouse", "slug": "databricks", "source": "seed"},
    {"name": "Anthropic", "platform": "greenhouse", "slug": "anthropic", "source": "seed"},
    {"name": "Figma", "platform": "greenhouse", "slug": "figma", "source": "seed"},
    {"name": "Discord", "platform": "greenhouse", "slug": "discord", "source": "seed"},
    {"name": "Palantir", "platform": "lever", "slug": "palantir", "source": "seed"},
    {"name": "Plaid", "platform": "lever", "slug": "plaid", "source": "seed"},
    {"name": "OpenAI", "platform": "ashby", "slug": "openai", "source": "seed"},
    {"name": "NVIDIA", "platform": "workday", "slug": "nvidia",
     "host": "nvidia.wd5.myworkdayjobs.com", "tenant": "nvidia",
     "site": "NVIDIAExternalCareerSite", "source": "seed"},
]

PROBE_NAMES = [
    # big tech / public
    "Airbnb", "Coinbase", "Robinhood", "DoorDash", "Instacart", "Pinterest",
    "Reddit", "Dropbox", "Lyft", "Roblox", "Datadog", "Cloudflare", "Twilio",
    "MongoDB", "Elastic", "GitLab", "HashiCorp", "Asana", "Duolingo",
    "Affirm", "Chime", "SoFi", "Snowflake", "Okta", "Squarespace",
    # unicorns / late-stage
    "Scale AI", "Ramp", "Brex", "Gusto", "Checkr", "Flexport", "Benchling",
    "Samsara", "Vercel", "Notion", "Linear", "Perplexity", "Replit",
    "Anduril", "Zipline", "Nuro", "Zoox", "Voleon", "Sierra", "Mistral AI",
    "Together AI", "Modal", "Grammarly", "Canva", "Airtable", "Retool",
    "Postman", "Miro", "Attentive", "Whatnot", "Deel", "Rippling",
    "Wiz", "Snyk", "Chainalysis", "Kraken", "Gemini", "Cruise",
]
