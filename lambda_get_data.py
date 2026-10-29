"""
lambda_get_data.py - AWS Lambda function (get_data)
Retrieves the most recent 60 telemetry readings for machine1 from DynamoDB,
formats numbers, and returns them oldest-first for dashboard time-series plotting.
Designed for AWS Lambda Function URLs.
"""

import os
import time
import json
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key


def decimal_to_number(obj):
    """
    Recursively converts DynamoDB Decimal objects to standard Python int or float
    so that data can be serialized to JSON.
    """
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, dict):
        return {k: decimal_to_number(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimal_to_number(item) for item in obj]
    return obj


def lambda_handler(event, context):
    """
    Lambda handler for Function URL requests.
    Queries DynamoDB table for recent machine telemetry.
    """
    # 1. Read DynamoDB table name from environment variables
    table_name = os.environ.get("TABLE_NAME")
    if not table_name:
        err_msg = "TABLE_NAME environment variable is not configured."
        print(f"Configuration Error: {err_msg}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": err_msg})
        }

    try:
        # 2. Connect to DynamoDB resource and get table reference
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(table_name)

        # 3. Query the latest 60 items for machine1 (newest first)
        response = table.query(
            KeyConditionExpression=Key("machine_id").eq("machine1"),
            ScanIndexForward=False,  # Descending order (newest first)
            Limit=60                 # Fetch at most 60 recent data points
        )

        raw_items = response.get("Items", [])

        # 4. Convert Decimal values to native int/float for JSON serialization
        converted_items = decimal_to_number(raw_items)

        # 5. Reverse the list so items are ordered chronologically (oldest first)
        # This makes plotting charts on dashboards straightforward
        chronological_items = list(reversed(converted_items))

        # Current Unix timestamp in milliseconds
        current_time_ms = int(time.time() * 1000)

        # 6. Construct response in Lambda Function URL format
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "items": chronological_items,
                "server_time": current_time_ms
            })
        }

    except Exception as err:
        # Print error details to CloudWatch Logs and return HTTP 500
        print(f"Error querying telemetry data from DynamoDB: {err}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "error": "Failed to fetch telemetry data",
                "details": str(err)
            })
        }
