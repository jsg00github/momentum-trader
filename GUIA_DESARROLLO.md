# 📘 Guía de Desarrollo - Momentum Trader

## Flujo de Trabajo

```
EDITAR (Local) → TESTEAR (Local) → COMMIT (GitHub) → DEPLOY (Render)
```

---

## 1️⃣ Levantar el Servidor Local

Abrí PowerShell en la carpeta del proyecto y ejecutá:

```powershell
cd backend
python -m uvicorn main:app --reload --port 8000
```

Luego abrí en el navegador: **http://localhost:8000**

> 💡 El flag `--reload` reinicia el servidor automáticamente cuando guardás cambios.

---

## 2️⃣ Hacer Cambios

- **Backend (Python):** Editá archivos `.py` en la carpeta `backend/`
- **Frontend (JS/HTML/CSS):** Editá archivos en `backend/static/`

Después de guardar:
- Cambios de **Python**: El servidor se reinicia solo
- Cambios de **Frontend**: Solo refrescá el navegador (F5)

---

## 3️⃣ Subir Cambios a la Nube

Cuando todo funciona en local, ejecutá:

```powershell
git add .
git commit -m "Descripción de lo que cambiaste"
git push origin master
```

---

## 4️⃣ Deploy Automático

Render.com detecta el push automáticamente y despliega en ~2 minutos.

Tu app en la nube: **https://momentum-trader-XXXX.onrender.com**

---

## 🔧 Comandos Útiles

| Acción | Comando |
|--------|---------|
| Ver estado de Git | `git status` |
| Ver cambios | `git diff` |
| Deshacer cambios no guardados | `git checkout -- archivo` |
| Ver logs del servidor | (se muestran en la terminal) |

---

## ⚠️ Errores Comunes

### "Port already in use"
```powershell
Get-Process -Name python | Stop-Process -Force
```

### "Module not found" en Render
Agregá la dependencia a `requirements.txt` y volvé a pushear.

### Cambios no aparecen en la nube
1. Verificá que hiciste `git push`
2. Revisá los logs en Render Dashboard

---

## 📁 Estructura del Proyecto

```
backend/
├── main.py              # Punto de entrada FastAPI
├── trade_journal.py     # Lógica del journal
├── screener.py          # Scanner de acciones
├── alerts.py            # Sistema de alertas
├── requirements.txt     # Dependencias Python
├── Procfile            # Config para Render
└── static/
    ├── index.html      # Frontend principal
    ├── app_v2.js       # Lógica React
    └── style.css       # Estilos
```

---

**Última actualización:** Diciembre 2024
