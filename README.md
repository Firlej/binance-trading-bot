# binance-trading-bot


### Setup

Create `.env` file based on `.env.example` file

```bash
cp .env.example .env
```

```bash
rm -rf venv && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

```bash
pip install ccxt asyncio python-dotenv
```

```bash
pip freeze > requirements.txt
```

```bash
sudo docker build -t binance-trading-bot .
```

```bash
sudo docker run \
--env-file .env \
--rm \
--detach \
--name btcbusd binance-trading-bot
```

```bash
sudo docker container kill $(sudo docker ps -aqf "name=btcbusd*") && sudo docker build -t binance-trading-bot . && sudo docker run --env-file .env --rm --detach --name btcbusd binance-trading-bot
```

```bash
sudo docker container kill $(sudo docker ps -aqf "name=btcbusd*")
```


```bash
sudo docker logs $(sudo docker ps -aqf "name=btcbusd*")
```


Delete all containers and images
```bash
sudo docker rm -f $(sudo docker ps -aq) && sudo docker rmi $(sudo docker images -q)
```