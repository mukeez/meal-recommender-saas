-- Migration: Google Places API Integration
-- Description: Add support for Google Places restaurants, truncate scraped data, add new columns
-- Date: 2025-10-23

-- Step 1: Backup existing scraped restaurants (optional safety measure)
CREATE TABLE IF NOT EXISTS restaurants_backup_scraped AS 
SELECT * FROM restaurants WHERE source = 'scraper';

-- Step 2: Truncate restaurants table to start fresh with Google Places
TRUNCATE TABLE restaurants CASCADE;

-- Step 3: Add new columns for Google Places integration
ALTER TABLE restaurants 
  ADD COLUMN IF NOT EXISTS google_place_id VARCHAR UNIQUE,
  ADD COLUMN IF NOT EXISTS place_types JSONB,
  ADD COLUMN IF NOT EXISTS price_level INTEGER CHECK (price_level >= 1 AND price_level <= 4),
  ADD COLUMN IF NOT EXISTS photo_references JSONB,
  ADD COLUMN IF NOT EXISTS data_source VARCHAR DEFAULT 'google_places',
  ADD COLUMN IF NOT EXISTS last_updated_at TIMESTAMP DEFAULT NOW();

-- Step 4: Modify menu_url to allow longer URLs (Google Places URLs can be long)
ALTER TABLE restaurants 
  ALTER COLUMN menu_url TYPE TEXT;

-- Step 5: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_restaurants_google_place_id 
  ON restaurants(google_place_id);

CREATE INDEX IF NOT EXISTS idx_restaurants_place_types 
  ON restaurants USING GIN(place_types);

CREATE INDEX IF NOT EXISTS idx_restaurants_data_source 
  ON restaurants(data_source);

CREATE INDEX IF NOT EXISTS idx_restaurants_last_updated 
  ON restaurants(last_updated_at);

-- Step 6: Add constraint to ensure google_place_id for new Google Places entries
ALTER TABLE restaurants 
  ADD CONSTRAINT restaurants_google_place_id_required 
  CHECK (data_source != 'google_places' OR google_place_id IS NOT NULL);

-- Step 7: Create function to auto-update last_updated_at timestamp
CREATE OR REPLACE FUNCTION update_restaurant_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 8: Create trigger for auto-updating timestamp
DROP TRIGGER IF EXISTS restaurants_update_timestamp ON restaurants;
CREATE TRIGGER restaurants_update_timestamp
    BEFORE UPDATE ON restaurants
    FOR EACH ROW
    EXECUTE FUNCTION update_restaurant_timestamp();

-- Step 9: Add comments for documentation
COMMENT ON TABLE restaurants IS 'Restaurants sourced from Google Places API (post-migration Oct 2025)';
COMMENT ON COLUMN restaurants.google_place_id IS 'Google Places unique identifier (place_id from API)';
COMMENT ON COLUMN restaurants.place_types IS 'Array of Google Places types (e.g., ["italian_restaurant", "cafe"])';
COMMENT ON COLUMN restaurants.data_source IS 'Source of restaurant data (google_places, manual, etc.)';
COMMENT ON COLUMN restaurants.price_level IS 'Google Places price level (1=cheap, 4=expensive)';
COMMENT ON COLUMN restaurants.photo_references IS 'Google Places photo references for future use';
COMMENT ON COLUMN restaurants.menu_url IS 'URL to restaurant menu (extracted from Google Places website field)';

-- Step 10: Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Google Places integration migration completed successfully';
    RAISE NOTICE 'Restaurants table truncated and ready for Google Places data';
END $$;
