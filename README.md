# binance-trading-bot


### Setup

Create `.env` file based on `.env.example` file

```
cp .env.example .env
```

```
rm -rf venv && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

```
pip freeze > requirements.txt
```