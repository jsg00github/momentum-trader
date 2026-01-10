// Configuration for Backend API URL
// Checks if running on localhost or production

(function () {
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

    // If local, assume backend is on port 8000 (standard FastAPI default)
    // If production (Vercel/Railway), assume relative path /api or specific URL

    // NOTE: If using Vercel rewrites to backend, relative '/api' is best.
    // If Vercel is just frontend and hits Railway directly, we need full URL.
    // For now, let's assume Vercel rewrites or standard relative path behavior.

    // However, the guide implies separating them. 
    // "const API_URL = ... ? 'http://localhost:8000' : 'https://tu-url.up.railway.app';"

    // Let's set a placeholder that the user MUST update after Railway deploy
    const RAILWAY_URL = "https://CHANGE_ME_TO_YOUR_RAILWAY_URL.up.railway.app";

    window.API_BASE = isLocal ? "http://localhost:8000/api" : `${RAILWAY_URL}/api`;

    console.log("[Config] API_BASE set to:", window.API_BASE);
})();
