"""
Compatibility wrapper for the refactored job_collector package.
This file maintains backward compatibility with existing scripts.
"""

# Import the main function from the new structure
from main import main

if __name__ == "__main__":
    main()
