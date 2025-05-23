# ========== Standard Library ==========
import os
import json
import math
import signal
import asyncio
import logging
import traceback
from io import BytesIO
from datetime import datetime, timedelta, timezone as dt_timezone

# ========== Third-Party Libraries ==========
import boto3
import requests
import urllib3
import feedparser
from PIL import Image
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError
from matplotlib import pyplot as plt
from matplotlib.patches import Circle, Rectangle
from matplotlib import patheffects as path_effects, font_manager
from pytz import timezone, utc
from botocore.exceptions import ClientError

# ========== Local Modules ==========
from fbPost import post_image_to_facebook
from discord_logger import DiscordLogHandler
from save_quake import save_quake_to_dynamodb


# ============ Setup & Logging ============ #
load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QuakeBot")
#Discord Log Handling(Optional)
discord_handler = DiscordLogHandler()
discord_handler.setLevel(logging.INFO)
discord_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
discord_handler.setFormatter(discord_formatter)
logger.addHandler(discord_handler)

# ============ Configurations ============ #
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
CITIES_JSON = "myanmar_cities.json"
CHECK_INTERVAL = 60
#LAST_EVENT_FILE = "last_quake_text.txt"
FONT = font_manager.FontProperties(family="Arial Unicode MS") 
BURMESE_DIGITS = "၀၁၂၃၄၅၆၇၈၉"

# ============ AWS DynamoDB Setup ============ #
region = os.getenv("AWS_REGION", "us-west-1")
dynamodb = boto3.resource('dynamodb', region_name=region)
table = dynamodb.Table('QuakeLogs_Test')

# ============ Utility Functions ============ #
def quake_exists_in_db(quake_id):
    try:
        response = table.get_item(Key={'quake_id': quake_id})
        return 'Item' in response
    except ClientError as e:
        logger.error(f"Error checking quake ID: {e.response['Error']['Message']}")
        return False
    
def get_pacific_time_str():
    pacific = timezone('US/Pacific')
    return datetime.now(pacific).strftime("%H:%M")
#Load City Json
with open(CITIES_JSON, 'r', encoding='utf-8') as f:
    CITY_DATA = json.load(f)

def burmese_number(number):
    return ''.join(BURMESE_DIGITS[int(d)] if d.isdigit() else d for d in str(number))

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def find_nearest_city(lat, lon):
    nearest = None
    min_dist = float('inf')
    for city in CITY_DATA:
        try:
            city_lat = float(city['lat'])
            city_lon = float(city['lng'])
            dist = haversine(lat, lon, city_lat, city_lon)
            if dist < min_dist:
                min_dist = dist
                nearest = city
                nearest['distance'] = round(dist * 0.621371)
        except (KeyError, ValueError):
            continue
    return nearest

def convert_utc_to_myanmar(utc_str):
    clean_str = utc_str.replace("UTC", "").strip()
    formats_to_try = ["%Y-%m-%d %H:%M:%S"]
    for fmt in formats_to_try:
        try:
            dt_utc = datetime.strptime(clean_str, fmt)
            dt_mm = dt_utc + timedelta(hours=6, minutes=30)
            hour_24 = int(dt_mm.strftime("%H"))
            minute = dt_mm.strftime("%M")
            second = dt_mm.strftime("%S")
            if 1 <= hour_24 <= 10:
                tod = "မနက်"
            elif 11 <= hour_24 <= 15:
                tod = "နေ့လည်"
            elif 16 <= hour_24 <= 18:
                tod = "ညနေ"
            else:
                tod = "ည"
            time_clocks = {1: "🕐", 2: "🕑", 3: "🕒", 4: "🕓", 5: "🕔", 6: "🕕",
                           7: "🕖", 8: "🕗", 9: "🕘", 10: "🕙", 11: "🕚", 12: "🕛"}
            hour_12 = int(dt_mm.strftime("%I"))
            clock_emoji = time_clocks.get(hour_12, "🕓")
            return f"{clock_emoji} {tod} {burmese_number(hour_12)}နာရီ {burmese_number(minute)}မိနစ် {burmese_number(second)}စက္ကန့်"
        except ValueError:
            continue
    logger.error(f"Could not parse UTC time string: {utc_str}")
    return None

# ============ Fetch & Filter Quakes ============ #
def fetch_quakes_from_rss():
    feed = feedparser.parse("https://earthquake.tmd.go.th/feed/rss_tmd.xml")
    new_quakes = []

    for entry in feed.entries:
        try:
            quake_id = entry.link.split("earthquake=")[-1]
            if quake_exists_in_db(quake_id):
                continue

            lat = float(entry.get("geo_lat", 0.0))
            lon = float(entry.get("geo_long", 0.0))
            mag = float(entry.get("tmd_magnitude", 0.0))
            depth = float(entry.get("tmd_depth", 0.0))
            utc_time = entry.get("tmd_time", "")
            link = entry.link

            if mag < 2.0:
                save_quake_to_dynamodb(quake_id, mag, utc_time, depth, lat, lon, "ignored")
                logger.info(f"🟢 Magnitude {mag} earthquake ignored. ({get_pacific_time_str()})")
                continue

            is_myanmar = "เมียนมา" in entry.title or "Myanmar" in entry.title

            if not is_myanmar and mag < 3.0:
                save_quake_to_dynamodb(quake_id, mag, utc_time, depth, lat, lon, "Telegram ignored")
                logger.info(f"🟢 Small quake outside Myanmar ignored. ({get_pacific_time_str()})")
                continue

            logger.info(f"🔔 Magnitude {mag} earthquake detected at ({get_pacific_time_str()}).Initiating Alerts.")

            new_quakes.append({
                "id": quake_id,
                "lat": lat,
                "lon": lon,
                "mag": mag,
                "depth": depth,
                "date": utc_time,
                "link": link
            })

        except Exception as e:
            logger.warning(f"Error parsing RSS entry: {e}")
            continue

    return list(reversed(new_quakes))

def build_facebook_caption(fbemoji, mag, city_mm, distance_miles, mm_time, depth_km, lat, lon, link):
    return (
        f"{fbemoji}ပြင်းအား{burmese_number(mag)}အဆင့်ရှိငလျင် {city_mm}အနီးလှုပ်ခတ်သွား\n\n"
        f"🛰️ ဒီ Page က မြန်မာပြည်နဲ့ အိမ်နီးချင်းနိုင်ငံ​တွေရဲ့ ငလျင်ဌာန​တွေနဲ့ပူး​ပေါင်းပြီး မြန်မာပြည်သူ​တွေ ငလျင်အချက်အလက်​တွေ အချိန်နဲ့တစ်​ပြေးညီသိရအောင်တင်ပေးတာမို့လို့ Like👍 နဲ့ Follow✅လုပ်ထားပေးပါ\n\n"
        f"ငလျင် Telegram ➤ https://t.me/myanmar_earthquake_alert\n"
        f"အင်အား : {burmese_number(mag)}\n"
        f"နေရာ : {city_mm}မှ {distance_miles}မိုင်ခန့်အကွာ\n"
        f"လှုပ်ခတ်ချိန် : {mm_time}\n"
        f"အနက် : {burmese_number(depth_km)} ကီလိုမီတာ\n"
        f"ဗဟိုမှတ်: Latitude {lat} | Longitude {lon}\n"
        f"မြေပုံအသေးစိပ်ကြည့်ရှရန် : https://www.google.com/maps?q={lat},{lon}"
    )

# ============ Broadcasted ID File Helpers ============ #
def load_broadcasted_ids():
    if not os.path.exists("broadcasted_quakes.txt"):
        return set()
    with open("broadcasted_quakes.txt", "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def save_broadcasted_id(quake_id):
    with open("broadcasted_quakes.txt", "a", encoding="utf-8") as f:
        f.write(f"{quake_id}\n")

def save_last_quake_id(quake_id):
    with open("last_quake_text.txt", "w", encoding="utf-8") as f:
        f.write(quake_id)

def save_ignored_quake_id(quake_id):
    with open("ignored_quakes.txt", "a", encoding="utf-8") as f:
        f.write(f"{quake_id}\n")

def load_ignored_quake_ids():
    if not os.path.exists("ignored_quakes.txt"):
        return set()
    with open("ignored_quakes.txt", "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

#============== Map Generation ==================#
def generate_map(lat, lon, output_file, mag=5.0, depth=10, utc_time=""):
    from datetime import datetime
    from pytz import timezone, utc
    import matplotlib.patheffects as path_effects
    from matplotlib.patches import Rectangle

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    size = 600
    zoom = 9

    map_url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        "center": f"{lat},{lon}",
        "zoom": str(zoom),
        "size": f"{size}x{size}",
        "maptype": "hybrid",   # Satellite + City labels + Roads
        "tilt":"45",
        "heading": "90",
        "scale": 2,
        "key": api_key
    }

    try:
        response = requests.get(map_url, params=params)
        map_image = Image.open(BytesIO(response.content))

        try:
            dt_utc = datetime.strptime(utc_time.replace("UTC", "").strip(), "%Y-%m-%d %H:%M:%S")
            dt_utc = utc.localize(dt_utc)
            dt_mm = dt_utc.astimezone(timezone("Asia/Yangon"))
        except Exception:
            logger.warning(f"Invalid UTC time format: '{utc_time}'. Using current UTC time.")
            dt_mm = datetime.now(timezone.utc).replace(tzinfo=utc).astimezone(timezone("Asia/Yangon"))

        time_str = dt_mm.strftime("%I:%M %p").upper()
        date_str = dt_mm.strftime("%d/%m/%Y").upper()
        emoji = "⚠️⚠️" if mag > 3.9 else " "
        mag_str = f"{emoji} {mag:.1f} MAGNITUDE {emoji}"
        footer = "FOLLOW US ON FACEBOOK AND TELEGRAM FOR LATEST EARTHQUAKE ALERTS"

        fig, ax = plt.subplots(figsize=(6, 6), dpi=100)
        ax.imshow(map_image)
        ax.axis('off')

        # Shockwave circles - softer color
        ax.plot(size, size, 'o', color='red', markersize=8)
        base_radius = int(mag * 20 + depth * 0.5)
        for i, r in enumerate([base_radius, base_radius + 40, base_radius + 80, base_radius + 120]):
            ax.add_patch(Circle((size, size), r, edgecolor='red', fill=False, linewidth=6, alpha=0.5 - i * 0.1))

        # Earthquake alert header
        t = ax.text(0.5, 0.92, "EARTHQUAKE ALERT!", fontsize=30, fontweight='bold', color='red',
                    ha='center', va='center', transform=ax.transAxes, zorder=3)
        t.set_path_effects([path_effects.Stroke(linewidth=3, foreground='white'), path_effects.Normal()])

        # Date
        t = ax.text(0.5, 0.09, date_str, fontsize=12, fontweight='bold', color='white',
                ha='center', va='center', transform=ax.transAxes)
        t.set_path_effects([path_effects.Stroke(linewidth=2, foreground='black'), path_effects.Normal()])

        # Time
        t = ax.text(0.5, 0.14, time_str, fontsize=12, fontweight='bold', color='white',
                ha='center', va='center', transform=ax.transAxes)
        t.set_path_effects([path_effects.Stroke(linewidth=2, foreground='black'), path_effects.Normal()])

        # Magnitude
        t = ax.text(0.5, 0.20, mag_str, fontsize=23, fontweight='bold', color='red',
            ha='center', va='center', transform=ax.transAxes)
        t.set_path_effects([path_effects.Stroke(linewidth=2, foreground='white'), path_effects.Normal()])

        # Footer (bottom bar)
        ax.add_patch(Rectangle(
            (0, 0), 1, 0.04, transform=ax.transAxes,
            color='red', zorder=2
        ))
        ax.text(0.5, 0.02, footer, fontsize=9, fontweight='bold', color='white',
            ha='center', va='center', transform=ax.transAxes, zorder=3)

        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
        plt.savefig(output_file, format='png', dpi=100, bbox_inches='tight', pad_inches=0)
        plt.close()
        logger.info("✅ Quake Map rendered Successfully.")
    except Exception as e:
        logger.error(f"Error generating shockwave map: {e}")


def write_status(status: str):
    with open("status.json", "w") as f:
        json.dump({"status": status, "time": datetime.now(dt_timezone.utc).isoformat()}, f)

async def send_alert(bot, quake):
    lat = quake["lat"]
    lon = quake["lon"]
    mag = quake["mag"]
    utc_time = quake["date"]
    depth_km = quake["depth"]
    quake_id = quake["id"]
    link = quake["link"]
    mm_time = convert_utc_to_myanmar(utc_time)
    nearest = find_nearest_city(lat, lon)
    city_mm = nearest['city_mm'] if nearest else "မသိရ"
    distance_miles = burmese_number(nearest['distance']) if nearest and 'distance' in nearest else "?"
    fbemoji = "🚨" if mag >= 4.0 else "⚠️"

    if mag >= 6.0:
        emoji = "🔴🚨"
    elif mag >= 5.0:
        emoji = "🟠⚠️"
    elif mag >= 4.0:
        emoji = "🟡"
    else:
        emoji = "🟢"

    image_path = "quake_map.png"
    generate_map(lat, lon, image_path, mag, depth_km, utc_time)
    if not os.path.exists(image_path):
        logger.error("Generated map is missing.")
        return
    #Post to Facebook
    fb_caption = build_facebook_caption(fbemoji, mag, city_mm, distance_miles, mm_time, depth_km, lat, lon, link)
    page_id, post_id = post_image_to_facebook(image_path, fb_caption)
    if not page_id or not post_id:
        logger.error("Failed to get Facebook post link.")
        return
    fb_post_url = f"https://www.facebook.com/{page_id}/posts/{post_id}"

    if mag < 3.0:
        logger.info(f"Skipped Telegram due to magnitude {mag} < 3.0.")
        return
    #Post to Telegram if magnitude > 3.0
    telegram_caption = (
        f"{emoji} အင်အား {burmese_number(mag)} အဆင့်\n"
        f"📍 {city_mm}မှ {distance_miles} မိုင်ခန့်အကွာ\n"
        f"{mm_time}\n\n"
        f"[👉 အသေးစိပ်ဖတ်ရှုရန်]({fb_post_url})"
    )

    try:
        await bot.send_photo(chat_id=CHANNEL_ID, photo=open(image_path, 'rb'), caption=telegram_caption, parse_mode='Markdown')
        logger.info("Alerts successfully sent to all platforms....")
    except TelegramError as e:
        logger.error(f"Telegram error: {e}")

# ============ Main Loop ============ #
async def monitor_loop():
    bot = Bot(token=TOKEN)
    logger.info(f"QuakeBot: Bot started at ({get_pacific_time_str()}). Monitoring every 60s.")

    while True:
        found_new_quake = False  # Track if new quakes are found

        new_quakes = fetch_quakes_from_rss()

        if new_quakes:
            for quake in new_quakes:
                saved = save_quake_to_dynamodb(
                    quake["id"],
                    quake["mag"],
                    quake["date"],
                    quake["depth"],
                    quake["lat"],
                    quake["lon"],
                    "Alerted"
                )
                if saved:
                    found_new_quake = True
                    await send_alert(bot, quake)
                    await asyncio.sleep(2)

        if not found_new_quake:
            logger.info(f"No earthquake detected at ({get_pacific_time_str()}). Waiting for the next check...")

        write_status("healthy")  # ✅ Update heartbeat
        await asyncio.sleep(CHECK_INTERVAL)



if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown_handler(sig, frame):
        logger.info("Shutdown signal received. Stopping bot...")
        loop.stop()

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    try:
        loop.run_until_complete(monitor_loop())
    except Exception as e:
        error = traceback.format_exc()
        logger.critical(f"Unhandled exception in monitor_loop: {error}")
        with open("latest_error.log", "w", encoding="utf-8") as f:
            f.write(error)
    finally:    
        loop.close()
