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

```bash
sudo docker build -t binance-trading-bot .
```

Kill containers and rebuild images
```bash
sudo docker container kill $(sudo docker ps -aqf "name=bot*") && sudo docker build -t binance-trading-bot .
```

Stop containers
```bash
sudo docker container stop $(sudo docker ps -aqf "name=bot*")
```

Kill containers
```bash
sudo docker container kill $(sudo docker ps -aqf "name=bot*")
```

Print logs
```bash
sudo docker logs $(sudo docker ps -aqf "name=bot-oskar")
```


Delete all containers and images
```bash
sudo docker rm -f $(sudo docker ps -aq)
sudo docker rmi $(sudo docker images -q)
```


Run containers
```bash
sudo docker container stop $(sudo docker ps -aqf "name=bot*")
sudo docker rm -f $(sudo docker ps -aqf "name=bot*")
sudo docker build -t binance-trading-bot .
sudo docker run --env-file .env --detach --name bot-oskar binance-trading-bot
sudo docker run --env-file .env.marcel --detach --name bot-marcel binance-trading-bot
```

bash into container
```bash
docker exec -it $(sudo docker ps -aqf "name=bot-oskar") bash
```

