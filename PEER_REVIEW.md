# 📊 PEER REVIEW: MOMENTUM TRADER
## Análisis Profesional de Código - Preparación para Cloud Deployment

**Fecha:** 2026-01-13  
**Aplicación:** Momentum Trader (Multi-Market Trading Journal)  
**Stack:** FastAPI + React (Babel JSX) + SQLAlchemy + PostgreSQL/SQLite  
**Target:** Railway (Backend) + Vercel (Frontend)

---

# 🏗️ EXECUTIVE SUMMARY

## Fortalezas
- ✅ Arquitectura multi-tenant bien implementada (user_id en todos los models)
- ✅ Sistema de cache de precios robusto (price_service.py)
- ✅ JWT authentication funcional
- ✅ Soporte multi-mercado (USA, Argentina, Crypto)
- ✅ Database abstraction lista para PostgreSQL

## Áreas Críticas a Mejorar
- ⚠️ **Frontend monolítico** (487KB en un solo archivo)
- ⚠️ **Secrets hardcodeados** en código
- ⚠️ **Falta rate limiting** en endpoints públicos
- ⚠️ **Sin health checks** apropiados para containers
- ⚠️ **Sin migraciones** de base de datos

---

# 🔒 SEGURIDAD

## 🔴 CRÍTICO: Secrets Hardcodeados

### auth.py:14
```python
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey123")  # VULNERABLE
```

### price_service.py:28
```python
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "cvmo1npr01ql90pv62e0cvmo1npr01ql90pv62eg")  # EXPOSED
```

**Remediación:**
```python
# auth.py
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required")

# price_service.py
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
if not FINNHUB_API_KEY:
    print("[Warning] FINNHUB_API_KEY not set, yfinance-only mode")
```

## 🔴 CRÍTICO: Binance API Keys en DB sin encriptar

### models.py:140-147
```python
class BinanceConfig(Base):
    api_key = Column(String)      # ⚠️ Plain text
    api_secret = Column(String)   # ⚠️ Plain text
```

**Remediación:**
```python
from cryptography.fernet import Fernet

# Usar encryption at rest
class BinanceConfig(Base):
    encrypted_api_key = Column(String)
    encrypted_api_secret = Column(String)
    
    def set_keys(self, api_key, api_secret, encryption_key):
        f = Fernet(encryption_key)
        self.encrypted_api_key = f.encrypt(api_key.encode()).decode()
        self.encrypted_api_secret = f.encrypt(api_secret.encode()).decode()
```

## 🟡 MEDIO: CORS Permisivo

### main.py:47-52
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Demasiado abierto
    allow_credentials=True,
)
```

**Para producción:**
```python
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
if not ALLOWED_ORIGINS or ALLOWED_ORIGINS == [""]:
    ALLOWED_ORIGINS = ["http://localhost:3000", "https://tudominio.vercel.app"]
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

# ⚡ PERFORMANCE

## Problema 1: Frontend Monolítico (487KB)

**Impacto:** Tiempo de carga inicial lento, no cacheable por partes

**Remediación para Vercel:**
```
/frontend
  /src
    /components
      TradeJournal.jsx
      CryptoJournal.jsx
      Dashboard.jsx
    App.jsx
  package.json (Vite + React)
```

## Problema 2: N+1 Queries

### watchlist.py:42-43
```python
prices_map = market_data.get_batch_latest_prices(tickers)  # ✅ OK

# Pero en otros lugares:
for ticker in tickers:
    price = get_price(ticker)  # ⚠️ N llamadas
```

**Ya resuelto parcialmente en price_service.py** con batch fetching.

## Problema 3: Sync Database Sessions en Async Context

### database.py
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Para mejor performance con async:**
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# database.py
DATABASE_URL = os.getenv("DATABASE_URL").replace("postgresql://", "postgresql+asyncpg://")
async_engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession)

async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session
```

## Problema 4: Cache In-Memory No Persistente

### price_service.py
```python
_price_cache = PriceCache(ttl=CACHE_TTL_SECONDS)  # Se pierde en restart
```

**Para Railway (multi-instance):**
```python
import redis

redis_client = redis.from_url(os.getenv("REDIS_URL"))

def get_cached_price(ticker):
    cached = redis_client.get(f"price:{ticker}")
    if cached:
        return json.loads(cached)
    return None

def cache_price(ticker, data, ttl=300):
    redis_client.setex(f"price:{ticker}", ttl, json.dumps(data))
```

---

# 🗄️ DATABASE & MULTI-TENANCY

## ✅ Bien Implementado
- Todos los models tienen `user_id` como FK
- Queries filtran por `current_user.id`
- Relaciones ORM correctas

## 🟡 Faltante: Migraciones

**No hay Alembic configurado.** Esto es crítico para producción.

```bash
pip install alembic
alembic init migrations

# alembic.ini
sqlalchemy.url = postgresql://...

# migrations/env.py
from models import Base
target_metadata = Base.metadata
```

**Agregar a Dockerfile:**
```dockerfile
CMD alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```

## 🟡 Índices Faltantes

### models.py - Agregar índices compuestos
```python
class Trade(Base):
    __table_args__ = (
        Index('ix_trade_user_status', 'user_id', 'status'),
        Index('ix_trade_user_ticker', 'user_id', 'ticker'),
    )
```

---

# 🚀 DEPLOYMENT CHECKLIST

## Railway (Backend)

### 1. Environment Variables Requeridas
```
DATABASE_URL=postgresql://...
SECRET_KEY=<random-32-chars>
FINNHUB_API_KEY=<your-key>
REDIS_URL=redis://... (opcional)
ALLOWED_ORIGINS=https://yourapp.vercel.app
```

### 2. Dockerfile Optimizado
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3. Agregar Health Check Endpoint

```python
# main.py
@app.get("/health")
def health_check():
    """Health check for container orchestration."""
    try:
        # Test DB connection
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Unhealthy: {e}")
```

## Vercel (Frontend)

### 1. Estructura Recomendada
```
/frontend
  /public
    index.html
  /src
    App.jsx
    components/
  package.json
  vercel.json
```

### 2. vercel.json
```json
{
  "builds": [{ "src": "package.json", "use": "@vercel/static-build" }],
  "routes": [{ "src": "/(.*)", "dest": "/index.html" }],
  "env": {
    "VITE_API_URL": "@api_url"
  }
}
```

### 3. Separar Frontend
Actualmente el frontend está embebido en `/static/app.js`. Para Vercel:

1. Crear nuevo repo o carpeta `/frontend`
2. Inicializar con Vite: `npm create vite@latest . -- --template react`
3. Migrar componentes de app.js a archivos separados
4. Configurar `VITE_API_URL` para apuntar a Railway

---

# 📋 ENTREGABLES

## 1. Backlog Priorizado

| Prioridad | Item | Esfuerzo | Impacto |
|-----------|------|----------|---------|
| P0 | Remover secrets hardcodeados | 1h | Crítico |
| P0 | Agregar health check endpoint | 30min | Crítico |
| P0 | Configurar Alembic migraciones | 2h | Crítico |
| P1 | Encriptar Binance keys | 2h | Alto |
| P1 | Configurar CORS restrictivo | 1h | Alto |
| P1 | Agregar rate limiting | 2h | Alto |
| P2 | Migrar cache a Redis | 4h | Medio |
| P2 | Separar frontend a Vercel | 8h | Medio |
| P3 | Async database sessions | 4h | Bajo |
| P3 | Agregar índices DB | 1h | Bajo |

## 2. Métricas de Código

| Archivo | LOC | Complejidad | Estado |
|---------|-----|-------------|--------|
| main.py | 1251 | Alta | Refactor recomendado |
| app.js | ~8500 | Muy Alta | Dividir urgente |
| trade_journal.py | 1083 | Media | OK |
| price_service.py | 532 | Baja | ✅ Bien estructurado |
| models.py | 172 | Baja | ✅ Bien estructurado |

## 3. Riesgos Identificados

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| API keys expuestas | Alta | Crítico | Env vars obligatorias |
| DB sin migraciones | Alta | Alto | Implementar Alembic |
| Frontend lento | Media | Medio | Code splitting |
| Cache lost on restart | Media | Bajo | Redis |

---

# ✅ CONCLUSIÓN

La aplicación tiene una **base sólida** para multi-tenancy y está **casi lista** para cloud deployment. Los issues de seguridad son fáciles de resolver (1-2 horas de trabajo).

**Próximo paso recomendado:**
1. Crear branch `feature/cloud-ready`
2. Resolver P0 items (secrets + health check + alembic)
3. Deploy a Railway staging
4. Test con 2-3 usuarios concurrentes
5. Decidir si separar frontend (opcional pero recomendado)

---

*Documento generado por peer review automatizado - 2026-01-13*
