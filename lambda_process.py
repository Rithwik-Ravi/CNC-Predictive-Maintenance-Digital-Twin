"""
lambda_process.py - AWS Lambda function (process_telemetry)
Evaluates incoming CNC machine sensor telemetry, calculates failure probability
using a pre-trained logistic regression model, writes metrics to DynamoDB,
and sends an alert email via SNS if failure risk exceeds threshold.
"""

import os
import time
import json
import math
from decimal import Decimal
import boto3

# --- Pre-trained Logistic Regression Model Parameters ---
# Features order: temperature, vibration, rpm, current
MEAN = [
    62.94354889589906,
    2.7101293375394326,
    1478.4268138801262,
    12.874274447949526
]
SCALE = [
    6.024439305950324,
    1.4418101920708906,
    36.75394019873994,
    1.5078280053651663
]
COEF = [
    1.9919690678566517,
    2.1587823458903825,
    -1.6054621956100164,
    1.9630176576113105
]
INTERCEPT = -3.397768879935952

# --- Thresholds and Operational Configuration ---
WARN_THRESHOLD = 0.4
ALERT_THRESHOLD = 0.8
MACHINE_ID = "machine1"
ALERT_COOLDOWN_SECONDS = 600


def predict_probability(temperature, vibration, rpm, current):
    """
    Pure mathematical function to calculate failure probability.
    Does not require any AWS dependencies or external ML libraries.

    Formula:
        z = INTERCEPT + sum(coef * ((value - mean) / scale))
        probability = 1 / (1 + exp(-z))
    """
    features = [temperature, vibration, rpm, current]

    # Calculate standardized linear combination
    z = INTERCEPT
    for val, mean, scale, coef in zip(features, MEAN, SCALE, COEF):
        z += coef * ((val - mean) / scale)

    # Clamp z to range [-30, 30] to prevent math overflow/underflow in exp()
    z = max(-30.0, min(30.0, z))

    # Logistic sigmoid function
    probability = 1.0 / (1.0 + math.exp(-z))
    return probability


def lambda_handler(event, context):
    """
    AWS Lambda handler function.
    Triggered by AWS IoT Core rule with machine telemetry payload.
    """
    # Environment variables for AWS resources
    table_name = os.environ.get("TABLE_NAME")
    topic_arn = os.environ.get("TOPIC_ARN")

    # Parse payload if passed as JSON string
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except Exception as err:
            print(f"Error parsing event string as JSON: {err}")

    # Extract sensor readings from the event
    temperature = float(event.get("temperature", 0.0))
    vibration = float(event.get("vibration", 0.0))
    rpm = float(event.get("rpm", 0.0))
    current = float(event.get("current", 0.0))
    # Event timestamp is in milliseconds; default to current time in ms
    timestamp_ms = int(event.get("timestamp", int(time.time() * 1000)))

    # Compute failure probability
    probability = predict_probability(temperature, vibration, rpm, current)

    # Determine health status based on thresholds
    if probability < WARN_THRESHOLD:
        status = "NORMAL"
    elif probability < ALERT_THRESHOLD:
        status = "WARNING"
    else:
        status = "CRITICAL"

    print(
        f"Machine: {MACHINE_ID} | Probability: {probability:.4f} | Status: {status} "
        f"| Temp: {temperature}C | Vib: {vibration}mm/s | RPM: {rpm} | Curr: {current}A"
    )

    # Boto3 clients are instantiated inside the handler to prevent import-time AWS calls
    dynamodb = None
    table = None
    sns_client = None

    if table_name:
        try:
            dynamodb = boto3.resource("dynamodb")
            table = dynamodb.Table(table_name)
        except Exception as err:
            print(f"Error initializing DynamoDB resource: {err}")

    if topic_arn:
        try:
            sns_client = boto3.client("sns")
        except Exception as err:
            print(f"Error initializing SNS client: {err}")

    # 1. Store telemetry item into DynamoDB
    if table:
        try:
            # DynamoDB does not support native Python floats; convert floats to Decimal
            current_time_sec = int(time.time())
            ttl_value = current_time_sec + 86400  # Expire after 24 hours

            item = {
                "machine_id": MACHINE_ID,
                "timestamp": timestamp_ms,
                "temperature": Decimal(str(temperature)),
                "vibration": Decimal(str(vibration)),
                "rpm": Decimal(str(rpm)),
                "current": Decimal(str(current)),
                "failure_probability": Decimal(str(round(probability, 6))),
                "status": status,
                "ttl": ttl_value
            }
            table.put_item(Item=item)
            print("Successfully recorded telemetry to DynamoDB.")
        except Exception as err:
            # Catch AWS errors and log to CloudWatch without crashing
            print(f"Error putting item to DynamoDB: {err}")
    else:
        print("TABLE_NAME not configured; skipping DynamoDB telemetry write.")

    # 2. Alert logic: send email via SNS if probability exceeds ALERT_THRESHOLD with cooldown
    if probability > ALERT_THRESHOLD and topic_arn and sns_client and table:
        try:
            current_time_sec = time.time()
            alert_state_key = {
                "machine_id": f"{MACHINE_ID}_alert_state",
                "timestamp": 0
            }

            # Check previous alert time to enforce cooldown
            last_alert_time = 0.0
            alert_response = table.get_item(Key=alert_state_key)
            if "Item" in alert_response and "last_alert_time" in alert_response["Item"]:
                last_alert_time = float(alert_response["Item"]["last_alert_time"])

            time_since_last_alert = current_time_sec - last_alert_time

            if time_since_last_alert >= ALERT_COOLDOWN_SECONDS:
                subject = f"Maintenance alert: CNC Machine 1"
                message = (
                    f"CRITICAL MAINTENANCE ALERT\n"
                    f"Machine ID: {MACHINE_ID}\n\n"
                    f"Failure Probability: {probability * 100:.1f}%\n"
                    f"Vibration: {vibration} mm/s\n"
                    f"Temperature: {temperature} C\n"
                    f"RPM: {rpm}\n"
                    f"Current: {current} A\n\n"
                    f"Warning: Impending bearing failure detected. Please schedule maintenance."
                )

                sns_client.publish(
                    TopicArn=topic_arn,
                    Subject=subject,
                    Message=message
                )
                print("Alert notification sent via SNS.")

                # Update the alert state timestamp to reset the cooldown timer
                table.put_item(
                    Item={
                        "machine_id": f"{MACHINE_ID}_alert_state",
                        "timestamp": 0,
                        "last_alert_time": Decimal(str(int(current_time_sec)))
                    }
                )
                print("Alert cooldown state updated in DynamoDB.")
            else:
                remaining_cooldown = int(ALERT_COOLDOWN_SECONDS - time_since_last_alert)
                print(f"Alert throttled due to cooldown ({remaining_cooldown}s remaining).")
        except Exception as err:
            # Catch SNS and alert state DynamoDB errors without crashing
            print(f"Error handling SNS alert: {err}")
    elif probability > ALERT_THRESHOLD and not topic_arn:
        print("ALERT_THRESHOLD exceeded, but TOPIC_ARN is not set. Skipping SNS alert.")

    # Return summary dictionary
    return {
        "failure_probability": probability,
        "status": status
    }
