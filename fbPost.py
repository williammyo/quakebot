import os
import logging
import requests
from dotenv import load_dotenv
from discord_logger import DiscordLogHandler

# Load environment variables
load_dotenv()

# ============ Config ============ #
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
FB_API_VERSION = "v18.0"
FB_GRAPH_URL = f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/photos"

logger = logging.getLogger("FBPoster")
logger.setLevel(logging.INFO)

# ============ Discord Log Handler ============ #
discord_handler = DiscordLogHandler()
discord_handler.setLevel(logging.INFO)
discord_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
discord_handler.setFormatter(discord_formatter)
logger.addHandler(discord_handler)

# ============ Facebook Poster ============ #
def post_image_to_facebook(image_path, caption):
    """
    Upload an image to Facebook Page with a caption and return (page_id, post_id).
    """
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        logger.error("Missing Facebook Page ID or Token in environment variables.")
        return None, None

    if not os.path.exists(image_path):
        logger.error(f"Image file not found: {image_path}")
        return None, None

    try:
        with open(image_path, 'rb') as img:
            files = {'source': img}
            data = {
                'caption': caption,
                'access_token': FB_PAGE_TOKEN
            }
            response = requests.post(FB_GRAPH_URL, files=files, data=data)
            result = response.json()
            if "id" in result:
                full_id = result['id']
                logger.info(f"Succesfully alerted Facebook! PostID: {full_id}")
                if "_" in full_id:
                    page_id, post_id = full_id.split("_")
                else:
                    page_id = FB_PAGE_ID
                    post_id = full_id
                return page_id, post_id
            else:
                logger.error(f"Facebook API Error: {result}")
                return None, None
    except Exception as e:
        logger.error(f"Exception during Facebook upload: {e}")
        return None, None

# ============ Example Call (for testing) ============ #
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    post_image_to_facebook("quake_map.png", "🔔 Earthquake Alert! Stay safe. #Myanmar")
