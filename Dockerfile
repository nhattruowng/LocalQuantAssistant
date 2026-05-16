FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    APP_CONFIG_PATH=src/config/settings.yaml \
    LOCALQUANT_DB_PATH=data/localquant.db \
    LOCALQUANT_ENV=docker

WORKDIR /app

RUN groupadd --system --gid 10001 localquant \
    && useradd --system --uid 10001 --gid localquant --create-home localquant

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .
RUN mkdir -p data/raw data/processed data/backtest models logs \
    && chown -R localquant:localquant /app

USER localquant

EXPOSE 8501

CMD ["streamlit", "run", "src/app/dashboard.py", "--server.address=0.0.0.0", "--server.port=8501"]
