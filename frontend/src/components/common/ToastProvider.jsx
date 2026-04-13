import React, { createContext, useContext, useState, useCallback } from 'react';

const ToastContext = createContext();
export const useToast = () => useContext(ToastContext);

/**
 * ToastProvider — replaces native alert() with styled floating notifications.
 * Wrap your app: <ToastProvider><App /></ToastProvider>
 * Usage: const { addToast } = useToast(); addToast('Saved!', 'success');
 */
export default function ToastProvider({ children }) {
    const [toasts, setToasts] = useState([]);

    const addToast = useCallback((message, type = 'info', duration = 4000) => {
        const id = Date.now() + Math.random();
        setToasts(prev => [...prev, { id, message, type }]);
        setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration);
    }, []);

    const removeToast = useCallback((id) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    const ICONS = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️',
    };

    const STYLES = {
        success: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
        error: 'bg-red-500/15 text-red-400 border-red-500/30',
        warning: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
        info: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    };

    return (
        <ToastContext.Provider value={{ addToast }}>
            {children}
            {/* Toast Container */}
            <div className="fixed bottom-20 right-6 z-[200] flex flex-col gap-2 max-w-sm pointer-events-none">
                {toasts.map(t => (
                    <div
                        key={t.id}
                        className={`pointer-events-auto px-4 py-3 rounded-xl text-sm font-medium shadow-2xl
                        border backdrop-blur-md animate-slide-in flex items-center gap-3 cursor-pointer
                        ${STYLES[t.type] || STYLES.info}`}
                        onClick={() => removeToast(t.id)}
                    >
                        <span className="text-base">{ICONS[t.type] || ICONS.info}</span>
                        <span className="flex-1">{t.message}</span>
                        <button className="text-white/40 hover:text-white/70 text-xs ml-2">✕</button>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
}
