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
pip install ccxt asyncio python-dotenv
```

```
pip freeze > requirements.txt
```

```
sudo docker build -t binance-trading-bot .
```

```
sudo docker run \
--env-file .env \
--rm \
--detach \
--name btcbusd binance-trading-bot
```

```
sudo docker container kill $(sudo docker ps -aqf "name=btcbusd*")
```