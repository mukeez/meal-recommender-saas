# Constants for unit conversions
LBS_TO_KG = 0.453592
INCHES_TO_CM = 2.54
CM_TO_INCHES = 1 / INCHES_TO_CM
GRAMS_PER_OUNCE = 28.3495

# Serving units
class ServingUnit:
    GRAMS = "grams"
    OUNCES = "ounces"

def convert_to_grams(value: float, unit: str) -> float:
    """Convert serving size to grams."""
    if unit == ServingUnit.OUNCES:
        return value * GRAMS_PER_OUNCE
    return value  # Already in grams

def convert_from_grams(value: float, target_unit: str) -> float:
    """Convert serving size from grams to target unit."""
    if target_unit == ServingUnit.OUNCES:
        return value / GRAMS_PER_OUNCE
    return value  # Already in grams

def parse_gram_quantity(quantity_str: str) -> float:
    """Parse gram quantity from strings like '150g', '100g', etc.
    
    Args:
        quantity_str: String containing gram quantity (e.g., "150g", "100g")
        
    Returns:
        Float value of the gram quantity, defaults to 1.0 if parsing fails
    """
    import re
    
    # Extract numbers from the string, looking for patterns like "150g" or "100 g"
    match = re.search(r'(\d+(?:\.\d+)?)\s*g', quantity_str.lower())
    if match:
        return float(match.group(1))
    
    # Fallback: try to extract any number from the string
    numbers = re.findall(r'\d+(?:\.\d+)?', quantity_str)
    if numbers:
        return float(numbers[0])
    
    # Default to 1 gram if no parseable quantity found
    return 1.0

def normalize_nutrition_to_per_gram(calories: float, protein: float, carbs: float, fat: float, total_grams: float) -> tuple[float, float, float, float]:
    """Normalize nutritional values to per-gram basis.
    
    Args:
        calories: Total calories for the given quantity
        protein: Total protein in grams for the given quantity
        carbs: Total carbs in grams for the given quantity
        fat: Total fat in grams for the given quantity
        total_grams: Total weight in grams that the nutrition values represent
        
    Returns:
        Tuple of (calories_per_gram, protein_per_gram, carbs_per_gram, fat_per_gram)
    """
    if total_grams <= 0:
        return 0.0, 0.0, 0.0, 0.0
    
    return (
        calories / total_grams,
        protein / total_grams,
        carbs / total_grams,
        fat / total_grams
    )

def calculate_nutrition_for_amount(calories_per_gram: float, protein_per_gram: float, carbs_per_gram: float, fat_per_gram: float, amount_grams: float) -> tuple[float, float, float, float]:
    """Calculate nutritional values for a specific amount of grams.
    
    Args:
        calories_per_gram: Calories per gram
        protein_per_gram: Protein per gram
        carbs_per_gram: Carbs per gram
        fat_per_gram: Fat per gram
        amount_grams: Amount in grams to calculate for
        
    Returns:
        Tuple of (total_calories, total_protein, total_carbs, total_fat)
    """
    return (
        calories_per_gram * amount_grams,
        protein_per_gram * amount_grams,
        carbs_per_gram * amount_grams,
        fat_per_gram * amount_grams
    )

# Constants for macro calculations
PROTEIN_PER_KG = 1.8
FAT_PER_KG = 1.0
PROTEIN_CALS_PER_GRAM = 4
FAT_CALS_PER_GRAM = 9
CARB_CALS_PER_GRAM = 4
MIN_CARBS_GRAMS = 50


# Constants for goal calculations
CALORIES_PER_LB = 3500
CALORIES_PER_KG = 7700


USER_AGENTS = [
    # MACINSTOSH - Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.3124.85",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 OPR/118.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; Xbox; Xbox One) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edge/44.18363.8131",

    # Desktop - Windows
                
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Trailer/93.3.8652.5",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 OPR/117.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0"]
 

STEALTH_JS = """
        () => {
            // Helper to override navigator properties
            const overrideNavigator = (property, value) => {
                Object.defineProperty(navigator, property, {
                    get: () => value
                });
            };
            
            // 1. Mask WebDriver
            overrideNavigator('webdriver', false);
            
            // 2. Add plugins and mimeTypes
            const makeFakePluginArray = () => {
                const plugins = [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: 'Portable Document Format' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin', description: 'Native Client Executable' }
                ];
                
                const pluginArray = plugins.map(plugin => {
                    const mimeTypes = [{ type: 'application/pdf', suffixes: 'pdf', description: plugin.description }];
                    return { ...plugin, mimeTypes };
                });
                
                return pluginArray;
            };
            
            const fakePlugins = makeFakePluginArray();
            
            // Override plugins and mimeTypes
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = fakePlugins.map(plugin => {
                        return {
                            ...plugin,
                            length: 1,
                            refresh: () => {},
                            item: () => plugin
                        };
                    });
                    
                    plugins.refresh = () => {};
                    plugins.item = (index) => plugins[index];
                    plugins.namedItem = (name) => plugins.find(plugin => plugin.name === name);
                    plugins.__proto__ = plugins.__proto__;
                    
                    return plugins;
                }
            });
            
            // 3. Override hardware concurrency & device memory
            overrideNavigator('hardwareConcurrency', 8);
            overrideNavigator('deviceMemory', 8);
            
            // 4. Add language preferences
            overrideNavigator('languages', ['en-US', 'en']);
            
            // 5. Chrome specific overrides for automation flags
            if (window.chrome === undefined) {
                window.chrome = {
                    app: { isInstalled: false },
                    runtime: {},
                    loadTimes: () => {},
                    csi: () => {},
                    webstore: {}
                };
            }
            
            // 6. Modify canvas fingerprinting
            const originalGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type, attributes) {
                const context = originalGetContext.call(this, type, attributes);
                if (context && type === '2d') {
                    const originalGetImageData = context.getImageData;
                    context.getImageData = function(...args) {
                        const imageData = originalGetImageData.apply(this, args);
                        // Modify a few random pixels slightly
                        if (imageData && imageData.data && imageData.data.length > 10) {
                            const offset = Math.floor(Math.random() * (imageData.data.length / 10));
                            imageData.data[offset] = (imageData.data[offset] + Math.floor(Math.random() * 10)) % 255;
                            imageData.data[imageData.data.length - offset - 1] = 
                                (imageData.data[imageData.data.length - offset - 1] + Math.floor(Math.random() * 10)) % 255;
                        }
                        return imageData;
                    };
                    
                    const originalMeasureText = context.measureText;
                    context.measureText = function(...args) {
                        const textMetrics = originalMeasureText.apply(this, args);
                        const originalWidth = textMetrics.width;
                        Object.defineProperty(textMetrics, 'width', { 
                            get: () => originalWidth + Math.random() * 0.0000001 
                        });
                        return textMetrics;
                    };
                }
                return context;
            };
            
            // 7. Override permission behavior
            const originalPermission = window.Notification?.requestPermission;
            if (originalPermission) {
                window.Notification.requestPermission = function() {
                    return Promise.resolve('denied');
                };
            }
            
            // 8. Mask all automation-related objects
            delete window.__playwright;
            delete window.__nightmareJS;
            delete window.__puppeteer;
            delete window.__selenium;
            delete window.__webdriver;
            delete window.__driver;
            delete window.__nightmare;
            delete window.callSelenium;
            delete window.callPhantom;
            delete window._phantom;
            delete window.Buffer;
            delete window.emit;
            delete window.spawn;
            
            // 9. Add common browser functions and properties
            window.outerHeight = window.innerHeight;
            window.outerWidth = window.innerWidth;
            window.screenX = 20;
            window.screenY = 20;
            window.screenLeft = 20;
            window.screenTop = 20;
        }
        """