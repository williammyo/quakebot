import boto3
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import os # Added os import

# Setup logger
logger = logging.getLogger("SaveQuake")
logger.setLevel(logging.INFO)
# Prevent adding handlers multiple times if imported elsewhere
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# Load environment variables or set default region
# Ensure environment variables are loaded if using .env file
# from dotenv import load_dotenv # Uncomment if you need this here too, though usually handled in main
# load_dotenv() # Uncomment if you need this here too

region = os.getenv("AWS_REGION", "us-west-1")
dynamodb = boto3.resource('dynamodb', region_name=region)
table_name = os.getenv("DYNAMODB_TABLE", "EarthquakeLogs") # Corrected table name to match main.py default/env
table = dynamodb.Table(table_name)

def parse_utc_datetime(utc_str):
    """Parses a UTC datetime string trying multiple formats."""
    clean_utc_datetime = utc_str.replace('UTC', '').strip()
    formats_to_try = [
        "%Y-%m-%d %H:%M:%S", # Format with space
        "%Y-%m-%dT%H:%M:%S", # Format with 'T' (ISO 8601)
        "%Y-%m-%d %H:%M:%S.%f", # Format with microseconds (if needed)
        "%Y-%m-%dT%H:%M:%S.%f" # Format with 'T' and microseconds
    ]
    for fmt in formats_to_try:
        try:
            # Use the correct format string
            dt_utc = datetime.strptime(clean_utc_datetime, fmt)
            return dt_utc
        except ValueError:
            continue # Try the next format

    logger.error(f"Could not parse UTC time string: {utc_utc_datetime}") # Corrected variable name
    return None


def save_quake_to_dynamodb(quake_id, magnitude, utc_datetime_str, depth, lat, lon, status):
    # Changed parameter name to avoid confusion with datetime object
    dt_utc = parse_utc_datetime(utc_datetime_str)

    if dt_utc is None:
        logger.error(f"❌ Skipping save for quake {quake_id}: Could not parse UTC time '{utc_datetime_str}'")
        return # Exit function if parsing failed

    try:
        # Convert to Myanmar Time (+6:30) from the parsed datetime object
        mm_datetime = (dt_utc + timedelta(hours=6, minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")

        # Save to DynamoDB
        table.put_item(
            Item={
                'quake_id': quake_id,
                'magnitude': Decimal(str(magnitude)),
                'utc_time': dt_utc.strftime("%Y-%m-%dT%H:%M:%S"),  # Save UTC in correct T format
                'mm_time': mm_datetime,
                'depth': Decimal(str(depth)),
                'latitude': Decimal(str(lat)),
                'longitude': Decimal(str(lon)),
                'status': status
            },
            ConditionExpression='attribute_not_exists(quake_id)'
        )
        logger.info(f"✅ Quake {quake_id} saved successfully to DynamoDB.")
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        logger.warning(f"⚠️ Quake {quake_id} already exists. Skipping.")
    except Exception as e:
        logger.error(f"❌ Failed to save quake {quake_id}: {str(e)}")


if __name__ == "__main__":
    # Simple test case with 'T' format
    save_quake_to_dynamodb(
        quake_id="testquake001",
        magnitude=Decimal('5.5'), # Use Decimal for magnitude in test too
        utc_datetime_str="2025-04-25T12:00:00", # Test with 'T'
        depth=Decimal('10.0'), # Use Decimal for depth in test too
        lat=Decimal('16.8'),   # Use Decimal for lat in test too
        lon=Decimal('96.1'),   # Use Decimal for lon in test too
        status="alerted"
    )
    # Another test case with space format (if applicable)
    save_quake_to_dynamodb(
        quake_id="testquake002",
        magnitude=Decimal('4.0'),
        utc_datetime_str="2025-04-25 13:00:00", # Test with space
        depth=Decimal('50.0'),
        lat=Decimal('17.0'),
        lon=Decimal('97.0'),
        status="alerted"
    )