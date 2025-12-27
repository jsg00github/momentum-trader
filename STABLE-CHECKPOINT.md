# Backup de Estado Estable - Momentum Trader

**Fecha:** 27 de Diciembre, 2024  
**Versión:** v1.0-stable  
**Estado:** ✅ FUNCIONANDO - Scanner Optimizado

## ✨ Características Incluidas

### Scanner Algorítmico
- ✅ Escaneo de 400 acciones líquidas (S&P 500)
- ✅ Tiempo de escaneo: 2-3 minutos
- ✅ Progress bar en tiempo real con detalles de batch
- ✅ Sistema anti-cuelgue con timeouts de 45s
- ✅ Abandono forzado de threads zombies (`shutdown(wait=False)`)

### Criterios de Búsqueda
1. **Precio mínimo:** $2.00
2. **Liquidez:** > 300,000 acciones/día
3. **Rally 3 meses:** > +90%
4. **Consolidación 1 mes:** Entre -25% y 0%
5. **Despertar 1 semana:** > +10%

### Trade Journal
- ✅ Registro de operaciones (Entry, Stop, Target)
- ✅ Cálculo automático de P&L
- ✅ Importación desde CSV
- ✅ Analytics con equity curve y calendar heatmap

### Otros Módulos
- ✅ Options Scanner (flujo de opciones institucionales)
- ✅ Watchlist interactiva con pre-market data
- ✅ DetailView con gráficos TradingView-style
- ✅ Sistema de backups de base de datos
- ✅ Telegram Alerts (morning/evening briefings)

## 📁 Archivos Críticos

### Backend Core
- `backend/main.py` - FastAPI server
- `backend/scan_engine.py` - **Motor de escaneo optimizado**
- `backend/screener.py` - Lógica de criterios
- `backend/scoring.py` - Sistema de puntuación
- `backend/trade_journal.py` - CRUD de operaciones
- `backend/alerts.py` - Telegram integration

### Frontend
- `backend/static/index.html` - Punto de entrada
- `backend/static/app_v2.js` - **React App principal**

### Configuración
- `tickers.txt` - **Lista curada de 400 acciones**
- `backend/trades.db` - Base de datos SQLite
- `.env` - Variables de entorno (Telegram tokens)

## 🔄 Cómo Restaurar Este Estado

### Opción 1: Backup Manual (Recomendado)
```powershell
# 1. Guardar este backup
Copy-Item -Recurse "c:/Users/micro/.gemini/antigravity/playground/ancient-glenn" "c:/Users/micro/Desktop/momentum-trader-STABLE-BACKUP"

# 2. Para restaurar más tarde
Remove-Item -Recurse "c:/Users/micro/.gemini/antigravity/playground/ancient-glenn"
Copy-Item -Recurse "c:/Users/micro/Desktop/momentum-trader-STABLE-BACKUP" "c:/Users/micro/.gemini/antigravity/playground/ancient-glenn"
```

### Opción 2: Git Checkpoint
```powershell
# Crear snapshot
cd c:/Users/micro/.gemini/antigravity/playground/ancient-glenn
git add .
git commit -m "STABLE v1.0 - Scanner optimizado funcionando"
git tag v1.0-stable

# Para volver a este punto más tarde
git reset --hard v1.0-stable
```

## ⚙️ Configuración Actual

### Scanner Engine
- **Batch size:** 50 tickers
- **Workers por batch:** 8 threads
- **Timeout por batch:** 45 segundos
- **Universo:** 400 acciones (tickers.txt)
- **Tiempo estimado:** 2-3 minutos

### Optimizaciones Aplicadas
1. ✅ `executor.shutdown(wait=False)` - Previene cuelgues por threads zombies
2. ✅ `concurrent.futures.as_completed(timeout=45)` - Timeout estricto
3. ✅ Universo reducido (10,500 → 400) - 90% reducción en tiempo
4. ✅ Garbage collection forzado entre batches
5. ✅ Progress tracking detallado con nombre de batch

## 🚀 Cómo Ejecutar

```powershell
cd c:/Users/micro/.gemini/antigravity/playground/ancient-glenn
python backend/main.py
```

Luego abrir: `http://127.0.0.1:8000`

## 📝 Notas Importantes

- **NO BORRAR** `tickers.txt` - Contiene el universo curado de 400 acciones
- **NO MODIFICAR** `scan_engine.py` línea 175 (`shutdown(wait=False)`) - Crítico para estabilidad
- Si el scanner se cuelga: Reiniciar backend con `taskkill /F /IM python.exe`
- La base de datos `trades.db` está en la carpeta `backend/`

## 🐛 Troubleshooting

**Problema:** Scanner se cuelga en un batch  
**Solución:** El timeout de 45s debería saltarlo automáticamente. Si no, reiniciar backend.

**Problema:** "Address already in use"  
**Solución:** `taskkill /F /IM python.exe` y volver a ejecutar

**Problema:** Frontend no carga  
**Solución:** Verificar que el backend esté corriendo en puerto 8000

## 📊 Rendimiento Esperado

- **Scan completo:** 2-3 minutos (400 tickers)
- **Resultados típicos:** 0-5 acciones por escaneo (criterios muy estrictos)
- **Uso de CPU:** Moderado durante scan, bajo en reposo
- **Uso de RAM:** ~200-300 MB

---

**⚠️ IMPORTANTE:** Este es un punto de restauración estable. Antes de hacer cambios grandes, crear un backup con:
```powershell
Copy-Item -Recurse "c:/Users/micro/.gemini/antigravity/playground/ancient-glenn" "c:/Users/micro/Desktop/backup-$(Get-Date -Format 'yyyy-MM-dd-HHmm')"
```
