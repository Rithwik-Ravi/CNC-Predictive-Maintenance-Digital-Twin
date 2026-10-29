import ssl, hashlib
pem = open("certs/device.pem.crt").read()
der = ssl.PEM_cert_to_DER_cert(pem)
print("Certificate ID of your file:", hashlib.sha256(der).hexdigest())