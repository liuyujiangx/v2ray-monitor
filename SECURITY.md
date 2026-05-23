# Security Policy

## Sensitive Data

Do not commit these files or values:

- `config.toml`
- SQLite database files under `data/`
- V2Ray access or error logs
- Passwords, tokens, private keys, server IPs, or real user traffic logs

The repository includes `config.example.toml` as a safe template. Copy it to
`config.toml` on your server and keep the real file private.

## Reporting Security Issues

Please do not open public issues with secrets, live server addresses, or raw
traffic logs. Open a minimal issue that describes the problem without sensitive
details.
