import requests
import time
import os
import logging
from googletrans import Translator
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

# SETTINGS
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
USGS_FEED = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson'
CHECK_INTERVAL = 60  # in seconds

# Myanmar Bounding Box
MYANMAR_BOUNDS = {
    "min_lat": 9,
    "max_lat": 29,
    "min_lon": 92,
    "max_lon": 101
}

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def load_sent_event_ids():
    try:
        with open("sent_event_ids.txt", "r") as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()


def save_sent_event_ids(sent_event_ids):
    with open("sent_event_ids.txt", "w") as f:
        for event_id in sent_event_ids:
            f.write(event_id + "\n")

sent_event_ids = load_sent_event_ids()
translator = Translator()
bot = Bot(token=BOT_TOKEN)
def is_in_myanmar(lat, lon):
    return (MYANMAR_BOUNDS["min_lat"] <= lat <= MYANMAR_BOUNDS["max_lat"] and
            MYANMAR_BOUNDS["min_lon"] <= lon <= MYANMAR_BOUNDS["max_lon"])

def translate_to_burmese(text):
    try:
        result = translator.translate(text, dest='my')
        return result.text
    except Exception as err:
        logger.error(f"Translation failed: {err}")
        return text  # fallback to English
def fetch_and_send():
    global sent_event_ids
    try:
        res = requests.get(USGS_FEED)
        data = res.json()

        for feature in data['features']:
            props = feature['properties']
            geom = feature['geometry']
            quake_id = feature['id']

            if quake_id in sent_event_ids:
                continue

            lat, lon, depth = geom['coordinates'][1], geom['coordinates'][0], geom['coordinates'][2]

            if not is_in_myanmar(lat, lon):
                continue

            mag = props['mag']
            place = props['place']
            time_utc = time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(props['time'] / 1000))
            url = props['url']

            msg_en = (
                f"**Earthquake Alert - Myanmar**\n\n"
                f"**Magnitude:** {mag}\n"
                f"**Location:** {place}\n"
                f"**Depth:** {depth} km\n"
                f"**Time:** {time_utc}\n\n"
                f"[More Info]({url}) "
            )

            msg_mm = translate_to_burmese(msg_en)

            # Telegram expects MarkdownV2-style escaping
            msg_mm = msg_mm.replace("-", "\\-")
            try:
                bot.send_message(chat_id=CHANNEL_ID, text=msg_mm, parse_mode='MarkdownV2')
            except TelegramError as e:
                logger.error(f"Failed to send message to Telegram: {e}")
                # Implement retry logic if needed
                continue
            sent_event_ids.add(quake_id)
            save_sent_event_ids(sent_event_ids)
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while fetching data: {e}")
    except Exception as err:
        logger.error(f"An unexpected error occurred: {err}")

# Looping to check every X seconds
if __name__ == '__main__':
    logger.info("Bot started. Monitoring earthquakes in Myanmar...")
    try:
        bot.send_message(chat_id=CHANNEL_ID, text="Test Message: Bot started successfully!")
        logger.info("Test message sent successfully.")
    except TelegramError as e:
        logger.error(f"Failed to send test message: {e}")

    while True:
        fetch_and_send()
        time.sleep(CHECK_INTERVAL)
