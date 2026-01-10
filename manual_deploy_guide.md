# 🚀 Deploy Manual de Momentum Trader - $5/mes
## Sin Terraform, Paso a Paso para Principiantes

---

## 📋 OPCIÓN 1: RAILWAY + VERCEL (RECOMENDADA - $5/mes)

### **PARTE 1: Preparar el Código**

#### 1.1 Crear `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y gcc g++ curl && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código
COPY . .

# Puerto
EXPOSE 8000

# Comando
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 1.2 Actualizar `backend/requirements.txt`

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
pandas==2.1.3
numpy==1.26.2
yfinance==0.2.32
google-generativeai==0.3.1
python-multipart==0.0.6
python-dotenv==1.0.0
aiofiles==23.2.1
psycopg2-binary==2.9.9
sqlalchemy==2.0.23
alembic==1.12.1
```

#### 1.3 Crear `backend/database.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///trades.db")

# Railway usa postgres:// pero SQLAlchemy necesita postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

#### 1.4 Crear `backend/models.py`

```python
from sqlalchemy import Column, Integer, String, Float, Date, DateTime
from sqlalchemy.sql import func
from database import Base

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="default_user")
    ticker = Column(String, index=True)
    entry_date = Column(Date)
    exit_date = Column(Date, nullable=True)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    shares = Column(Integer)
    status = Column(String)
    strategy = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

#### 1.5 Actualizar `backend/main.py`

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models

# Crear tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Momentum Trader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Importar routers
from trade_journal import router as trade_router
# from watchlist import router as watchlist_router
# from calendar import router as calendar_router

app.include_router(trade_router)

@app.get("/api/health")
def health():
    return {"status": "healthy"}

# Servir frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

#### 1.6 Subir a GitHub

```bash
cd tu-proyecto
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/tu-usuario/momentum-trader.git
git push -u origin main
```

---

### **PARTE 2: Deploy del Backend en Railway**

#### 2.1 Crear Cuenta
1. Ir a https://railway.app
2. Clic en **"Start a New Project"**
3. Login con GitHub

#### 2.2 Crear Base de Datos PostgreSQL
1. Clic en **"+ New"**
2. Seleccionar **"Database"** → **"PostgreSQL"**
3. Esperar 30 segundos a que se cree
4. Clic en la base de datos → Tab **"Variables"**
5. Copiar el valor de `DATABASE_URL` (lo usarás después)

#### 2.3 Crear Servicio Backend
1. Clic en **"+ New"** → **"GitHub Repo"**
2. Conectar tu repositorio `momentum-trader`
3. Railway detecta automáticamente el Dockerfile

#### 2.4 Configurar Variables de Entorno
1. Clic en el servicio backend → Tab **"Variables"**
2. Agregar estas variables:

```
DATABASE_URL = (copia el valor de la base de datos PostgreSQL)
GEMINI_API_KEY = tu_api_key_de_gemini
FINNHUB_API_KEY = tu_api_key_de_finnhub (opcional)
PORT = 8000
```

3. Clic en **"Deploy"**

#### 2.5 Obtener URL Pública
1. Tab **"Settings"**
2. Sección **"Domains"**
3. Clic en **"Generate Domain"**
4. Te dará algo como: `momentum-trader-production.up.railway.app`
5. **GUARDAR ESTA URL** (la necesitarás para el frontend)

#### 2.6 Verificar que Funciona
```bash
curl https://tu-url.up.railway.app/api/health

# Debería responder:
# {"status":"healthy"}
```

---

### **PARTE 3: Deploy del Frontend en Vercel**

#### 3.1 Crear Cuenta
1. Ir a https://vercel.com
2. **"Sign Up"** con GitHub

#### 3.2 Preparar Frontend
1. En tu proyecto, crear `backend/static/config.js`:

```javascript
// backend/static/config.js
const API_URL = window.location.hostname === 'localhost' 
  ? 'http://localhost:8000'
  : 'https://tu-url.up.railway.app';  // ← CAMBIAR POR TU URL DE RAILWAY
```

2. En `backend/static/app.js`, reemplazar todas las llamadas fetch:

```javascript
// ANTES:
fetch('/api/trades')

// DESPUÉS:
fetch(`${API_URL}/api/trades`)
```

3. Commit y push:
```bash
git add .
git commit -m "Add production API URL"
git push
```

#### 3.3 Deploy en Vercel
1. En Vercel, clic en **"Add New..."** → **"Project"**
2. Import tu repo de GitHub
3. **Framework Preset**: Other
4. **Root Directory**: `backend/static`
5. **Build Command**: (dejar vacío)
6. **Output Directory**: `.` (punto)
7. Clic en **"Deploy"**

#### 3.4 Tu App Está Viva! 🎉
Vercel te dará una URL como:
```
https://momentum-trader.vercel.app
```

---

### **PARTE 4: Configurar Autenticación (Opcional pero Recomendado)**

#### 4.1 Usar Supabase Auth (GRATIS)

1. Ir a https://supabase.com
2. **"New Project"**
3. Name: `momentum-trader`
4. Crear proyecto (tarda 2 min)

#### 4.2 Configurar Auth

1. En Supabase Dashboard → **"Authentication"** → **"Providers"**
2. Habilitar **"Email"**
3. Ir a **"Settings"** → **"API"**
4. Copiar:
   - `Project URL`
   - `anon public` key

#### 4.3 Actualizar Frontend

Agregar a `backend/static/index.html` antes del cierre de `</head>`:

```html
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
```

Crear `backend/static/auth.js`:

```javascript
const SUPABASE_URL = 'https://tuprojectid.supabase.co';
const SUPABASE_KEY = 'tu_anon_key';
const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

async function login(email, password) {
  const { data, error } = await supabase.auth.signInWithPassword({
    email, password
  });
  
  if (error) {
    alert('Error: ' + error.message);
    return null;
  }
  
  return data.session.access_token;
}

async function signup(email, password) {
  const { data, error } = await supabase.auth.signUp({
    email, password
  });
  
  if (!error) {
    alert('Check your email to confirm!');
  }
  return data;
}

async function logout() {
  await supabase.auth.signOut();
  window.location.reload();
}

// Verificar si está logueado
async function checkAuth() {
  const { data: { session } } = await supabase.auth.getSession();
  return session;
}
```

#### 4.4 Agregar Login UI a `app.js`

```javascript
function LoginForm() {
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [isLogin, setIsLogin] = React.useState(true);
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isLogin) {
      const token = await login(email, password);
      if (token) window.location.reload();
    } else {
      await signup(email, password);
    }
  };
  
  return (
    <div style={{ maxWidth: '400px', margin: '100px auto', padding: '20px' }}>
      <h2>{isLogin ? 'Login' : 'Sign Up'}</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          style={{ width: '100%', padding: '10px', marginBottom: '10px' }}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          style={{ width: '100%', padding: '10px', marginBottom: '10px' }}
        />
        <button type="submit" style={{ width: '100%', padding: '10px' }}>
          {isLogin ? 'Login' : 'Sign Up'}
        </button>
      </form>
      <button onClick={() => setIsLogin(!isLogin)} style={{ marginTop: '10px' }}>
        {isLogin ? 'Need an account?' : 'Already have an account?'}
      </button>
    </div>
  );
}

// Modificar App component
function App() {
  const [session, setSession] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  
  React.useEffect(() => {
    checkAuth().then(session => {
      setSession(session);
      setLoading(false);
    });
  }, []);
  
  if (loading) return <div>Loading...</div>;
  if (!session) return <LoginForm />;
  
  return (
    <div>
      <button onClick={logout}>Logout</button>
      <MarketDashboard />
      <TradeJournal userId={session.user.id} />
      {/* resto de componentes */}
    </div>
  );
}
```

---

### **PARTE 5: Actualizar Backend para Multi-Usuario**

#### 5.1 Instalar Supabase en Backend

```bash
pip install supabase
```

Agregar a `requirements.txt`:
```
supabase==2.0.3
```

#### 5.2 Crear `backend/auth.py`

```python
from fastapi import Header, HTTPException
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Service key, no la anon key
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No token provided")
    
    token = authorization.split(" ")[1]
    
    try:
        user = supabase.auth.get_user(token)
        return user.user.id
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
```

#### 5.3 Actualizar `backend/trade_journal.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
import models

router = APIRouter(prefix="/api/trades", tags=["trades"])

@router.get("/")
def get_trades(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    trades = db.query(models.Trade).filter(
        models.Trade.user_id == user_id
    ).all()
    return trades

@router.post("/")
def create_trade(
    trade_data: dict,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    trade = models.Trade(**trade_data, user_id=user_id)
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade
```

#### 5.4 Agregar Variables a Railway

En Railway, agregar:
```
SUPABASE_URL = https://tuproject.supabase.co
SUPABASE_SERVICE_KEY = tu_service_role_key (la secreta)
```

---

### **PARTE 6: Monitoreo y Mantenimiento**

#### 6.1 Ver Logs en Railway
1. Clic en tu servicio
2. Tab **"Logs"**
3. Ver errores en tiempo real

#### 6.2 Ver Métricas
1. Tab **"Metrics"**
2. CPU, RAM, Network usage

#### 6.3 Backups de Base de Datos
Railway hace backups automáticos, pero puedes hacer uno manual:

```bash
# Instalar Railway CLI
npm i -g @railway/cli

# Login
railway login

# Backup
railway run pg_dump $DATABASE_URL > backup.sql
```

#### 6.4 Actualizar la App
```bash
# Hacer cambios en tu código
git add .
git commit -m "Fix bug X"
git push

# Railway y Vercel re-deployean automáticamente!
```

---

## 💰 COSTOS FINALES

| Servicio | Plan | Costo |
|----------|------|-------|
| **Railway** | Hobby | $5/mes (500 hrs) |
| **Vercel** | Hobby | GRATIS |
| **Supabase** | Free | GRATIS (50K usuarios) |
| **GitHub** | Free | GRATIS |
| **TOTAL** | | **$5/mes** |

---

## 🆘 TROUBLESHOOTING

### Error: "Application failed to respond"
- Verificar logs en Railway
- Asegurar que `PORT=8000` esté configurado
- Verificar que el Dockerfile esté en `backend/`

### Error: "CORS policy"
- Verificar que `allow_origins=["*"]` esté en `main.py`
- O configurar el dominio específico de Vercel

### Error: "Database connection failed"
- Verificar que `DATABASE_URL` esté correcta en Railway
- Revisar que empiece con `postgresql://` (no `postgres://`)

### Frontend no conecta con Backend
- Verificar que `API_URL` en `config.js` sea correcta
- Probar la URL manualmente: `https://tu-url.railway.app/api/health`

---

## ✅ CHECKLIST DE DEPLOY

- [ ] Código subido a GitHub
- [ ] Railway: Base de datos PostgreSQL creada
- [ ] Railway: Servicio backend deployado
- [ ] Railway: Variables de entorno configuradas
- [ ] Railway: URL pública generada
- [ ] Vercel: Frontend deployado
- [ ] Vercel: API_URL configurada
- [ ] App funciona en producción
- [ ] (Opcional) Supabase Auth configurado
- [ ] (Opcional) Multi-usuario implementado

---

## 🎓 PRÓXIMOS PASOS

1. **Custom Domain**: En Vercel → Settings → Domains → Add `tudominio.com`
2. **Scheduled Scans**: Railway tiene Cron Jobs (en Settings)
3. **Email Alerts**: Integrar SendGrid o Resend
4. **Analytics**: Agregar Vercel Analytics (gratis)
5. **Monitoring**: Railway tiene uptime monitoring incluido

---

## 📞 SOPORTE

- Railway Docs: https://docs.railway.app
- Vercel Docs: https://vercel.com/docs
- Supabase Docs: https://supabase.com/docs
- FastAPI Docs: https://fastapi.tiangolo.com

---

**¡LISTO! Tu app está en producción, multi-usuario, con autenticación, por $5/mes** 🎉