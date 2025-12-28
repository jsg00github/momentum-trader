console.log("=== APP.JS LOADING TEST ===");

// Test if React is loaded
if (typeof React === 'undefined') {
    console.error("❌ React is NOT loaded");
} else {
    console.log("✓ React loaded");
}

// Test if useState is available
try {
    const { useState } = React;
    console.log("✓ useState available");
} catch (e) {
    console.error("❌ useState error:", e);
}

console.log("=== Loading actual app.js ===");
