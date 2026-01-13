// Configuration for Backend API URL
// Checks if running on localhost or production

(function () {
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

    // URL de Producción (Railway)
    const RAILWAY_URL = "https://web-production-5f603.up.railway.app";

    // For local dev, use the SAME hostname as the browser to avoid CORS issues
    // This ensures 127.0.0.1:8000 or localhost:8000 matches the frontend origin
    if (isLocal) {
        window.API_BASE = `http://${window.location.hostname}:8000/api`;
    } else {
        window.API_BASE = `${RAILWAY_URL}/api`;
    }

    console.log("[Config] API_BASE set to:", window.API_BASE);
})();
