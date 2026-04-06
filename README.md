# binance-trading-bot

A Binance trading bot with order rebalancing, and thread-safe operations.

### Setup

Create `.env` file based on `.env.example` file

```bash
cp .env.example .env
```

```bash
rm -rf venv 
python3 -m venv venv
source venv/bin/activate
pip install ccxt asyncio python-dotenv numpy pandas --upgrade
pip freeze > requirements.txt
```

```bash
pip install -r requirements.txt
```

Stop and remove containers, rebuild new images, run new containers, 
```bash
docker compose down --remove-orphans
docker compose up --build --always-recreate-deps --detach --force-recreate
docker compose logs --follow --timestamps
```
