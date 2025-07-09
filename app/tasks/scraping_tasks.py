from app.worker import celery_app
from app.services.restaurant_scraper_service import scraper_service
from app.services.base_database_service import BaseDatabaseService
from app.services.location_service import location_service
from app.utils.helper_functions import deduplicate_dict_list
import logging
import json
import asyncio
from copy import deepcopy
import traceback
import time

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="restaurant_scraper")
def scrape_restaurants_task(self, location_name, latitude, longitude):
    """
    Celery task to scrape restaurants for a given location
    """
    try:
        bulk_restaurant_data = []
        # Initialize services
        if not BaseDatabaseService.subclasses:
            raise Exception("No database service implementation available")
                
        # Scrape restaurants
        restaurants = asyncio.run(scraper_service.scrape_restaurants(
            location=location_name,
            pages=1
        ))

        print(f"Scraped:{restaurants}")
        
        # Process and geocode each restaurant
        for restaurant in restaurants:
            try:
                restaurant_address = restaurant.get('location', '').strip() 
                if restaurant_address:
                    # Use the geocoder to get coordinates
                    time.sleep(2)  # Rate limit to avoid hitting geocoding service too fast
                    lat, lng = location_service.geocode_address(restaurant_address)
                    
                    if lat is not None and lng is not None:
                        logger.info(f"couldn't find coordinates for {restaurant['name']} at {restaurant_address}, using geocoded coordinates: {lat}, {lng}")
                        # Use geocoded coordinates
                        restaurant_lat = lat
                        restaurant_lng = lng
                    else:
                        # Fall back to provided location coordinates
                        restaurant_lat = latitude
                        restaurant_lng = longitude
                else:
                    # No address, use provided coordinates
                    restaurant_lat = latitude
                    restaurant_lng = longitude
                
                # Map scraped data to database schema with geocoded coordinates
                restaurant_data = {
                    "name": restaurant['name'],
                    "address": restaurant_address,
                    "latitude": restaurant_lat,
                    "longitude": restaurant_lng,
                    "rating": restaurant.get('rating', ''),
                    "phone": restaurant.get('phone', ''),
                    "website": restaurant.get('website', ''),
                    "menu_url": restaurant.get('menu_url', ''),
                    "source": 'scraper',
                    "menu_items": json.dumps(restaurant.get('menu', []))
                }

                bulk_restaurant_data.append(deepcopy(restaurant_data))
                
            
                logger.info(f"Inserted restaurant: {restaurant.get('name')}")
                
            except Exception as e:
                logger.error(f"Error processing restaurant : {str(e)}")


        # Insert into database
        if bulk_restaurant_data:
            dedup_restaurants = deduplicate_dict_list(bulk_restaurant_data)
            logger.info(f"Inserting {len(dedup_restaurants)} restaurants into database")
            BaseDatabaseService.subclasses[0]().insert_data(
                table_name="restaurants", 
                data=dedup_restaurants
            )
        
        return {"status": "success", "count": len(dedup_restaurants)}
        
    except Exception as e:
        logger.error(f"Scraping task failed: {e}")
        traceback.print_exc()
        return {"status": "error", "message": str(e)}