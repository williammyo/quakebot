import boto3
from datetime import datetime, timedelta, timezone as dt_timezone 
from decimal import Decimal
import logging
import os

# Setup logger for this module
logger = logging.getLogger("SaveQuake")
logger.setLevel(logging.INFO) # Or DEBUG for more verbosity
# Avoid adding handlers if they are already configured by a root logger or another module
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# AWS DynamoDB Setup
AWS_REGION = os.getenv("AWS_REGION", "us-west-1")
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE", "QuakeLogs_Test")

try:
    dynamodb_resource = boto3.resource('dynamodb', region_name=AWS_REGION)
    table = dynamodb_resource.Table(DYNAMODB_TABLE_NAME)
    logger.info(f"Successfully connected to DynamoDB table: {DYNAMODB_TABLE_NAME} in region {AWS_REGION}")
except Exception as e:
    logger.critical(f"Failed to connect to DynamoDB table {DYNAMODB_TABLE_NAME}: {e}", exc_info=True)
    # Depending on the application, you might want to exit or raise the exception
    # For this script, we'll let it try to run, but operations will fail.
    table = None 


def save_quake_to_dynamodb(quake_id, magnitude, utc_datetime_str, depth, lat, lon, status):
    """
    Saves earthquake data to DynamoDB if it doesn't already exist.
    Returns True if successfully saved, False otherwise.
    """
    if table is None:
        logger.error(f"DynamoDB table not initialized. Cannot save quake {quake_id}.")
        return False
        
    try:
        # Clean and parse UTC datetime string
        clean_utc_datetime_str = utc_datetime_str.replace('UTC', '').strip()
        # Attempt to parse with common formats
        dt_utc_obj = None
        possible_formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"] # Add more if needed
        for fmt in possible_formats:
            try:
                dt_utc_obj = datetime.strptime(clean_utc_datetime_str, fmt)
                break
            except ValueError:
                continue
        
        if dt_utc_obj is None:
            logger.error(f"Could not parse UTC datetime string '{utc_datetime_str}' for quake {quake_id}.")
            # Fallback: use current UTC time, or decide how to handle unparseable dates
            # For now, we'll prevent saving if the date is crucial and unparseable.
            return False

        # Ensure dt_utc_obj is timezone-aware (UTC)
        dt_utc_obj = dt_utc_obj.replace(tzinfo=dt_timezone.utc)

        # Convert to Myanmar Time (+6:30) for storage/display if needed
        mm_timezone = dt_timezone(timedelta(hours=6, minutes=30))
        mm_datetime_obj = dt_utc_obj.astimezone(mm_timezone)
        
        # Format times for DynamoDB storage (ISO 8601 T format is good)
        utc_time_iso = dt_utc_obj.isoformat()
        mm_time_iso = mm_datetime_obj.isoformat()

        item_to_save = {
            'quake_id': str(quake_id), # Ensure quake_id is string
            'magnitude': Decimal(str(magnitude)),
            'utc_time_original_str': utc_datetime_str, # Store the original string for reference
            'utc_time_iso': utc_time_iso,
            'mm_time_iso': mm_time_iso,
            'depth': Decimal(str(depth)),
            'latitude': Decimal(str(lat)),
            'longitude': Decimal(str(lon)),
            'status': str(status),
            'last_updated': datetime.now(dt_timezone.utc).isoformat() # Track last update
        }
        
        table.put_item(
            Item=item_to_save,
            ConditionExpression='attribute_not_exists(quake_id)' # Only save if quake_id is new
        )
        
        # Log success based on status
        if status == "Alerted":
            logger.info(f"✅ Quake {quake_id} (Status: {status}) saved successfully to DynamoDB.")
        elif status in ["ignored", "Telegram ignored"]:
            logger.info(f"✅ Quake {quake_id} (Status: {status}) recorded in DynamoDB.")
        else:
            logger.info(f"✅ Quake {quake_id} (Status: {status}) processed and saved to DynamoDB.")
        return True

    except dynamodb_resource.meta.client.exceptions.ConditionalCheckFailedException:
        # This means the quake_id already exists.
        logger.warning(f"⚠️ Quake {quake_id} already exists in DynamoDB. Skipping save with status '{status}'.")
        # You could add logic here to update the item if the status is different and an update is desired.
        # For example, if it was "ignored" and now it's "Alerted", you might want to update.
        # This would require changing ConditionExpression or using update_item.
        return False
    except ValueError as ve: # Catch Decimal conversion errors or other value errors
        logger.error(f"❌ Value error processing data for quake {quake_id}: {ve}. Data: mag={magnitude}, depth={depth}, lat={lat}, lon={lon}")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to save quake {quake_id} with status '{status}' to DynamoDB: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    logger.info("Running test case for save_quake_to_dynamodb...")
    
    # Test case 1: New quake
    test_id_1 = f"testquake_new_{int(datetime.now().timestamp())}"
    logger.info(f"Attempting to save new quake: {test_id_1}")
    success1 = save_quake_to_dynamodb(
        quake_id=test_id_1,
        magnitude=5.5,
        utc_datetime_str="2025-04-25 12:00:00 UTC", # Example with UTC
        depth=10.0,
        lat=16.8,
        lon=96.1,
        status="Alerted"
    )
    logger.info(f"Test 1 (new quake) success: {success1}")

    # Test case 2: Existing quake (attempt to save again)
    if success1: # Only try to re-save if the first save was successful
        logger.info(f"Attempting to save existing quake again: {test_id_1}")
        success2 = save_quake_to_dynamodb(
            quake_id=test_id_1, # Same ID
            magnitude=5.6, # Different magnitude to see if it overwrites (it shouldn't due to condition)
            utc_datetime_str="2025-04-25 12:05:00",
            depth=12.0,
            lat=16.9,
            lon=96.2,
            status="Alerted"
        )
        logger.info(f"Test 2 (existing quake) success: {success2} (should be False or log warning)")

    # Test case 3: Quake with slightly different time format
    test_id_3 = f"testquake_timefmt_{int(datetime.now().timestamp())}"
    logger.info(f"Attempting to save quake with T in datetime: {test_id_3}")
    success3 = save_quake_to_dynamodb(
        quake_id=test_id_3,
        magnitude=4.0,
        utc_datetime_str="2025-04-26T08:30:00", # ISO-like format without Z
        depth=20.0,
        lat=17.0,
        lon=95.5,
        status="ignored"
    )
    logger.info(f"Test 3 (time format) success: {success3}")

    # Test case 4: Invalid data (e.g., non-numeric magnitude)
    test_id_4 = f"testquake_invalid_data_{int(datetime.now().timestamp())}"
    logger.info(f"Attempting to save quake with invalid magnitude type: {test_id_4}")
    success4 = save_quake_to_dynamodb(
        quake_id=test_id_4,
        magnitude="strong", # Invalid
        utc_datetime_str="2025-04-27T10:00:00",
        depth=5.0,
        lat=18.0,
        lon=97.0,
        status="Alerted"
    )
    logger.info(f"Test 4 (invalid data) success: {success4} (should be False and log error)")
