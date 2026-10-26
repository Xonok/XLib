# Test fixtures

`cert.pem` and `key.pem` are a throwaway self-signed certificate for
`localhost` and `127.0.0.1`, used by `test_https.py` and the SSL-error test in
`test_server.py`. They are test data, not secrets: the key is committed on
purpose, and nothing outside the test suite should trust the certificate.

It expires in 2126, so a client that does verify it will not fail on a clock
check during the life of this repository.

Regenerate both files with:

```bash
openssl req -x509 -newkey rsa:2048 -nodes \
	-keyout key.pem -out cert.pem -days 36500 \
	-subj "/CN=localhost" \
	-addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```
