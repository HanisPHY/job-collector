"""
Visa sponsorship classifier.
"""


class SponsorshipClassifier:
    """Classifies jobs based on visa sponsorship keywords."""
    
    # Keywords that indicate visa sponsorship
    SPONSORSHIP_KEYWORDS = [
        'visa',
        'sponsor',
        'sponsorship',
        'h-1b',
        'h1b',
        'h1-b',
        'opt',
        'cpt',
        'stem opt',
        'work authorization',
        'work visa',
        'immigration',
        'green card',
        'permanent residency'
    ]
    
    @classmethod
    def classify(cls, job_description: str) -> str:
        """
        Classify sponsorship status based on keywords.
        
        Args:
            job_description: Job description text
            
        Returns:
            'Sponsor' if keywords found, 'Not (Maybe Not) Sponsor' otherwise
        """
        if not job_description:
            return "Not (Maybe Not) Sponsor"
        
        description_lower = job_description.lower()
        
        for keyword in cls.SPONSORSHIP_KEYWORDS:
            if keyword in description_lower:
                return "Sponsor"
        
        return "Not (Maybe Not) Sponsor"
