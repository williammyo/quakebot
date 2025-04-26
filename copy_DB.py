import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# AWS settings
region = "us-west-1"  # Change if needed
dynamodb = boto3.resource('dynamodb', region_name=region)

# Table names
source_table_name = "QuakeLogs_Test"
destination_table_name = "EarthquakeLogs"

# Connect to both tables
source_table = dynamodb.Table(source_table_name)
destination_table = dynamodb.Table(destination_table_name)

# Scan all items from source table
response = source_table.scan()
items = response['Items']

# Batch writer for destination table
with destination_table.batch_writer(overwrite_by_pkeys=['quake_id']) as batch:
    for item in items:
        # Reformat Decimal types if needed
        for key, value in item.items():
            if isinstance(value, float):
                item[key] = Decimal(str(value))
        batch.put_item(Item=item)

print(f"✅ Successfully copied {len(items)} earthquake records to {destination_table_name}")
