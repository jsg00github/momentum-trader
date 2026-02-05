// Configuration for Backend API URL
// Automatically detects if running locally or in production

(function () {
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

    if (isLocal) {
        // Local development - use same hostname to avoid CORS issues
        window.API_BASE = `http://${window.location.hostname}:8000/api`;
    } else {
        // Production - use relative path (same domain serves both frontend and API)
        window.API_BASE = '/api';
    }

    console.log("[Config] API_BASE set to:", window.API_BASE);
})();
