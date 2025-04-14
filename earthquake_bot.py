import requests
import time
from googletrans import Translator
from telegram import Bot

# SETTINGS
BOT_TOKEN = 7931901384:AAERPZAarqhdvk49kAWVWid6tyCw8ai92dc
CHANNEL_ID = +-yRQgtkqCwMxYzEx
USGS_FEED = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson'
CHECK_INTERVAL = 60  # in seconds

# Myanmar Bounding Box
MYANMAR_BOUNDS = {
    "min_lat": 9,
    "max_lat": 29,
    "min_lon": 92,
    "max_lon": 101
}

sent_event_ids = set()
translator = Translator()
bot = Bot(token=BOT_TOKEN)

def is_in_myanmar(lat, lon):
    return (MYANMAR_BOUNDS["min_lat"] <= lat <= MYANMAR_BOUNDS["max_lat"] and
            MYANMAR_BOUNDS["min_lon"] <= lon <= MYANMAR_BOUNDS["max_lon"])

def translate_to_burmese(text):
    try:
        result = translator.translate(text, dest='my')
        return result.text
    except Exception as e:
        print("Translation failed:", e)
        return text  # fallback to English

def fetch_and_send():
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
                f"**Time:** {time_utc}\n"
                f"[More Info]({url})"
            )

            msg_mm = translate_to_burmese(msg_en)

            # Telegram expects MarkdownV2-style escaping
            bot.send_message(chat_id=CHANNEL_ID, text=msg_mm, parse_mode='Markdown')

            sent_event_ids.add(quake_id)

    except Exception as e:
        print("Error:", e)

# Looping to check every X seconds
if __name__ == '__main__':
    print("Bot started. Monitoring earthquakes in Myanmar...")
    while True:
        fetch_and_send()
        time.sleep(CHECK_INTERVAL)
