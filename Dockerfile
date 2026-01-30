FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y gcc g++ curl && rm -rf /var/lib/apt/lists/*

# Copiar requirements desde backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el contenido de backend a /app
COPY backend/ .

# Las rutas copiadas ahora estan en /app
# E.g. /app/run.py, /app/main.py

ENV PORT=8000
EXPOSE $PORT

CMD ["python", "run.py"]
