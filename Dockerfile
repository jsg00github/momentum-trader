FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y gcc g++ curl && rm -rf /var/lib/apt/lists/*

# Copiar TODO el contexto (respetando .dockerignore)
COPY . .

# DEBUG: Verificar estructura
RUN echo "--- Listing /app ---" && ls -la /app
RUN echo "--- Listing /app/backend ---" && ls -la /app/backend

# Instalar dependencias
RUN pip install --no-cache-dir -r backend/requirements.txt

# Cambiar al directorio backend para ejecutar
WORKDIR /app/backend

ENV PORT=8000
EXPOSE $PORT

# run.py busca 'main:app', y main.py usa imports relativos (corregidos en el paso anterior)
CMD ["python", "run.py"]
