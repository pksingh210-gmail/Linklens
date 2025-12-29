"""
LinkedIn Contact Info Extraction Module
Extracts email and phone numbers from LinkedIn profile contact overlay
"""

import re
import requests
from bs4 import BeautifulSoup
import time


def get_contact_info_for_profile(vanity_id, cookies, timeout=30):
    """
    Scrape contact information (email, phone) for a LinkedIn profile.
    
    Args:
        vanity_id (str): LinkedIn profile vanity ID (e.g., 'johnsmith')
        cookies (dict): Dictionary of LinkedIn cookies (must include 'li_at')
        timeout (int): Request timeout in seconds
        
    Returns:
        dict: Contains 'emails' and 'phones' lists, plus 'phone_sources' for debugging
        
    Raises:
        Exception: If profile load fails or cookies are invalid
    """
    if not cookies.get("li_at"):
        raise Exception("Missing required LinkedIn authentication cookie (li_at)")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }

    session = requests.Session()
    session.headers.update(headers)
    
    # Set cookies properly
    for name, value in cookies.items():
        session.cookies.set(name, value, domain='.linkedin.com')

    # First, visit the main profile page (establishes session)
    profile_url = f"https://www.linkedin.com/in/{vanity_id}/"
    try:
        response = session.get(profile_url, timeout=timeout, allow_redirects=True)
        if response.status_code != 200:
            raise Exception(f"Profile page failed to load: HTTP {response.status_code}")
        
        # Small delay to mimic human behavior
        time.sleep(1)
        
    except requests.RequestException as e:
        raise Exception(f"Failed to access profile page: {e}")

    # Now try to load the contact info overlay
    overlay_url = f"https://www.linkedin.com/in/{vanity_id}/overlay/contact-info/"
    html_to_parse = ""
    
    try:
        # Add referer header for overlay request
        overlay_headers = headers.copy()
        overlay_headers["Referer"] = profile_url
        session.headers.update(overlay_headers)
        
        response = session.get(overlay_url, timeout=timeout, allow_redirects=True)
        
        if response.status_code == 200:
            html_to_parse = response.text
            # Save for debugging
            #with open(f"debug_overlay_{vanity_id}.html", "w", encoding="utf-8") as f:
            #    f.write(response.text)
        else:
            # Fallback to main profile page
            html_to_parse = session.get(profile_url, timeout=timeout).text
            #with open(f"debug_profile_{vanity_id}.html", "w", encoding="utf-8") as f:
            #    f.write(html_to_parse)
                
    except requests.RequestException as e:
        # Use main profile page HTML as final fallback
        try:
            html_to_parse = session.get(profile_url, timeout=timeout).text
        except:
            raise Exception(f"Failed to access any LinkedIn page: {e}")

    return parse_contact_from_html(html_to_parse)


def parse_contact_from_html(html):
    """
    Extract emails and phone numbers from LinkedIn HTML.
    Enhanced version with multiple extraction strategies.
    
    Args:
        html (str): HTML content from LinkedIn profile or contact overlay
        
    Returns:
        dict: {
            'emails': list of email addresses,
            'phones': list of phone numbers,
            'phone_sources': dict mapping phone -> extraction method
        }
    """
    contact_info = {}
    phones = []
    phone_sources = {}
    
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")

    # ==================== EMAIL EXTRACTION ====================
    email_regex = r'\b([a-zA-Z0-9][a-zA-Z0-9._+-]{0,63}@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
    candidates = set(re.findall(email_regex, text, re.IGNORECASE))
    
    # Filter out common false positives
    exclude_terms = [
        "linkedin.com", "example.com", "test.com", "domain.com",
        "@2x.", "@1x.", ".png", ".jpg", ".svg", ".gif", ".webp",
        "static.licdn", "noreply", "donotreply", "no-reply",
        "support@", "help@", "info@example", "feedback@"
    ]
    
    valid_emails = []
    for e in candidates:
        e_lower = e.lower()
        # Skip if contains excluded terms
        if any(x in e_lower for x in exclude_terms):
            continue
        # Must have valid TLD
        if not re.search(r'\.(com|org|net|edu|gov|co|io|ai|au|uk|de|fr|ca|in|pk|us|jp|br|mx|ru|cn|es|it|nl|se|ch|at|be|pl|cz)$', e_lower, re.IGNORECASE):
            continue
        # Must not be too short (avoid false positives)
        if len(e) < 6:
            continue
        valid_emails.append(e)
    
    if valid_emails:
        contact_info["emails"] = sorted(set(valid_emails))

    # ==================== PHONE EXTRACTION ====================
    def add_phone(num, section):
        """Add phone if not already captured"""
        if num not in phone_sources:
            phones.append(num)
            phone_sources[num] = section

    # 1️⃣ Look for phone in specific LinkedIn sections/divs
    # Try common class patterns for contact sections
    contact_sections = soup.find_all(['section', 'div', 'li'], class_=re.compile(r'(contact|phone|pv-contact)', re.I))
    for section in contact_sections:
        section_text = section.get_text(" ", strip=True)
        # Look for phone patterns
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (123) 456-7890
            r'\+?\d{1,3}[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',        # +1 123 456 7890
            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',                         # 123-456-7890
            r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',                         # (123)456-7890
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, section_text)
            for match in matches:
                clean = re.sub(r'\D', '', match)
                if 10 <= len(clean) <= 15:  # Valid phone length
                    add_phone(clean, "Contact Section")

    # 2️⃣ Section-based extraction (look for 'Phone' label)
    for label in soup.find_all(string=re.compile(r'^\s*Phone\s*$', re.IGNORECASE)):
        parent = label.parent
        if parent:
            # Look in parent and next siblings
            search_area = parent.get_text(" ", strip=True)
            next_sib = parent.find_next_sibling()
            if next_sib:
                search_area += " " + next_sib.get_text(" ", strip=True)
            
            candidates = re.findall(r'[\d\+\-\s\(\)]{7,20}', search_area)
            for c in candidates:
                clean = re.sub(r'\D', '', c.strip())
                if 10 <= len(clean) <= 15:
                    add_phone(clean, "Phone Label")

    # 3️⃣ Look for phone near "Phone" keyword in text (broader search)
    phone_blocks = re.findall(r'(?:Phone|Tel|Mobile|Cell)[:\s]*([\d\+\-\s\(\)]{7,20})', text, re.IGNORECASE)
    for block in phone_blocks:
        clean = re.sub(r'\D', '', block.strip())
        if 10 <= len(clean) <= 15:
            add_phone(clean, "Phone Keyword")

    # 4️⃣ JSON/script embedded numbers
    for script in soup.find_all("script"):
        script_text = script.string or ""
        
        # Look for various JSON patterns
        patterns = [
            r'"number"\s*:\s*"([^"]+)"',
            r'"phone"\s*:\s*"([^"]+)"',
            r'"phoneNumber"\s*:\s*"([^"]+)"',
            r'"mobilePhone"\s*:\s*"([^"]+)"',
            r'"telephone"\s*:\s*"([^"]+)"',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, script_text):
                phone_str = match.group(1)
                clean = re.sub(r'\D', '', phone_str)
                if 10 <= len(clean) <= 15:
                    add_phone(clean, "JSON Embedded")

    # 5️⃣ Look for href="tel:" links
    tel_links = soup.find_all('a', href=re.compile(r'^tel:', re.I))
    for link in tel_links:
        phone_str = link.get('href', '').replace('tel:', '')
        clean = re.sub(r'\D', '', phone_str)
        if 10 <= len(clean) <= 15:
            add_phone(clean, "Tel Link")

    # Store results
    if phones:
        contact_info["phones"] = phones
        contact_info["phone_sources"] = phone_sources

    return contact_info


def format_contact_info(contact_info):
    """
    Format contact info for display or logging.
    
    Args:
        contact_info (dict): Output from parse_contact_from_html()
        
    Returns:
        str: Formatted string representation
    """
    lines = []
    lines.append("=" * 60)
    lines.append("EXTRACTED CONTACT INFORMATION")
    lines.append("=" * 60)
    
    if not contact_info:
        lines.append("⚠️ No contact information found")
        return "\n".join(lines)
    
    if contact_info.get("emails"):
        lines.append("\n📧 EMAILS:")
        for email in contact_info["emails"]:
            lines.append(f"   • {email}")
    else:
        lines.append("\n📧 EMAILS: None found")
    
    if contact_info.get("phones"):
        lines.append("\n📞 PHONES:")
        for phone in contact_info["phones"]:
            source = contact_info.get("phone_sources", {}).get(phone, "Unknown")
            lines.append(f"   • {phone}   (from {source})")
    else:
        lines.append("\n📞 PHONES: None found")
    
    return "\n".join(lines)