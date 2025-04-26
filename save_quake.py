import boto3
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import os

# Setup logger
logger = logging.getLogger("SaveQuake")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# AWS config
region = os.getenv("AWS_REGION", "us-west-1")
dynamodb = boto3.resource("dynamodb", region_name=region)
table_name = os.getenv("DYNAMODB_TABLE", "EarthquakeLogs")
table = dynamodb.Table(table_name)

def parse_utc_datetime(utc_str):
    """Parses a UTC datetime string into a datetime object."""
    clean_str = utc_str.replace("UTC", "").strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(clean_str, fmt)
        except ValueError:
            continue
    logger.error(f"❌ Could not parse UTC time string: {utc_str}")
    return None

def save_quake_to_dynamodb(quake_id, magnitude, utc_datetime_str, depth, lat, lon, status):
    dt_utc = parse_utc_datetime(utc_datetime_str)
    if dt_utc is None:
        logger.error(f"❌ Skipping save for quake {quake_id}: Invalid UTC time format")
        return False

    mm_time = (dt_utc + timedelta(hours=6, minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")
    try:
        table.put_item(
            Item={
                "quake_id": quake_id,
                "magnitude": Decimal(str(magnitude)),
                "utc_time": dt_utc.strftime("%Y-%m-%dT%H:%M:%S"),
                "mm_time": mm_time,
                "depth": Decimal(str(depth)),
                "latitude": Decimal(str(lat)),
                "longitude": Decimal(str(lon)),
                "status": status,
            },
            ConditionExpression="attribute_not_exists(quake_id)"
        )
        logger.info(f"✅ Quake {quake_id} saved successfully to DynamoDB.")
        return True

    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        logger.warning(f"⚠️ Quake {quake_id} already exists. Skipping.")
        return False

    except Exception as e:
        logger.error(f"❌ Failed to save quake {quake_id}: {e}")
        return False

# === Optional: Run test directly ===
if __name__ == "__main__":
    test_data = [
        {
            "quake_id": "testquake001",
            "magnitude": 5.5,
            "utc_datetime_str": "2025-04-25T12:00:00",
            "depth": 10.0,
            "lat": 16.8,
            "lon": 96.1,
            "status": "alerted"
        },
        {
            "quake_id": "testquake002",
            "magnitude": 4.0,
            "utc_datetime_str": "2025-04-25 13:00:00",
            "depth": 50.0,
            "lat": 17.0,
            "lon": 97.0,
            "status": "alerted"
        }
    ]
    for quake in test_data:
        save_quake_to_dynamodb(**quake)
