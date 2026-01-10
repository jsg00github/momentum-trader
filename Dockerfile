FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y gcc g++ curl && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código
COPY . .

# Puerto (Railway usa $PORT dinámico)
ENV PORT=8000
EXPOSE $PORT

# Comando (shell form para expandir $PORT)
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
