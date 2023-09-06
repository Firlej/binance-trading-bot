# binance-trading-bot


### Setup

Create `.env` file based on `.env.example` file

```bash
cp .env.example .env
```

```bash
rm -rf venv 
python3 -m venv venv
source venv/bin/activate
pip install ccxt asyncio python-dotenv numpy
pip freeze > requirements.txt
```

```bash
pip install -r requirements.txt
```

Stop and remove containers, rebuild new images, run new containers, 
```bash
sudo docker-compose down --remove-orphans
sudo docker-compose up --build --always-recreate-deps --detach --force-recreate
sudo docker-compose logs --follow --timestamps
```

bash into container
```bash
docker-compose exec bot-o bash
```
