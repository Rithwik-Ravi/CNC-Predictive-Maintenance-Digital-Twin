"""
CNC Machine IoT Simulator for AWS IoT Core
Simulates sensor telemetry from a CNC machine across healthy and degrading states,
publishing JSON messages over MQTT (mutual TLS) and logging data to a CSV file.
"""

import os
import time
import json
import random
import csv
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

# --- Configuration Constants ---
ENDPOINT = "a3ghzmcyr4pmfq-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = f"cnc-machine-1-{random.randint(1000, 9999)}"
TOPIC = "factory/machine1/telemetry"
PORT = 8883

# Mutual TLS Certificate files (located in the certs folder)
ROOT_CA = "certs/AmazonRootCA1.pem"
PRIVATE_KEY = "certs/private.pem.key"
CERTIFICATE = "certs/device.pem.crt"

# Local CSV file for logging sensor data
CSV_FILE = "sensor_log.csv"

# Machine lifecycle parameters
HEALTHY_STEPS = 150       # 150 steps @ 2s each = 300s (5 minutes) of healthy operation
DEGRADATION_STEPS = 100   # 100 steps of progressive degradation (failing bearing)
TOTAL_CYCLE_STEPS = HEALTHY_STEPS + DEGRADATION_STEPS  # 250 steps total per cycle


# Base directory of the script for robust path resolution
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def get_path(relative_path):
    """Resolves path relative to the script directory or current working directory."""
    if os.path.exists(relative_path):
        return os.path.abspath(relative_path)
    combined = os.path.join(BASE_DIR, relative_path)
    return combined


def main():
    root_ca_path = get_path(ROOT_CA)
    private_key_path = get_path(PRIVATE_KEY)
    certificate_path = get_path(CERTIFICATE)

    # Pre-flight check: ensure certificate files exist before connecting
    required_files = [
        ("Root CA Certificate", root_ca_path, "AmazonRootCA1.pem"),
        ("Private Key", private_key_path, "private.pem.key"),
        ("Device Certificate", certificate_path, "device.pem.crt"),
    ]
    for name, path, expected_name in required_files:
        if not os.path.exists(path):
            print(f"Error: {name} not found at '{path}'!")
            print(f"Make sure you place '{expected_name}' inside the 'certs' folder.")
            return

    # 1. Initialize the AWS IoT MQTT Client
    mqtt_client = AWSIoTMQTTClient(CLIENT_ID)
    mqtt_client.configureEndpoint(ENDPOINT, PORT)
    mqtt_client.configureCredentials(root_ca_path, private_key_path, certificate_path)

    # Configure connection settings for reliability
    mqtt_client.configureAutoReconnectBackoffTime(1, 32, 20)
    mqtt_client.configureOfflinePublishQueueing(-1)  # Infinite offline queueing
    mqtt_client.configureDrainingFrequency(2)         # Draining rate: 2 Hz
    mqtt_client.configureConnectDisconnectTimeout(10) # 10 seconds timeout
    mqtt_client.configureMQTTOperationTimeout(5)      # 5 seconds timeout

    # 2. Connect to AWS IoT Core
    mqtt_client.onOnline = lambda: print("[MQTT] ONLINE")
    mqtt_client.onOffline = lambda: print("[MQTT] OFFLINE")
    mqtt_client.connect()
    print("Connected to AWS IoT Core")

    # 3. Check if CSV file already exists and has content (to avoid duplicate headers)
    csv_file_path = get_path(CSV_FILE)
    file_exists = os.path.exists(csv_file_path) and os.path.getsize(csv_file_path) > 0

    # Open CSV in append mode ('a') so existing data is preserved
    with open(csv_file_path, mode="a", newline="", encoding="utf-8") as csv_file:
        csv_writer = csv.writer(csv_file)

        # Write header only if creating a new or empty file
        if not file_exists:
            csv_writer.writerow(["timestamp", "temperature", "vibration", "rpm", "current", "label"])
            csv_file.flush()

        step = 0

        # 4. Main simulation loop
        try:
            while True:
                # Calculate current position in the repeating 250-step cycle
                step_in_cycle = step % TOTAL_CYCLE_STEPS

                # Calculate progress: 0 while healthy, rises linearly from 0 to 1 during degradation
                if step_in_cycle < HEALTHY_STEPS:
                    progress = 0.0
                else:
                    # Degradation step count (1 to 100)
                    degradation_step = step_in_cycle - HEALTHY_STEPS + 1
                    progress = degradation_step / float(DEGRADATION_STEPS)

                # Generate sensor readings according to physical model formulas + Gaussian noise
                temperature = round(60.0 + 25.0 * (progress ** 2) + random.gauss(0, 0.8), 2)
                vibration = round(2.0 + 6.0 * (progress ** 2) + random.gauss(0, 0.15), 3)
                rpm = round(1500.0 - 120.0 * progress + random.gauss(0, 10.0), 1)
                current = round(12.0 + 5.0 * progress + random.gauss(0, 0.3), 2)

                # Timestamp in milliseconds (Unix time)
                timestamp = int(time.time() * 1000)

                # Label is 1 when failure is approaching (progress > 0.4), otherwise 0
                label = 1 if progress > 0.4 else 0

                # Construct flat JSON message (all values are numbers)
                payload_data = {
                    "temperature": temperature,
                    "vibration": vibration,
                    "rpm": rpm,
                    "current": current,
                    "timestamp": timestamp
                }
                payload_json = json.dumps(payload_data)

                # Publish to AWS IoT Core topic with QoS 0
                mqtt_client.publish(TOPIC, payload_json, 0)

                # Log reading to CSV file and flush to disk immediately
                csv_writer.writerow([timestamp, temperature, vibration, rpm, current, label])
                csv_file.flush()

                # Print to terminal with label
                print(f"Published [label={label}]: {payload_json}")

                step += 1
                time.sleep(2)

        except KeyboardInterrupt:
            # Handle Ctrl+C cleanly
            mqtt_client.disconnect()
            print("\nStopped")


if __name__ == "__main__":
    main()
