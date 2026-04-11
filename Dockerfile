# ============================================================
# Stage 1: Build Frontend (Node.js — discarded after build)
# ============================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ============================================================
# Stage 2: Python Application (production image)
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y gcc g++ curl && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL backend code
COPY . .

# Copy built frontend from Stage 1 into static/
# This OVERWRITES the old Babel/CDN static files with Vite-compiled bundles
COPY --from=frontend-builder /app/frontend/dist ./static/

# Puerto (Railway inyecta $PORT)
ENV PORT=8000
EXPOSE $PORT

# Comando
CMD ["python", "run.py"]
