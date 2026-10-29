# AWS IoT Core Certificates Directory

This folder is configured to hold the mutual TLS (mTLS) X.509 device certificates and private keys required by `simulator.py` to authenticate securely with AWS IoT Core over port 8883.

> **Security Notice**: Actual cryptographic credentials (`*.pem`, `*.key`, `*.crt`) are strictly ignored by `.gitignore` and must never be committed to version control.

## Required Files

When deploying a simulated or physical machine, download the certificates from the **AWS IoT Core Console** (`All devices` -> `Things` -> `Certificates`) and place them here with the following filenames:

1. `AmazonRootCA1.pem` - AWS Root Certificate Authority (CA) certificate.
2. `device.pem.crt` - X.509 Device Client Certificate.
3. `private.pem.key` - RSA 2048-bit Private Key for device authentication.

## Verification

To verify that your certificate is properly formatted and valid before connecting:
```bash
python check_cert.py
```
This prints the SHA-256 fingerprint of `device.pem.crt` to match with the AWS IoT Core console.
