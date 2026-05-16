PYTHON ?= python
DOCKER_COMPOSE ?= docker compose
SYMBOL ?= BTC/USDT
TIMEFRAME ?= 15m
MODEL ?= models/model.joblib
METADATA ?=
STREAMLIT_PORT ?= 8501

.PHONY: install collect features train backtest dashboard test docker-build docker-up docker-down docker-logs docker-shell docker-collect docker-features docker-train docker-backtest docker-test

install:
	$(PYTHON) -m pip install -r requirements.txt

collect:
	$(PYTHON) scripts/collect_market_data.py --symbol "$(SYMBOL)" --timeframe "$(TIMEFRAME)"

features:
	$(PYTHON) scripts/build_features.py --symbol "$(SYMBOL)" --timeframe "$(TIMEFRAME)"

train:
	$(PYTHON) main.py train --symbol "$(SYMBOL)" --timeframe "$(TIMEFRAME)"

backtest:
	$(PYTHON) main.py backtest --symbol "$(SYMBOL)" --timeframe "$(TIMEFRAME)" --model "$(MODEL)" $(if $(METADATA),--metadata "$(METADATA)",)

dashboard:
	streamlit run src/app/dashboard.py

test:
	pytest

docker-build:
	$(DOCKER_COMPOSE) build

docker-up:
	$(DOCKER_COMPOSE) up --build -d

docker-down:
	$(DOCKER_COMPOSE) down

docker-logs:
	$(DOCKER_COMPOSE) logs -f localquant

docker-shell:
	$(DOCKER_COMPOSE) run --rm localquant sh

docker-collect:
	$(DOCKER_COMPOSE) run --rm localquant python scripts/collect_market_data.py --symbol "$(SYMBOL)" --timeframe "$(TIMEFRAME)"

docker-features:
	$(DOCKER_COMPOSE) run --rm localquant python scripts/build_features.py --symbol "$(SYMBOL)" --timeframe "$(TIMEFRAME)"

docker-train:
	$(DOCKER_COMPOSE) run --rm localquant python main.py train --symbol "$(SYMBOL)" --timeframe "$(TIMEFRAME)"

docker-backtest:
	$(DOCKER_COMPOSE) run --rm localquant python main.py backtest --symbol "$(SYMBOL)" --timeframe "$(TIMEFRAME)" --model "$(MODEL)" $(if $(METADATA),--metadata "$(METADATA)",)

docker-test:
	$(DOCKER_COMPOSE) run --rm localquant pytest
