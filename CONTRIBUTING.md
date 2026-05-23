# Contributing

Thanks for your interest in V2Ray Monitor.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp config.example.toml config.toml
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Before Opening a Pull Request

- Do not include `config.toml`, database files, logs, tokens, passwords, or real
  server addresses.
- Update `README.md` when adding or changing user-visible features.
- Keep changes focused and easy to deploy on a small self-hosted server.
