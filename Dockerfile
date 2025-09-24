FROM python:3.11-slim

# Dépendances système si besoin
RUN apt-get update && apt-get install -y \
    gcc \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

VOLUME /app
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
