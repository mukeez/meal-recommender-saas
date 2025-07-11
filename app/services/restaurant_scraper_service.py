"""
Restaurant Scraper Service using Playwright with Stealth Mode and Anti-Detection Measures
"""
from playwright.async_api import async_playwright
import asyncio
import random
import logging
from typing import List, Dict, Any
from copy import deepcopy

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import random
from collections import deque

from app.utils.slack import send_slack_alert
from app.utils.constants import USER_AGENTS, STEALTH_JS

class UserAgentRotator:
    """Rotates user agents to avoid detection."""
    def __init__(self, user_agents: List, n: int =3):
        """
        Initializes the RestaurantScraper instance with a list of user agents and a limit for tracking the last used agents.

            user_agents (List): A list of user agent strings to be used for web scraping.
            n (int, optional): The maximum number of recently used user agents to track. Defaults to 3.
        """    
        self.user_agents = list(user_agents)
        self.n = min(n, len(self.user_agents) - 1) if len(self.user_agents) > 1 else 0
        self.last_n = deque(maxlen=self.n)

    def get_next(self):
        """      
        Returns:
            str: A user agent string from the list, avoiding the last n used.
        """
        available = [ua for ua in self.user_agents if ua not in self.last_n]
        if not available:
            self.last_n.clear()
            available = self.user_agents[:]
        ua = random.choice(available)
        self.last_n.append(ua)
        return ua

class RestaurantScraper:
    """Restaurant scraper using Playwright with stealth mode and anti-detection measures."""
    
    def __init__(self):
        """Initialize the Playwright restaurant scraper."""
        self.browser = None
        self.page = None
        self.user_agents = USER_AGENTS
        self.ua_rotator = UserAgentRotator(self.user_agents, n=2)
    
    async def _random_delay(self, min_seconds=1, max_seconds=3):
        """Add a random delay to mimic human behavior."""
        await asyncio.sleep(random.uniform(min_seconds, max_seconds))
    
    async def _handle_popups(self):
        """Handle any popup or intercepted click dialogs."""
        try:
            # More generic selector that targets g-lightbox's close button regardless of ID
            popup_selector = '//*[@id="_eK84aKMC2Y327w_i_b-4CA_12"]/g-lightbox/div/div[2]/div[2]'
            
            close_button = await self.page.query_selector(popup_selector)
            if close_button:
                logger.info(f"Found popup to close with selector")
                await close_button.click()
                await self._random_delay(0.5, 1.5)
                return True
            
            return False
        except Exception as e:
            logger.debug(f"Error handling popups: {e}")
            return False
    
    def get_user_agent(self) -> str:
        """Return a rotated user agent string, avoiding the last n used."""
        return self.ua_rotator.get_next()

    async def _apply_stealth_scripts(self, context):
        """Apply stealth scripts to avoid detection."""
        # Comprehensive stealth script to avoid bot detection
        await context.add_init_script(STEALTH_JS)
    
    async def scrape_restaurants(self, location: str, pages: int = 1) -> List[Dict[str, Any]]:
        """Scrape restaurant data for a location."""
        logger.info(f"Starting to scrape restaurants in {location}")
        
        async with async_playwright() as p:
            # Launch a browser with stealth mode and headless enabled
            self.browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-sandbox',
                    '--no-zygote',
                    '--disable-setuid-sandbox',
                    '--disable-gpu',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-infobars',
                    '--window-position=0,0'
                ],
            )
            
            # Create a browser context with custom settings
            # viewport_width = random.randint(1050, 1920)
            # viewport_height = random.randint(800, 1080)
            user_agent = self.get_user_agent()
            
            context = await self.browser.new_context(
                # viewport={'width': viewport_width, 'height': viewport_height},
                user_agent=user_agent,
                locale="en-US",
                timezone_id="America/New_York",
                permissions=['geolocation'],
                color_scheme='no-preference',
            )
            
            # Apply stealth scripts
            # await self._apply_stealth_scripts(context)
            
            # Create a new page
            self.page = await context.new_page()
            
            # Randomize HTTP headers
            await self.page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'max-age=0',
                'Sec-Ch-Ua': '"Chromium";v="116", "Google Chrome";v="116"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://www.google.com/'
            })
        
            # Increase the navigation timeout
            self.page.set_default_navigation_timeout(120000)  # 120 seconds
            
            restaurants = []
            
            try:
                # Handle navigation with better error handling and wait strategy
                logger.info(f"Navigating to search page for {location}")
                try:
                    # First try with 'domcontentloaded' which is faster than waiting for full load
                    await self.page.goto(
                        f"https://www.google.com/search?q=restaurants+in+{location}",
                        wait_until="domcontentloaded"
                    )
                    # Random wait time after page load
                    await self._random_delay(5, 7)

                    # Check for CAPTCHA presence
                    if await self._is_captcha_present():
                        logger.error("CAPTCHA detected, cannot proceed with scraping.")
                        send_slack_alert(f"CAPTCHA detected while scraping restaurants in {location} with User-Agent:{user_agent}.", title="⚠️ CAPTCHA Alert")
                        return []
                    
                    # Perform random mouse movements to mimic human
                    await self._perform_random_mouse_movements()
                    
                except Exception as e:
                    logger.warning(f"Initial navigation attempt failed: {e}, retrying...")
                    # If that fails, try with the default 'load' event
                    await self.page.goto(f"https://www.google.com/search?q=restaurants+in+{location}")

                    #Check for CAPTCHA again after retry
                    if await self._is_captcha_present():
                        logger.error("CAPTCHA detected after retry, cannot proceed with scraping.")
                        send_slack_alert(f"CAPTCHA detected while scraping restaurants in {location} after retry with User-Agent:{user_agent}.", title="⚠️ CAPTCHA Alert")
                        return []
                
                # Random delay
                await self._random_delay(3, 5)
                
                # Check for popups immediately after loading
                await self._handle_popups()
                
                # Try to find and click "View all" for restaurants
                try:
                    logger.info("Looking for 'View all' link to expand restaurant list")
                    view_all_selector = '//*[@id="Odp5De"]/div[1]/div/div/div/div[1]/div[2]/div/div[1]/div[2]/div/h3/g-more-link/a'
                    
                    view_all = await self.page.query_selector(view_all_selector)
                    if view_all:
                        # Scroll to element with randomization
                        await self._scroll_to_element_with_randomization(view_all)
                        await self._random_delay(3, 5)
                        
                        # Click the element with human-like timing
                        await self._human_like_click(view_all)
                        logger.info("Clicked 'View all' successfully")
                        
                        # Check for popups after clicking "View all"
                        await self._random_delay(2, 4)
                        await self._handle_popups()
                
                except Exception as e:
                    logger.warning(f"Could not find or click 'View all' link: {e}")
                    # Check for popups even when clicking fails
                    await self._handle_popups()
                
                # Process each page
                for page_num in range(pages):
                    logger.info(f"Processing page {page_num + 1}/{pages}")
                    
                    # Random delay between pages
                    await self._random_delay(5, 8)
                    
                    # Find all restaurant elements
                    restaurant_elements = await self.page.query_selector_all('div[jsname="MZArnb"]')
                    logger.info(f"Found {len(restaurant_elements)} restaurant elements on page {page_num + 1}")

                    
                    logger.info(f"Processing {len(restaurant_elements)} restaurant elements on page {page_num + 1}")
                    # Process each restaurant
                    for i, element in enumerate(restaurant_elements):
                        try:
                            if i == 10:
                                break
                            # Scroll element into view with natural behavior
                            await self._scroll_to_element_with_randomization(element)
                            await self._random_delay(0.5, 1.5)

                            # Find and click on restaurant name to open details
                            name_element = await element.query_selector('.OSrXXb')
                            if name_element:
                                name_text = await name_element.inner_text()
                                logger.info(f"Processing restaurant: {name_text}")
                                
                                # Click to view details with human-like behavior
                                await self._human_like_click(name_element)
                                await self._random_delay(3, 5)
                                
                                # Check for popups after clicking on restaurant
                                if await self._handle_popups():
                                    # If a popup was closed, click again to ensure details are shown
                                    try:
                                        await self._human_like_click(name_element)
                                        await self._random_delay(2, 3)
                                    except:
                                        pass
                                
                                await self._random_delay(3, 10)

                                # Extract restaurant details with additional popup handling
                                restaurant_data = await self._extract_restaurant_details()
                                # Add name if we have it but extraction failed
                                if restaurant_data.get("name") is None and name_text:
                                    restaurant_data["name"] = name_text
                                    
                                restaurants.append(deepcopy(restaurant_data))
                                
                                # Handle popups again after extraction before moving on
                                await self._handle_popups()
                            
                        except Exception as e:
                            logger.error(f"Error processing restaurant element {i}: {str(e)}")
                            # Try to close any popups that might have caused the error
                            await self._handle_popups()
                            continue
                    
                    # Try to navigate to next page if needed
                    if page_num < pages - 1:
                        try:
                            # Handle popups before trying to navigate
                            await self._handle_popups()
                            
                            next_button = await self.page.query_selector('#pnnext')
                            if next_button:
                                await self._scroll_to_element_with_randomization(next_button)
                                await self._random_delay(1, 2)
                                await self._human_like_click(next_button)
                                await self._random_delay(3, 5)
                                
                                # Check for popups after navigation
                                await self._handle_popups()
                                
                                logger.info(f"Navigated to page {page_num + 2}")
                            else:
                                logger.warning("No next page button found")
                                break
                        except Exception as e:
                            logger.warning(f"Could not navigate to next page: {e}")
                            await self._handle_popups()
                            break

                if not restaurants:
                    logger.warning(f"No restaurant data found for {location} after scraping {pages} pages.")
                    send_slack_alert(f"No restaurant data found for {location} after scraping {pages} pages.", title="⚠️ No Data Found")

                logger.info(f"Scraping completed for {location}. Found {len(restaurants)} restaurants.")
                
                return restaurants
                
            except Exception as e:
                error_msg = f"Error during restaurant scraping: {str(e)}"   
                logger.error(error_msg)
                send_slack_alert(error_msg, title="⚠️ Scraping Error")
                return []
                
            finally:
                if self.browser:
                    await self.browser.close()
                    logger.info("Browser closed")
    
    async def _perform_random_mouse_movements(self):
        """Perform random mouse movements to appear more human-like."""
        try:
            # Get viewport size
            viewport_size = self.page.viewport_size
            width = viewport_size['width']
            height = viewport_size['height']
            
            # Perform 3-7 random movements
            moves = random.randint(3, 7)
            for _ in range(moves):
                x = random.randint(10, width - 10)
                y = random.randint(10, height - 10)
                await self.page.mouse.move(x, y)
                await self._random_delay(0.1, 0.5)
        except Exception as e:
            logger.debug(f"Error in mouse movements: {e}")
            pass
    
    async def _scroll_to_element_with_randomization(self, element):
        """Scroll to element with natural, randomized behavior."""
        try:
            # Get element position
            box = await element.bounding_box()
            if not box:
                return
            
            # Current scroll position
            current_scroll = await self.page.evaluate("() => window.scrollY")
            target_scroll = box['y'] - random.randint(50, 200)  # Randomize target position
            
            # Break down the scroll into multiple small steps to look more natural
            distance = target_scroll - current_scroll
            steps = random.randint(5, 15)  # Randomize number of steps
            
            for i in range(1, steps + 1):
                # Calculate intermediate position with slight randomization
                pos = current_scroll + (distance * i / steps) + random.randint(-5, 5)
                await self.page.evaluate(f"window.scrollTo(0, {pos})")
                await self._random_delay(0.05, 0.15)
        
        except Exception as e:
            # Fallback to basic scroll if the advanced method fails
            logger.debug(f"Error in scroll randomization: {e}")
            try:
                await element.scroll_into_view_if_needed()
            except:
                pass
    
    async def _human_like_click(self, element):
        """Click an element with human-like behavior."""
        try:
            box = await element.bounding_box()
            if not box:
                # Fallback to regular click if we can't get position
                await element.click()
                return
            
            # Calculate a slightly random position within the element
            x = box['x'] + box['width'] * random.uniform(0.2, 0.8)
            y = box['y'] + box['height'] * random.uniform(0.2, 0.8)
            
            # Move mouse to element with variable speed
            await self.page.mouse.move(x, y, steps=random.randint(3, 10))
            
            # Small delay before clicking (humans aren't instant)
            await self._random_delay(0.05, 0.2)
            
            # Click with random duration
            await self.page.mouse.down()
            await self._random_delay(0.05, 0.15)
            await self.page.mouse.up()
            
        except Exception as e:
            logger.debug(f"Error in human-like click: {e}")
            # Fallback to regular click
            await element.click()
    
    async def _extract_restaurant_details(self) -> Dict[str, Any]:
        """Extract details from a restaurant's page."""
        restaurant = {}

        # Random delay before extraction
        await self._random_delay(1, 2)
        
        tabs = await self.page.query_selector_all('[jsname="AznF2e"]')
        
        if tabs and len(tabs) > 0:
            await self._human_like_click(tabs[0])

            # handle popups
            await self._handle_popups()
        
        try:
            # Restaurant name
            name_element = await self.page.query_selector('.SPZz6b')
            if name_element:
                h2_element = await name_element.query_selector('h2')
                if h2_element:
                    span_element = await h2_element.query_selector('span')
                    if span_element:
                        restaurant["name"] = (await span_element.inner_text()).strip()
            
            # Rating
            try:
                rating_element = await self.page.query_selector('.Aq14fc')
                restaurant["rating"] = (await rating_element.inner_text()).strip() if rating_element else ""
            except:
                restaurant["rating"] = ""
            
            # Location/Address
            try:
                location_element = await self.page.query_selector('.LrzXr')
                restaurant["location"] = (await location_element.inner_text()).strip() if location_element else ""
            except:
                restaurant["location"] = ""
            
            # Phone number
            try:
                phone_element = await self.page.query_selector('span.LrzXr.zdqRlf.kno-fv')
                restaurant["phone"] = (await phone_element.inner_text()).strip() if phone_element else ""
            except:
                restaurant["phone"] = ""

            # Website Url
            try:
                # Find div with ssk attribute containing "14_0:location"
                website_div = await self.page.query_selector('div[ssk*="14:0_local_action"]')
                if website_div:
                    # Find the a tag within this div
                    website_link = await website_div.query_selector('a')
                    if website_link:
                        # Extract the href attribute
                        href = await website_link.get_attribute('href')
                        restaurant["website"] = href if href else ""
                        logger.info(f"Found website: {restaurant['website']}")
                    else:
                        restaurant["website"] = ""
                else:
                    restaurant["website"] = ""
            except Exception as e:
                logger.debug(f"Error extracting website: {e}")
                restaurant["website"] = ""

            # Menu url
            try:
                # Find span with class GkdNbc
                spans = self.page.locator("span.GKdNbc")
                menu_url = restaurant["website"] if restaurant["website"] else ""

                span_count = await spans.count()
                for i in range(span_count):
                    text = await spans.nth(i).inner_text()
                    if "Menu" in text.strip():
                        # Found the target span, get the next sibling span with no class and extract <a href>
                        target_link = spans.nth(i).locator("xpath=following-sibling::span[not(@class)][1]/a")
                        if await target_link.count() > 0:
                            menu_url = await target_link.first.get_attribute("href")
                            logger.info(f"Menu URL: {menu_url}")
                        break  # Stop after the first match

                restaurant["menu_url"] = menu_url
            except Exception as e:
                logger.debug(f"Error extracting menu URL: {e}")
                restaurant["menu_url"] = restaurant["website"] if restaurant["website"] else ""
                
                    
            # Opening hours
            try:
                hours_button = await self.page.query_selector('.IDu36')
                if hours_button:
                    await self._scroll_to_element_with_randomization(hours_button)
                    await self._random_delay(0.5, 1)
                    await self._human_like_click(hours_button)
                    await self._random_delay(1, 2)
                    
                    # Check for popups after clicking the hours button
                    await self._handle_popups()
                    
                    hours_element = await self.page.query_selector('.WgFkxc')
                    if hours_element:
                        hours_text = await hours_element.inner_text()
                        if hours_text:
                            restaurant["hours"] = hours_text
                        else:
                            hours_table = await self.page.query_selector('table.WgFkxc')
                            restaurant["hours"] = await hours_table.inner_text() if hours_table else "Hours not available"
                    
                    # Close the hours dialog if it opened one
                    try:
                        # Check for specific lightbox close button
                        close_selectors = [
                            '//*[@id="gsr"]/div[*]/g-lightbox/div/div[2]/div[2]',
                            '//g-lightbox/div/div[2]/div[2]',
                            '//div[@role="dialog"]//button'
                        ]
                        
                        for selector in close_selectors:
                            close_button = await self.page.query_selector(selector)
                            if close_button and await close_button.is_visible():
                                await self._human_like_click(close_button)
                                await self._random_delay(0.5, 1)
                                break
                    except:
                        # If we can't find the close button, try to handle any popup
                        await self._handle_popups()
                else:
                    restaurant["hours"] = ""
            except:
                restaurant["hours"] = ""
                # Ensure we handle popups even if getting hours fails
                await self._handle_popups()

            # Check if there's a menu tab and process it
            if tabs and len(tabs) > 1:
                try:
                    # Random delay before clicking menu tab
                    await self._random_delay(0.5, 1.5)
                    
                    # Click menu tab with human-like behavior
                    await self._human_like_click(tabs[1])
                    
                    # Handle popups     
                    await self._handle_popups()
                    
                    # Random delay before extraction
                    await self._random_delay(1, 2)
                    
                    # Extract meal names and descriptions   
                    meal_names = await self.page.query_selector_all('.gq9CCd')
                    meal_desc = await self.page.query_selector_all('.LvL5Ne')
                    restaurant["menu"] = []
                    
                    for name, desc in zip(meal_names, meal_desc):
                        name_text = await name.inner_text() if name else ""
                        desc_text = await desc.inner_text() if desc else ""
                        meal_info = {
                            "name": name_text.strip(),
                            "description": desc_text.strip()
                        }
                        restaurant["menu"].append(meal_info)
                        
                        # Occasional small delay during extraction to mimic human reading
                        if random.random() < 0.3:
                            await self._random_delay(0.2, 0.5)

                except Exception as e:
                    logger.error(f"Error extracting menu details: {str(e)}")
                    # Handle popups that might have interfered
                    await self._handle_popups()
                    restaurant["menu"] = []
            
        except Exception as e:
            logger.error(f"Error extracting restaurant details: {str(e)}")
            # Try to close any popups that might have interfered
            await self._handle_popups()
        
        return restaurant
    
    async def _is_captcha_present(self) -> bool:
        """Check if a CAPTCHA is present on the current page."""
        try:
            # Check URL for CAPTCHA indicators
            current_url = self.page.url
            if "sorry/index" in current_url or "captcha" in current_url:
                return True
                
            # Check for common CAPTCHA text
            page_text = await self.page.content()
            captcha_indicators = [
                "unusual traffic", 
                "verify you're a human", 
                "security check",
                "prove you're not a robot",
                "captcha"
            ]
            
            for indicator in captcha_indicators:
                if indicator.lower() in page_text.lower():
                    return True
                    
            # Check for reCAPTCHA elements
            captcha_selectors = [
                "iframe[src*='recaptcha']",
                "div.g-recaptcha",
                "div[class*='captcha']",
                "input[name*='captcha']"
            ]
            
            for selector in captcha_selectors:
                if await self.page.query_selector(selector):
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Error checking for CAPTCHA: {str(e)}")
            return False


# Create the scraper instance
scraper_service = RestaurantScraper()