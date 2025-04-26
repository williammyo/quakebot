import boto3
from datetime import datetime, timedelta
from decimal import Decimal
import logging

# Setup logger
logger = logging.getLogger("SaveQuake")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Load environment variables or set default region
import os
region = os.getenv("AWS_REGION", "us-west-1")
dynamodb = boto3.resource('dynamodb', region_name=region)
table_name = os.getenv("DYNAMODB_TABLE", "QuakeLogs_Test")
table = dynamodb.Table(table_name)

def save_quake_to_dynamodb(quake_id, magnitude, utc_datetime, depth, lat, lon, status):
    try:
        # Remove 'UTC' if it exists
        clean_utc_datetime = utc_datetime.replace('UTC', '').strip()
        
        # Parse UTC time with correct format
        dt_utc = datetime.strptime(clean_utc_datetime, "%Y-%m-%d %H:%M:%S")
        
        # Convert to Myanmar Time (+6:30)
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
    # Simple test case
    save_quake_to_dynamodb(
        quake_id="testquake001",
        magnitude=5.5,
        utc_datetime="2025-04-25T12:00:00",
        depth=10.0,
        lat=16.8,
        lon=96.1,
        status="alerted"
    )
