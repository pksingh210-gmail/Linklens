# backend/linkedin_search.py
import time
from typing import List, Optional

class LinkedInSearch:
    def __init__(self, page, status_callback=None):
        self.page = page
        self.status_callback = status_callback or (lambda msg: None)
    
    def collect_profile_links(
        self, 
        job_title: str, 
        country: str, 
        max_results: int = 20, 
        city: Optional[str] = ""
    ) -> List[str]:
        """
        Collect LinkedIn profile links based on search criteria.
        
        Args:
            job_title: Job title to search for
            country: Country filter
            max_results: Maximum number of profiles to collect
            city: Optional city filter
            
        Returns:
            List of profile URLs
        """
        if not self.page:
            raise RuntimeError("LinkedIn page context required for search")
        
        # Build search query
        search_keywords = f"{job_title} {city} {country}".strip()
        search_url = (
            f"https://www.linkedin.com/search/results/people/"
            f"?keywords={search_keywords.replace(' ', '%20')}"
            f"&origin=GLOBAL_SEARCH_HEADER"
        )
        
        self.status_callback(f"🔍 Searching LinkedIn: {search_keywords}")
        
        # Navigate to search results
        self.page.goto(search_url)
        time.sleep(4)
        
        profile_links = set()
        scroll_attempts = 0
        max_scroll_attempts = 5
        
        # Scroll and collect links
        while len(profile_links) < max_results and scroll_attempts < max_scroll_attempts:
            # Find all profile links on current page
            anchors = self.page.query_selector_all("a[href*='/in/']")
            
            for a in anchors:
                href = a.get_attribute("href")
                if href and "/search/" not in href:
                    # Clean URL (remove query parameters)
                    clean_url = href.split("?")[0]
                    profile_links.add(clean_url)
                    
                    if len(profile_links) >= max_results:
                        break
            
            # Scroll down to load more results
            self.page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            time.sleep(2)
            scroll_attempts += 1
        
        result_list = list(profile_links)[:max_results]
        self.status_callback(f"✅ Collected {len(result_list)} profile links")
        
        return result_list


