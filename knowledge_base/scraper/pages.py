# knowledge_base/scraper/pages.py

# These pages always exist — scrape them directly
STATIC_PAGES = [
    {"url": "https://digix-ai.com/",
     "category": "home",
     "filename": "home.txt",
     "language": "en"}},

    {"url": "https://digix-ai.com/about-us",
     "category": "about",
     "filename": "about.txt",
     "language": "en"},

    {"url": "https://digix-ai.com/services",
     "category": "services", 
     "filename": "services.txt",
     "language": "en"},

    {"url": "https://digix-ai.com/training-programs",
     "category": "training",
     "filename": "training.txt",
     "language": "en"},

    {"url": "https://digix-ai.com/impact", 
     "category": "impact", 
     "filename": "impact.txt",
     "language": "en"},

    {"url": "https://digix-ai.com/contact",
     "category": "contact",
     "filename": "contact.txt",
     "language": "en"},

    # Arabic pages
    {"url": "https://digix-ai.com/ar",
     "category": "home",
     "filename": "home_ar.txt",
     "language": "ar"},

    {"url": "https://digix-ai.com/ar/about-us",
     "category": "about",
     "filename": "about_ar.txt",
     "language": "ar"},

    {"url": "https://digix-ai.com/ar/services",
     "category": "services",
     "filename": "services_ar.txt",
     "language": "ar"},

    {"url": "https://digix-ai.com/ar/training-programs",
     "category": "training",
     "filename": "training_ar.txt",
     "language": "ar"},

    {"url": "https://digix-ai.com/ar/impact",
     "category": "impact",
     "filename": "impact_ar.txt",
     "language": "ar"},

    {"url": "https://digix-ai.com/ar/contact",
     "category": "contact",
     "filename": "contact_ar.txt",
     "language": "ar"},
]

# These are sections that will have dynamic child pages in the future
# The scraper will look for links within these base URLs and follow them
DYNAMIC_SECTIONS = [
    {
        "base_url": "https://digix-ai.com/training-programs",
        "child_path": "/training/",   # Only follow links that start with this
        "category": "training_course",
        "language": "en"
    },

    {
        "base_url": "https://digix-ai.com/ar/training-programs",
        "child_path": "/ar/training/",
        "category": "training_course",
        "language": "ar"
    },

    {
        "base_url": "https://digix-ai.com/services",
        "child_path": "/services/",
        "category": "service_detail",
        "language": "en"
    },

    {
        "base_url": "https://digix-ai.com/ar/services",
        "child_path": "ar/services/",
        "category": "service_detail",
        "language": "ar"
    },
]
