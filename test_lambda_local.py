"""
test_lambda_local.py - Local test for Lambda probability prediction function
Imports predict_probability from lambda_process without invoking AWS services.
Tests healthy and failing machine sensor readings.
"""

from lambda_process import predict_probability


def main():
    print("Testing failure prediction logic locally...\n")

    # 1. Healthy sensor readings test: ~60 C, 2 mm/s, 1500 RPM, 12 A
    healthy_temp = 60.0
    healthy_vib = 2.0
    healthy_rpm = 1500.0
    healthy_curr = 12.0

    prob_healthy = predict_probability(
        healthy_temp, healthy_vib, healthy_rpm, healthy_curr
    )

    print("--- Healthy Sensor Reading ---")
    print(f"Inputs: Temperature={healthy_temp} C, Vibration={healthy_vib} mm/s, RPM={healthy_rpm}, Current={healthy_curr} A")
    print(f"Failure Probability: {prob_healthy:.6f} ({prob_healthy * 100:.2f}%)")
    print(f"Status Evaluation:   {'NORMAL' if prob_healthy < 0.4 else 'WARNING' if prob_healthy < 0.8 else 'CRITICAL'}")
    print()

    # 2. Failing sensor readings test: ~85 C, 8 mm/s, 1380 RPM, 17 A
    failing_temp = 85.0
    failing_vib = 8.0
    failing_rpm = 1380.0
    failing_curr = 17.0

    prob_failing = predict_probability(
        failing_temp, failing_vib, failing_rpm, failing_curr
    )

    print("--- Failing Sensor Reading ---")
    print(f"Inputs: Temperature={failing_temp} C, Vibration={failing_vib} mm/s, RPM={failing_rpm}, Current={failing_curr} A")
    print(f"Failure Probability: {prob_failing:.6f} ({prob_failing * 100:.2f}%)")
    print(f"Status Evaluation:   {'NORMAL' if prob_failing < 0.4 else 'WARNING' if prob_failing < 0.8 else 'CRITICAL'}")
    print()

    # Confirm outcomes
    assert prob_healthy < 0.1, f"Expected healthy probability near 0, got {prob_healthy}"
    assert prob_failing > 0.9, f"Expected failing probability near 1, got {prob_failing}"
    print("All checks passed: healthy is near 0 and failing is near 1.")


if __name__ == "__main__":
    main()
