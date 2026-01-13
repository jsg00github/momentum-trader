# 🚀 DEPLOYMENT CHECKLIST
## Railway (Backend) + Vercel (Frontend)

---

## ✅ Archivos Listos

| Archivo | Estado | Notas |
|---------|--------|-------|
| `Dockerfile` | ✅ OK | Python 3.11-slim, instala deps |
| `Procfile` | ✅ OK | Para Heroku/Railway |
| `requirements.txt` | ✅ OK | 21 dependencias |
| `run.py` | ✅ OK | Maneja $PORT dinámico |
| `.gitignore` | ✅ OK | Excluye .env, *.db, __pycache__ |
| `database.py` | ✅ OK | Maneja postgres:// → postgresql:// |

---

## 🔧 Environment Variables para Railway

Configurar en Railway Dashboard → Variables:

```bash
# OBLIGATORIAS
DATABASE_URL=postgresql://user:pass@host:5432/dbname
SECRET_KEY=<generar-con: openssl rand -hex 32>
FINNHUB_API_KEY=cvmo1npr01ql90pv62e0cvmo1npr01ql90pv62eg

# OPCIONALES
ALLOWED_ORIGINS=https://tu-app.vercel.app,https://tu-dominio.com
PRICE_CACHE_TTL=300
```

### Generar SECRET_KEY seguro:
```powershell
# PowerShell
-join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })
```

---

## 🗄️ Base de Datos

### Opción 1: Railway PostgreSQL (Recomendado)
1. En Railway: New → Database → PostgreSQL
2. Copiar `DATABASE_URL` del dashboard
3. Agregar como variable de entorno

### Opción 2: Usar SQLite temporal
- Ya funciona, pero no persiste entre deploys
- Solo para testing inicial

### Migrar datos locales:
```bash
# Exportar trades de SQLite local
sqlite3 trades.db ".dump trades" > trades_export.sql

# En Railway, usar pg_restore o SQL directo
```

---

## 🎨 Frontend (Vercel)

### Opción A: Deploy estático desde Railway
El frontend está embebido en `/static/`. Railway lo servirá automáticamente.
No necesitás Vercel por ahora.

### Opción B: Separar frontend (futuro)
1. Crear `/frontend` con Vite + React
2. Migrar componentes de `app.js`
3. Configurar `VITE_API_URL` apuntando a Railway

---

## 📋 Pre-Deploy Checklist

### Código
- [x] Secrets removidos del código (usa env vars)
- [x] Health check endpoint `/health` funciona
- [x] CORS configurado via `ALLOWED_ORIGINS`
- [x] Axios interceptor para auth automático
- [x] Database URL soporta PostgreSQL

### Archivos
- [x] Dockerfile correcto
- [x] Procfile presente
- [x] requirements.txt actualizado
- [x] .gitignore excluye .env y *.db

### Testing
- [ ] Login/Register funciona
- [ ] Trades CRUD funciona
- [ ] Precios live cargan (Finnhub → yfinance fallback)
- [ ] Global Portfolio carga

---

## 🚂 Deploy a Railway

### Paso 1: Conectar repo
```
Railway Dashboard → New Project → Deploy from GitHub
Seleccionar: jsg00github/momentum-trader
Branch: desarrollo
```

### Paso 2: Agregar PostgreSQL
```
New → Database → PostgreSQL
Copiar DATABASE_URL
```

### Paso 3: Variables de entorno
```
Settings → Variables → Add:
- DATABASE_URL (copiar de PostgreSQL)
- SECRET_KEY (generar nuevo)
- FINNHUB_API_KEY
- ALLOWED_ORIGINS (tu dominio frontend)
```

### Paso 4: Deploy
Railway hace auto-deploy cuando pusheás a `desarrollo`.

### Paso 5: Ejecutar migraciones (si usas Alembic)
```bash
# En Railway Shell o local conectado a Postgres
alembic upgrade head
```

---

## ⚠️ Cosas a Tener en Cuenta

### 1. Primera carga lenta
- El cache de precios está vacío
- Se llena automáticamente cada 5 minutos
- Primera request toma ~5-10 segundos

### 2. Tokens JWT
- Expiran en 7 días
- Si cambiás SECRET_KEY, todos los tokens se invalidan
- Los usuarios tendrán que reloguearse

### 3. SQLite vs PostgreSQL
- Algunas queries pueden necesitar ajuste
- `DateTime(timezone=True)` funciona igual
- Los archivos .db locales NO se suben (están en .gitignore)

### 4. Background Jobs
- APScheduler corre en proceso principal
- En multi-instance, pueden duplicarse
- Considerar usar Redis + Celery para producción pesada

---

## 🔍 Post-Deploy Verificación

```bash
# Verificar health
curl https://tu-app.railway.app/health

# Verificar login
curl -X POST https://tu-app.railway.app/api/auth/login \
  -d "username=test@test.com&password=yourpass" \
  -H "Content-Type: application/x-www-form-urlencoded"

# Verificar API protegida
curl https://tu-app.railway.app/api/trades/list \
  -H "Authorization: Bearer <token>"
```

---

## 📞 Troubleshooting

| Error | Causa | Solución |
|-------|-------|----------|
| 401 en todo | SECRET_KEY cambió | Reloguear usuarios |
| 500 en DB | DATABASE_URL mal | Verificar formato postgresql:// |
| Timeout | Cold start | Esperar 30s, Railway duerme apps gratis |
| CORS error | Origins mal | Agregar dominio a ALLOWED_ORIGINS |

---

*Checklist generado: 2026-01-13*
