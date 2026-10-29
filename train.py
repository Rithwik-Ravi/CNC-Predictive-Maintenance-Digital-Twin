"""
train.py - Predictive Maintenance Failure Prediction Model
Trains a Logistic Regression model to predict impending machine failure
based on sensor telemetry data (temperature, vibration, rpm, current).
"""

import os
import sys
import json
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix

# Determine paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "sensor_log.csv")
OUTPUT_JSON = os.path.join(BASE_DIR, "model_params.json")

# Define feature columns and target column
FEATURES = ["temperature", "vibration", "rpm", "current"]
TARGET = "label"


def main():
    # 1. Check if the dataset exists
    if not os.path.exists(CSV_FILE):
        print(f"Error: '{CSV_FILE}' does not exist.")
        sys.exit(1)

    # 2. Load dataset with pandas
    df = pd.read_csv(CSV_FILE)

    # 3. Validate dataset size (must have at least 300 rows)
    if len(df) < 300:
        print(f"Error: '{CSV_FILE}' has only {len(df)} rows (minimum required is 300).")
        sys.exit(1)

    # 4. Check that required columns exist
    missing_cols = [col for col in FEATURES + [TARGET] if col not in df.columns]
    if missing_cols:
        print(f"Error: Missing columns in CSV: {missing_cols}")
        sys.exit(1)

    # 5. Validate label values (must have more than one class to train a classifier)
    unique_labels = df[TARGET].dropna().unique()
    if len(unique_labels) < 2:
        print(f"Error: '{CSV_FILE}' has only one label value ({unique_labels}). At least two classes are required.")
        sys.exit(1)

    # Separate features (X) and target (y)
    X = df[FEATURES]
    y = df[TARGET]

    # 6. Split data: 75% train, 25% test, stratified by label for balanced representation
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y
    )

    # 7. Feature scaling: fit StandardScaler on training data only to prevent data leakage
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 8. Train Logistic Regression model on the scaled training features
    model = LogisticRegression(random_state=42)
    model.fit(X_train_scaled, y_train)

    # 9. Evaluate model performance on the test set
    y_pred = model.predict(X_test_scaled)

    print("Classification Report:")
    print(classification_report(y_test, y_pred))

    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    print()

    # 10. Extract parameters in full precision
    mean_vals = scaler.mean_.tolist()
    scale_vals = scaler.scale_.tolist()
    coef_vals = model.coef_[0].tolist()
    intercept_val = float(model.intercept_[0])

    # 11. Print values in the exact copy-paste-friendly Python format
    print(f"MEAN = {mean_vals}")
    print(f"SCALE = {scale_vals}")
    print(f"COEF = {coef_vals}")
    print(f"INTERCEPT = {intercept_val}")

    # 12. Save parameters to model_params.json
    model_params = {
        "MEAN": mean_vals,
        "SCALE": scale_vals,
        "COEF": coef_vals,
        "INTERCEPT": intercept_val
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(model_params, f, indent=4)

    print(f"\nParameters saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
