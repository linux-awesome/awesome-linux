import re
import requests
from pathlib import Path
from urllib.parse import unquote
import concurrent.futures
from typing import List, Tuple
import logging
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_links(content: str) -> List[str]:
    """
    Extract all http/https links from mixed content (Markdown and HTML)
    
    Args:
        content: The text content containing both Markdown and HTML
        
    Returns:
        List of unique URLs found in the content
    """
    links = set()
    
    # 1. Extract links from HTML tags using BeautifulSoup
    soup = BeautifulSoup(content, 'html.parser')
    
    # Find all tags with href or src attributes
    for tag in soup.find_all(href=True):
        url = tag['href']
        if url.startswith(('http://', 'https://')):
            links.add(url)
            
    for tag in soup.find_all(src=True):
        url = tag['src']
        if url.startswith(('http://', 'https://')):
            links.add(url)
    
    # 2. Extract Markdown style links
    # Remove HTML tags first to avoid duplicate matches
    markdown_content = soup.get_text()
    markdown_pattern = r'\[([^\]]+)\]\((https?://[^\s\)]+)\)'
    markdown_links = re.findall(markdown_pattern, markdown_content)
    links.update(url for _, url in markdown_links)
    
    # 3. Extract direct URLs
    url_pattern = r'(?<!\()(https?://[^\s\)]+)(?!\))'
    direct_links = re.findall(url_pattern, markdown_content)
    links.update(direct_links)
    
    # Clean and normalize URLs
    cleaned_links = set()
    for link in links:
        # Remove trailing punctuation that might have been included
        link = re.sub(r'[.,;:]+$', '', link)
        # Decode URL-encoded characters
        link = unquote(link)
        cleaned_links.add(link)
    
    return list(cleaned_links)

def check_link(url: str) -> Tuple[str, bool, str]:
    """
    Check if a single link is valid
    
    Args:
        url: The URL to check
        
    Returns:
        Tuple of (url, is_valid, error_message)
    """
    try:
        # Set headers to simulate browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Try HEAD request first to minimize data transfer
        response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        
        # If HEAD request fails, fall back to GET request
        if response.status_code >= 400:
            response = requests.get(url, headers=headers, timeout=10)
            
        if response.status_code < 400:
            return url, True, "OK"
        else:
            return url, False, f"HTTP {response.status_code}"
            
    except requests.exceptions.RequestException as e:
        return url, False, str(e)

def check_readme_links(readme_path: str, max_workers: int = 5) -> List[Tuple[str, bool, str]]:
    """
    Check all links in a README file
    
    Args:
        readme_path: Path to the README.md file
        max_workers: Maximum number of concurrent workers for link checking
        
    Returns:
        List of (url, is_valid, error_message) tuples
    """
    try:
        # Read README file
        content = Path(readme_path).read_text(encoding='utf-8')
        
        # Extract links
        links = extract_links(content)
        logger.info(f"Found {len(links)} unique links in {readme_path}")
        
        # Check links concurrently
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(check_link, url): url for url in links}
            for future in concurrent.futures.as_completed(future_to_url):
                results.append(future.result())
                
        return results
                
    except Exception as e:
        logger.error(f"Error processing {readme_path}: {str(e)}")
        raise

def main():
    """
    Main function to run the link checker
    
    Returns:
        0 if all links are valid, 1 if invalid links found or errors occurred
    """
    readme_path = "README.md"  # Could be passed as command line argument
    
    try:
        results = check_readme_links(readme_path)
        
        # Print results
        print("\nLink Check Results:")
        print("-" * 80)
        
        invalid_links = []
        valid_count = 0
        
        # Sort results by validity and URL for better readability
        sorted_results = sorted(results, key=lambda x: (x[1], x[0]))
        
        for url, is_valid, error_msg in sorted_results:
            if is_valid:
                valid_count += 1
                print(f"✓ Valid:   {url}")
            else:
                invalid_links.append((url, error_msg))
                print(f"❌ Invalid: {url}")
                print(f"   Error:   {error_msg}")
                
        print("-" * 80)
        print(f"Total links checked: {len(results)}")
        print(f"Valid links: {valid_count}")
        print(f"Invalid links: {len(invalid_links)}")
        
    except Exception as e:
        logger.error(f"Script execution failed: {str(e)}")
        return 1
        
    return 0 if not invalid_links else 1

if __name__ == "__main__":
    exit(main())