#!/usr/bin/env python3
"""
Hokusai Paintings Link Scraper
Strategy: Use Selenium to interact with lazy-loaded content on Google Arts & Culture
"""

import time
import json
import logging
from typing import List, Set
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
from urllib.parse import urljoin, urlparse


class HokusaiLinkScraper:
    def __init__(self, headless=True, delay=2):
        """
        Initialize the scraper with Chrome WebDriver

        Args:
            headless (bool): Run browser in headless mode
            delay (int): Delay between actions in seconds
        """
        self.base_url = "https://artsandculture.google.com"
        self.target_url = "https://artsandculture.google.com/entity/hokusai/m0bwf4?categoryid=artist"
        self.delay = delay
        self.scraped_links = set()

        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        # Setup Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

    def start_scraping(self):
        """Main method to orchestrate the scraping process"""
        try:
            self.logger.info("Starting Hokusai painting links scraping...")

            # Step 1: Load the page
            self.load_page()

            # Step 2: Find the collection container
            container = self.find_collection_container()

            # Step 3: Scrape initial visible links
            self.scrape_visible_links(container)

            # Step 4: Scroll and load more content
            self.scroll_and_load_content(container)

            # Step 5: Final scrape of all links
            self.scrape_all_links(container)

            # Step 6: Save results
            self.save_results()

            self.logger.info(f"Scraping completed! Found {len(self.scraped_links)} unique painting links")

        except Exception as e:
            self.logger.error(f"Error during scraping: {str(e)}")
        finally:
            self.cleanup()

    def load_page(self):
        """Load the target page and wait for initial content"""
        self.logger.info("Loading Hokusai page...")
        self.driver.get(self.target_url)

        # Wait for page to load
        time.sleep(self.delay * 2)

        # Accept cookies if present
        try:
            cookie_button = self.driver.find_element(By.XPATH,
                                                     "//button[contains(text(), 'Accept') or contains(text(), 'OK')]")
            cookie_button.click()
            time.sleep(1)
        except NoSuchElementException:
            pass

        self.logger.info("Page loaded successfully")

    def find_collection_container(self):
        """Find the collection container using the provided XPath"""
        # Updated XPath provided by user
        xpath_selector = "/html/body/div[3]/div/div[3]/div[2]/div/div[2]/span[1]/div/div/div[3]"

        self.logger.info("Waiting for page to fully load...")
        time.sleep(5)  # Give more time for dynamic content

        # Debug: Print current page structure
        self.debug_page_structure()

        try:
            # Try the exact xpath first
            self.logger.info(f"Trying exact XPath: {xpath_selector}")
            container = self.wait.until(
                EC.presence_of_element_located((By.XPATH, xpath_selector))
            )
            self.logger.info("✓ Found collection container using provided XPath")
            return container
        except TimeoutException:
            self.logger.warning("Exact XPath failed, trying alternatives...")

            # More specific fallback selectors for Google Arts & Culture
            fallback_selectors = [
                # Try parent containers that might contain the scrollable area
                "/html/body/div[3]/div/div[3]/div[2]/div/div[2]/span[1]/div/div",
                "/html/body/div[3]/div/div[3]/div[2]/div/div[2]/span[1]/div",
                "/html/body/div[3]/div/div[3]/div[2]/div/div[2]",
                "/html/body/div[3]/div/div[3]/div[2]/div",

                # CSS-based selectors
                "div[role='main'] div[style*='overflow']",
                "div[style*='scroll']",
                "[data-ved] div[style*='overflow']",

                # Common patterns in Google Arts pages
                "//div[contains(@style, 'overflow-x')]",
                "//div[contains(@style, 'scroll')]",
                "//span[@role='presentation']//div",
                "//div[@data-ved]//div[contains(@style, 'width')]",

                # Look for any scrollable container
                "//div[@role='main']//div[contains(@style, 'overflow')]",
                "//div[contains(@class, 'entity')]//div[contains(@style, 'scroll')]"
            ]

            for i, selector in enumerate(fallback_selectors):
                try:
                    self.logger.info(f"Trying fallback {i + 1}: {selector}")
                    if selector.startswith("//") or selector.startswith("/html"):
                        container = self.driver.find_element(By.XPATH, selector)
                    else:
                        container = self.driver.find_element(By.CSS_SELECTOR, selector)

                    self.logger.info(f"✓ Found collection container using fallback: {selector}")

                    # Verify it contains potential artwork links
                    links_in_container = container.find_elements(By.XPATH, ".//a")
                    self.logger.info(f"Container has {len(links_in_container)} links")

                    return container
                except NoSuchElementException:
                    continue
                except Exception as e:
                    self.logger.debug(f"Fallback {i + 1} error: {str(e)}")
                    continue

            # Last resort: try to find any container with links
            self.logger.warning("All selectors failed, trying last resort...")
            return self.find_any_link_container()

    def debug_page_structure(self):
        """Debug method to understand page structure"""
        try:
            # Get page title
            title = self.driver.title
            self.logger.info(f"Page title: {title}")

            # Count total divs
            all_divs = self.driver.find_elements(By.TAG_NAME, "div")
            self.logger.info(f"Total divs on page: {len(all_divs)}")

            # Count total links
            all_links = self.driver.find_elements(By.TAG_NAME, "a")
            self.logger.info(f"Total links on page: {len(all_links)}")

            # Look for any links containing 'asset'
            asset_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'asset')]")
            self.logger.info(f"Links containing 'asset': {len(asset_links)}")

            if asset_links:
                self.logger.info("Sample asset links found:")
                for i, link in enumerate(asset_links[:3]):
                    href = link.get_attribute('href')
                    self.logger.info(f"  {i + 1}. {href}")

            # Check if we need to scroll or interact first
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if "loading" in body_text.lower() or len(asset_links) == 0:
                self.logger.warning("Page might still be loading or need interaction")

        except Exception as e:
            self.logger.error(f"Debug failed: {str(e)}")

    def find_any_link_container(self):
        """Last resort: find any container that has artwork links"""
        try:
            # Look for any element that contains asset links
            elements_with_asset_links = self.driver.find_elements(
                By.XPATH, "//div[.//a[contains(@href, 'asset')]]"
            )

            if elements_with_asset_links:
                # Find the one with the most links
                best_container = None
                max_links = 0

                for element in elements_with_asset_links:
                    links = element.find_elements(By.XPATH, ".//a[contains(@href, 'asset')]")
                    if len(links) > max_links:
                        max_links = len(links)
                        best_container = element

                if best_container:
                    self.logger.info(f"✓ Found container with {max_links} asset links")
                    return best_container

            # If still nothing, just return body
            self.logger.warning("Using document body as fallback container")
            return self.driver.find_element(By.TAG_NAME, "body")

        except Exception as e:
            self.logger.error(f"Last resort failed: {str(e)}")
            raise Exception("Could not find any suitable container")

    def scrape_visible_links(self, container):
        """Scrape currently visible painting links"""
        self.logger.info("Scraping visible links...")

        # Debug container info
        try:
            container_tag = container.tag_name
            container_classes = container.get_attribute('class') or 'No classes'
            self.logger.info(f"Container: <{container_tag}> classes: {container_classes}")
        except:
            pass

        # Find all clickable elements that might be painting links
        link_selectors = [
            # Direct links with asset in href
            ".//a[contains(@href, '/asset/')]",
            ".//a[contains(@href, '/artwork/')]",

            # Google Arts specific patterns
            ".//a[contains(@href, 'artsandculture.google.com')]",
            ".//a[@data-ved]",
            ".//a[contains(@data-href, 'asset')]",

            # Div elements that might be clickable
            ".//div[@role='button']//a",
            ".//div[@data-ved]//a",
            ".//div[contains(@style, 'cursor')]//a",

            # Image containers with links
            ".//img/..//a",
            ".//img/ancestor::a",

            # Any link in the container
            ".//a[@href]"
        ]

        found_any_links = False

        for selector in link_selectors:
            try:
                links = container.find_elements(By.XPATH, selector)
                self.logger.info(f"Selector '{selector}' found {len(links)} elements")

                for link in links:
                    try:
                        href = link.get_attribute('href')
                        data_href = link.get_attribute('data-href')
                        onclick = link.get_attribute('onclick')

                        # Check all possible href sources
                        potential_urls = [href, data_href]

                        # Extract from onclick if present
                        if onclick:
                            import re
                            onclick_urls = re.findall(r'["\']([^"\']*(?:asset|artwork)[^"\']*)["\']', onclick)
                            potential_urls.extend(onclick_urls)

                        for url in potential_urls:
                            if url and self.is_valid_painting_link(url):
                                self.scraped_links.add(url)
                                found_any_links = True
                                if len(self.scraped_links) <= 5:  # Log first few found
                                    self.logger.info(f"Found link: {url}")

                    except Exception as e:
                        self.logger.debug(f"Error processing link: {str(e)}")
                        continue

            except Exception as e:
                self.logger.debug(f"Selector {selector} failed: {str(e)}")

        if not found_any_links:
            self.logger.warning("No valid painting links found in container!")
            # Debug: show what links are actually in the container
            try:
                all_links = container.find_elements(By.XPATH, ".//a[@href]")
                self.logger.info(f"All links in container: {len(all_links)}")
                for i, link in enumerate(all_links[:10]):  # Show first 10
                    href = link.get_attribute('href')
                    text = link.text.strip()[:50]
                    self.logger.info(f"  {i + 1}. {href} | Text: '{text}'")
            except Exception as e:
                self.logger.error(f"Debug links failed: {str(e)}")

        self.logger.info(f"Total unique links found so far: {len(self.scraped_links)}")

    def is_valid_painting_link(self, url):
        """Check if URL is a valid painting link"""
        if not url:
            return False

        # Make relative URLs absolute
        if url.startswith('/'):
            url = urljoin(self.base_url, url)

        # Must be from Google Arts & Culture
        if 'artsandculture.google.com' not in url:
            return False

        # Must be an asset or artwork page
        if not any(keyword in url for keyword in ['/asset/', '/artwork/']):
            return False

        # Should not be the main entity page
        if '/entity/hokusai' in url and 'categoryid=artist' in url:
            return False

        # Should not be search or other utility pages
        invalid_patterns = ['/search', '/explore', '/story', '/exhibit', '/theme']
        if any(pattern in url for pattern in invalid_patterns):
            return False

        return True

    def save_results(self):
        """Save scraped links to files"""
        # Save as JSON
        links_list = sorted(list(self.scraped_links))

        results = {
            'total_links': len(links_list),
            'scrape_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'source_url': self.target_url,
            'links': links_list
        }

        with open('hokusai_painting_links.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        # Save as plain text for easy reading
        with open('hokusai_painting_links.txt', 'w', encoding='utf-8') as f:
            f.write(f"Hokusai Painting Links - Total: {len(links_list)}\n")
            f.write(f"Scraped on: {results['scrape_timestamp']}\n")
            f.write("=" * 50 + "\n\n")
            for i, link in enumerate(links_list, 1):
                f.write(f"{i:3d}. {link}\n")

        self.logger.info("Results saved to hokusai_painting_links.json and hokusai_painting_links.txt")

    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'driver'):
            self.driver.quit()
        self.logger.info("Cleanup completed")

    def get_results(self):
        """Return the scraped links"""
        return list(self.scraped_links)


def main():
    """Main execution function"""
    # Create scraper instance
    scraper = HokusaiLinkScraper(headless=False, delay=2)  # Set headless=True for production

    try:
        # Start scraping
        scraper.start_scraping()

        # Get results
        links = scraper.get_results()

        print(f"\n{'=' * 60}")
        print(f"SCRAPING COMPLETED SUCCESSFULLY!")
        print(f"{'=' * 60}")
        print(f"Total links found: {len(links)}")
        print(f"Target was: 955 items")
        print(f"Coverage: {len(links) / 955 * 100:.1f}%" if len(
            links) <= 955 else f"Found {len(links) - 955} extra links!")
        print(f"\nFirst 5 links:")
        for i, link in enumerate(links[:5], 1):
            print(f"{i}. {link}")

        if len(links) > 5:
            print("...")
            print(f"Files saved: hokusai_painting_links.json, hokusai_painting_links.txt")

    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()