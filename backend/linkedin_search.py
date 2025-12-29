# linkedin_search.py
import time
from typing import List, Optional

class LinkedInSearch:
    def __init__(self, page, status_callback=None):
        self.page = page
        self.status_callback = status_callback or (lambda msg: None)

    def collect_profile_links(
        self, job_title: str, country: str, max_results: int = 50, city: Optional[str] = ""
    ) -> List[str]:
        if not self.page:
            raise RuntimeError("LinkedIn page context required for search")

        search_keywords = f"{job_title} {city} {country}".strip()
        search_url = f"https://www.linkedin.com/search/results/people/?keywords={search_keywords.replace(' ', '%20')}&origin=GLOBAL_SEARCH_HEADER"
        self.status_callback(f"🔍 Searching LinkedIn: {search_keywords}")
        self.page.goto(search_url)
        time.sleep(5)  # initial page load

        profile_links = set()
        scroll_attempts = 0
        max_scroll_attempts = 15  # allow more scrolls for more results

        while len(profile_links) < max_results and scroll_attempts < max_scroll_attempts:
            # select only real search result anchors
            anchors = self.page.query_selector_all(
                "div.search-results-container a.app-aware-link[href*='/in/']"
            )
            for a in anchors:
                href = a.get_attribute("href")
                if href and "/search/" not in href:
                    profile_links.add(href.split("?")[0])
                    if len(profile_links) >= max_results:
                        break

            prev_count = len(profile_links)

            # scroll the container instead of window
            self.page.evaluate("""
                const container = document.querySelector('div.search-results-container');
                if (container) {
                    container.scrollTop = container.scrollHeight;
                }
            """)

            time.sleep(3)  # allow new profiles to load

            # check if new profiles appeared
            if len(profile_links) == prev_count:
                scroll_attempts += 1  # no new results, count scroll
            else:
                scroll_attempts = 0  # reset attempts if new results found

            # optional: click "Next" if exists and not enough profiles
            next_btn = self.page.query_selector("button[aria-label='Next']")
            if next_btn and len(profile_links) < max_results:
                next_btn.click()
                self.page.wait_for_timeout(4000)  # wait for next page to load

        self.status_callback(f"✅ Collected {len(profile_links)} profile links")
        return list(profile_links)[:max_results]
