#!/usr/bin/env python3
"""
Hokusai Paintings Link Scraper
Strategy: Use Selenium to interact with lazy-loaded content on Google Arts & Culture
"""

import time
import json
import logging
import os
from pathlib import Path
from typing import List, Set
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
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

        # Get the directory where this script is located
        self.script_dir = Path(__file__).parent.absolute()

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
            self.logger.info(f"Script directory: {self.script_dir}")

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

    def scroll_and_load_content(self, container):
        """Navigate through content using horizontal navigation buttons with proper delays for lazy loading"""
        self.logger.info("Looking for horizontal navigation buttons...")

        try:
            # Button container path provided by user
            button_container_xpath = "/html/body/div[3]/div/div[3]/div[2]/div/div[2]/span[1]/div/div/div[2]/div"

            # Count initial links
            initial_links = len(self.scraped_links)
            self.logger.info(f"Starting with {initial_links} links")

            # Try to find the button container
            try:
                button_container = self.driver.find_element(By.XPATH, button_container_xpath)
                self.logger.info("✓ Found button container")
            except NoSuchElementException:
                self.logger.warning("Button container not found, trying alternatives...")
                button_container = self.find_navigation_buttons()
                if not button_container:
                    self.logger.warning("No navigation buttons found, falling back to scroll method")
                    self.fallback_scroll_method(container)
                    return

            # Look for navigation buttons in the container
            navigation_buttons = self.find_all_navigation_buttons(button_container)

            if navigation_buttons:
                self.navigate_with_buttons(navigation_buttons, container)
            else:
                self.logger.warning("No navigation buttons found, trying scroll method")
                self.fallback_scroll_method(container)

        except Exception as e:
            self.logger.error(f"Button navigation failed: {str(e)}")
            self.logger.info("Falling back to scroll method...")
            self.fallback_scroll_method(container)

    def find_navigation_buttons(self):
        """Find navigation button container using various selectors"""
        button_selectors = [
            # Alternative XPath patterns for the button container
            "/html/body/div[3]/div/div[3]/div[2]/div/div[2]/span[1]/div/div/div[2]",
            "/html/body/div[3]/div/div[3]/div[2]/div/div[2]/span[1]/div/div/div[1]",

            # CSS selectors for common button patterns
            "div[role='button']",
            "button",
            "[aria-label*='next']",
            "[aria-label*='previous']",
            "[aria-label*='scroll']",

            # Look for elements with navigation-like classes
            "//div[contains(@class, 'nav')]",
            "//div[contains(@class, 'button')]",
            "//div[contains(@class, 'scroll')]",
            "//div[contains(@class, 'arrow')]",

            # Look for clickable elements near the main container
            "//div[@role='button'][contains(@style, 'cursor')]",
            "//span[@role='button']",
        ]

        for selector in button_selectors:
            try:
                if selector.startswith("//") or selector.startswith("/html"):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                if elements:
                    self.logger.info(f"Found {len(elements)} potential button elements with: {selector}")
                    return elements[0].find_element(By.XPATH, "..")  # Return parent container

            except Exception as e:
                continue

        return None

    def find_all_navigation_buttons(self, button_container):
        """Find all navigation buttons (next, previous, etc.) in the container"""
        button_patterns = [
            # Look for buttons with navigation attributes
            ".//div[@role='button']",
            ".//button",
            ".//span[@role='button']",
            ".//div[contains(@aria-label, 'next')]",
            ".//div[contains(@aria-label, 'previous')]",
            ".//div[contains(@aria-label, 'scroll')]",

            # Look for elements with click handlers
            ".//div[@onclick]",
            ".//div[contains(@style, 'cursor: pointer')]",
            ".//div[contains(@style, 'cursor:pointer')]",

            # Look for arrow-like elements
            ".//div[contains(@class, 'arrow')]",
            ".//div[contains(text(), '›')]",
            ".//div[contains(text(), '‹')]",
            ".//div[contains(text(), '>')]",
            ".//div[contains(text(), '<')]",

            # SVG icons that might be buttons
            ".//svg/../..",
            ".//svg/..",
        ]

        all_buttons = []

        for pattern in button_patterns:
            try:
                buttons = button_container.find_elements(By.XPATH, pattern)
                for button in buttons:
                    if button not in all_buttons:
                        # Check if element looks clickable
                        if self.is_clickable_element(button):
                            all_buttons.append(button)
            except Exception as e:
                continue

        self.logger.info(f"Found {len(all_buttons)} potential navigation buttons")

        # Debug: show button info
        for i, button in enumerate(all_buttons[:5]):  # Show first 5
            try:
                tag = button.tag_name
                text = button.text.strip()[:20]
                aria_label = button.get_attribute('aria-label') or 'None'
                onclick = button.get_attribute('onclick') or 'None'
                self.logger.info(
                    f"  Button {i + 1}: <{tag}> text='{text}' aria-label='{aria_label}' onclick='{onclick[:30]}...'")
            except:
                pass

        return all_buttons

    def is_clickable_element(self, element):
        """Check if element appears to be clickable"""
        try:
            # Check various indicators of clickability
            role = element.get_attribute('role')
            if role in ['button', 'link']:
                return True

            onclick = element.get_attribute('onclick')
            if onclick:
                return True

            cursor_style = element.value_of_css_property('cursor')
            if cursor_style == 'pointer':
                return True

            # Check if it has click event listeners
            has_listeners = self.driver.execute_script("""
                var element = arguments[0];
                var listeners = getEventListeners(element);
                return listeners && listeners.click && listeners.click.length > 0;
            """, element)

            if has_listeners:
                return True

        except:
            pass

        return False

    def navigate_with_buttons(self, buttons, container):
        """Navigate through content by clicking buttons with proper delays"""
        self.logger.info(f"Navigating with {len(buttons)} buttons...")

        # Initial scrape
        self.scrape_visible_links(container)
        initial_count = len(self.scraped_links)

        # Try clicking each button multiple times to navigate through all content
        max_clicks_per_button = 50  # Adjust based on expected content amount

        for button_index, button in enumerate(buttons):
            self.logger.info(f"Trying button {button_index + 1}/{len(buttons)}")

            clicks_without_new_content = 0
            total_clicks = 0

            while total_clicks < max_clicks_per_button and clicks_without_new_content < 5:
                try:
                    # Get current link count
                    before_click_count = len(self.scraped_links)

                    # Click the button
                    self.driver.execute_script("arguments[0].click();", button)
                    total_clicks += 1

                    # Wait for lazy loading (2.5 seconds as requested)
                    self.logger.info(f"  Click {total_clicks}: Waiting 2.5s for lazy loading...")
                    time.sleep(2.5)

                    # Scrape new content
                    self.scrape_visible_links(container)
                    after_click_count = len(self.scraped_links)

                    new_links = after_click_count - before_click_count
                    if new_links > 0:
                        self.logger.info(f"  ✓ Found {new_links} new links (total: {after_click_count})")
                        clicks_without_new_content = 0
                    else:
                        clicks_without_new_content += 1
                        self.logger.info(f"  No new links found ({clicks_without_new_content}/5 empty clicks)")

                    # Check if we've reached the end (button might become disabled or change)
                    if self.is_button_disabled(button):
                        self.logger.info(f"  Button appears disabled, moving to next button")
                        break

                except Exception as e:
                    self.logger.warning(f"  Error clicking button: {str(e)}")
                    clicks_without_new_content += 1
                    if clicks_without_new_content >= 3:
                        break

            self.logger.info(
                f"Button {button_index + 1} completed: {total_clicks} clicks, {len(self.scraped_links)} total links")

        final_count = len(self.scraped_links)
        self.logger.info(f"Navigation completed: {final_count - initial_count} new links found")

    def is_button_disabled(self, button):
        """Check if a button appears to be disabled"""
        try:
            # Check disabled attribute
            if button.get_attribute('disabled'):
                return True

            # Check aria-disabled
            if button.get_attribute('aria-disabled') == 'true':
                return True

            # Check if button has disabled-like classes
            class_attr = button.get_attribute('class') or ''
            if any(disabled_class in class_attr.lower() for disabled_class in ['disabled', 'inactive', 'hidden']):
                return True

            # Check opacity (sometimes disabled buttons are faded)
            opacity = button.value_of_css_property('opacity')
            if opacity and float(opacity) < 0.5:
                return True

        except:
            pass

        return False

    def fallback_scroll_method(self, container):
        """Fallback to original scrolling method if buttons don't work"""
        self.logger.info("Using fallback scroll method...")

        try:
            # Get container dimensions
            container_width = self.driver.execute_script("return arguments[0].scrollWidth", container)
            visible_width = self.driver.execute_script("return arguments[0].clientWidth", container)

            if container_width > visible_width:
                self.logger.info(f"Scrolling through {container_width}px of content...")

                # Scroll in increments with delays
                scroll_increment = 200
                current_scroll = 0

                while current_scroll < container_width:
                    self.driver.execute_script("arguments[0].scrollLeft = arguments[1]", container, current_scroll)
                    time.sleep(2.5)  # Same delay as button method
                    self.scrape_visible_links(container)
                    current_scroll += scroll_increment

                    if current_scroll % 1000 == 0:  # Log progress every 1000px
                        self.logger.info(f"Scrolled to {current_scroll}px, {len(self.scraped_links)} links found")

        except Exception as e:
            self.logger.error(f"Fallback scroll failed: {str(e)}")

    def scrape_all_links(self, container):
        """Final comprehensive scrape of all links with additional scrolling strategies"""
        self.logger.info("Performing final comprehensive link scrape...")

        # Wait a bit more for any lazy-loaded content
        time.sleep(3)

        # Try alternative scrolling methods that might trigger more content
        self.logger.info("Trying alternative scrolling methods...")

        try:
            # Method 1: Use ActionChains for more natural scrolling
            actions = ActionChains(self.driver)
            actions.move_to_element(container)
            actions.perform()
            time.sleep(1)

            # Scroll with arrow keys (simulates user interaction)
            for _ in range(20):
                actions.send_keys_to_element(container, Keys.ARROW_RIGHT)
                actions.perform()
                time.sleep(0.5)

            time.sleep(3)
            self.scrape_visible_links(container)

            # Method 2: Scroll with mouse wheel simulation
            for i in range(10):
                self.driver.execute_script("""
                    var event = new WheelEvent('wheel', {
                        deltaX: 100,
                        deltaY: 0,
                        bubbles: true
                    });
                    arguments[0].dispatchEvent(event);
                """, container)
                time.sleep(0.8)

            time.sleep(3)
            self.scrape_visible_links(container)

            # Method 3: Try clicking/focusing elements to trigger loading
            try:
                clickable_elements = container.find_elements(By.XPATH, ".//div[@role='button'] | .//a | .//button")
                self.logger.info(f"Found {len(clickable_elements)} clickable elements")

                # Click a few elements to potentially trigger more content
                for i, element in enumerate(clickable_elements[:5]):
                    try:
                        self.driver.execute_script("arguments[0].focus();", element)
                        time.sleep(0.5)
                        # Don't actually click, just focus to avoid navigation
                    except:
                        pass

            except Exception as e:
                self.logger.debug(f"Element interaction failed: {str(e)}")

            # Method 4: Final aggressive scrolling
            self.logger.info("Final aggressive scrolling attempt...")

            # Scroll to various positions multiple times
            positions = [0, 0.25, 0.5, 0.75, 1.0, 0.5, 0]  # Including return trips
            for pos in positions:
                scroll_pos = int(self.driver.execute_script("return arguments[0].scrollWidth", container) * pos)
                self.driver.execute_script("arguments[0].scrollLeft = arguments[1]", container, scroll_pos)
                time.sleep(2.5)
                self.scrape_visible_links(container)

        except Exception as e:
            self.logger.warning(f"Alternative scrolling methods failed: {str(e)}")

        # Final scrape after all scrolling attempts
        self.scrape_visible_links(container)

        self.logger.info(f"Final total links found: {len(self.scraped_links)}")

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
        """Save scraped links to files in the script directory"""
        # Save as JSON
        links_list = sorted(list(self.scraped_links))

        results = {
            'total_links': len(links_list),
            'scrape_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'source_url': self.target_url,
            'script_directory': str(self.script_dir),
            'links': links_list
        }

        # Create file paths in script directory
        json_file_path = self.script_dir / 'hokusai_painting_links.json'
        txt_file_path = self.script_dir / 'hokusai_painting_links.txt'

        # Save as JSON
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        # Save as plain text for easy reading
        with open(txt_file_path, 'w', encoding='utf-8') as f:
            f.write(f"Hokusai Painting Links - Total: {len(links_list)}\n")
            f.write(f"Scraped on: {results['scrape_timestamp']}\n")
            f.write(f"Script directory: {self.script_dir}\n")
            f.write("=" * 50 + "\n\n")
            for i, link in enumerate(links_list, 1):
                f.write(f"{i:3d}. {link}\n")

        self.logger.info(f"Results saved to:")
        self.logger.info(f"  JSON: {json_file_path}")
        self.logger.info(f"  TXT:  {txt_file_path}")

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
    # Get script directory for output information
    script_dir = Path(__file__).parent.absolute()
    print(f"Script running from: {script_dir}")
    print(f"Output files will be saved to: {script_dir}")

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
        print(f"\nFiles saved in: {script_dir}")
        print(f"  - hokusai_painting_links.json")
        print(f"  - hokusai_painting_links.txt")
        print(f"\nFirst 5 links:")
        for i, link in enumerate(links[:5], 1):
            print(f"{i}. {link}")

        if len(links) > 5:
            print("...")

    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()