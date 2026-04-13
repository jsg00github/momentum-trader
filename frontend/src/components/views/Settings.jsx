import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../../api/client';
import { useToast } from '../common/ToastProvider';

/**
 * Settings — Platform settings panel
 * Theme, density, Telegram alerts, feedback
 */
function Settings() {
    const { addToast } = useToast();
    const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
    const [density, setDensity] = useState(localStorage.getItem('density') || 'comfortable');
    const [alertSettings, setAlertSettings] = useState({
        enabled: false,
        telegram_chat_id: '',
        notify_sl: true,
        notify_tp: true
    });
    const [loading, setLoading] = useState(true);
    const [feedback, setFeedback] = useState('');
    const [feedbackSent, setFeedbackSent] = useState(false);

    useEffect(() => {
        // Load alert settings from backend
        axios.get(`${API_BASE}/alerts/settings`)
            .then(res => {
                setAlertSettings(res.data);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    const handleThemeChange = (newTheme) => {
        setTheme(newTheme);
        localStorage.setItem('theme', newTheme);
        // Apply theme immediately
        document.body.classList.remove('theme-dark', 'theme-light', 'theme-cyber');
        document.body.classList.add(`theme-${newTheme}`);
        if (newTheme === 'light') {
            document.body.style.backgroundColor = '#f5f5f5';
            document.body.style.color = '#1a1a1a';
        } else if (newTheme === 'cyber') {
            document.body.style.backgroundColor = '#0d0221';
            document.body.style.color = '#00ff88';
        } else {
            document.body.style.backgroundColor = '#0a0a0a';
            document.body.style.color = '#ffffff';
        }
    };

    const handleDensityChange = (e) => {
        const newDensity = e.target.value;
        setDensity(newDensity);
        localStorage.setItem('density', newDensity);
        // Apply density immediately - just save for now as requires CSS
        document.body.classList.remove('density-comfortable', 'density-compact');
        document.body.classList.add(`density-${newDensity}`);
    };

    const handleAlertToggle = (field) => {
        const updated = { ...alertSettings, [field]: !alertSettings[field] };
        setAlertSettings(updated);
        axios.post(`${API_BASE}/alerts/settings`, updated).catch(console.error);
    };

    const handleChatIdSave = () => {
        axios.post(`${API_BASE}/alerts/settings`, alertSettings)
            .then(() => addToast('Telegram Chat ID saved!', 'success'))
            .catch(() => addToast('Error saving settings', 'error'));
    };

    const handleTestAlert = () => {
        axios.post(`${API_BASE}/alerts/test`)
            .then(() => addToast('Test alert sent! Check your Telegram.', 'success'))
            .catch(e => addToast('Error: ' + (e.response?.data?.detail || e.message), 'error'));
    };

    const handleFeedbackSubmit = () => {
        if (!feedback.trim()) return;
        // Send feedback via mailto or backend
        window.location.href = `mailto:javier.s.gomez@gmail.com?subject=Momentum Trader Feedback&body=${encodeURIComponent(feedback)}`;
        setFeedbackSent(true);
        setFeedback('');
    };

    return (
        <div className="p-8 max-w-4xl mx-auto">
            <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-blue-600/20 rounded-xl">
                    <span className="text-3xl">⚙️</span>
                </div>
                <div>
                    <h2 className="text-2xl font-bold text-white">Platform Settings</h2>
                    <p className="text-slate-400">Customize your trading experience</p>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Appearance */}
                <div className="bg-[#151515] border border-[#2a2a2a] rounded-xl p-6">
                    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                        <span>🎨</span> Appearance
                    </h3>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-2">Theme</label>
                            <div className="grid grid-cols-3 gap-2">
                                <button onClick={() => handleThemeChange('dark')} className={`px-3 py-2 text-xs font-bold rounded-lg border-2 transition ${theme === 'dark' ? 'bg-blue-600 text-white border-blue-400' : 'bg-[#2a2a2a] text-slate-400 border-[#3a3a3a] hover:border-blue-500'}`}>Dark</button>
                                <button onClick={() => handleThemeChange('light')} className={`px-3 py-2 text-xs font-bold rounded-lg border-2 transition ${theme === 'light' ? 'bg-blue-600 text-white border-blue-400' : 'bg-[#2a2a2a] text-slate-400 border-[#3a3a3a] hover:border-blue-500'}`}>Light</button>
                                <button onClick={() => handleThemeChange('cyber')} className={`px-3 py-2 text-xs font-bold rounded-lg border-2 transition ${theme === 'cyber' ? 'bg-blue-600 text-white border-blue-400' : 'bg-[#2a2a2a] text-slate-400 border-[#3a3a3a] hover:border-blue-500'}`}>Cyber</button>
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-2">Density</label>
                            <select value={density} onChange={handleDensityChange} className="w-full bg-[#0a0a0a] border border-[#3a3a3a] text-white text-sm rounded-lg p-2.5 focus:border-blue-500 focus:outline-none">
                                <option value="comfortable">Comfortable</option>
                                <option value="compact">Compact</option>
                            </select>
                        </div>
                    </div>
                </div>

                {/* Telegram Alerts */}
                <div className="bg-[#151515] border border-[#2a2a2a] rounded-xl p-6">
                    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                        <span>📱</span> Telegram Alerts
                    </h3>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-2">Chat ID</label>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={alertSettings.telegram_chat_id || ''}
                                    onChange={(e) => setAlertSettings({ ...alertSettings, telegram_chat_id: e.target.value })}
                                    placeholder="Your Telegram Chat ID"
                                    className="flex-1 bg-[#0a0a0a] border border-[#3a3a3a] text-white text-sm rounded-lg p-2.5 focus:border-blue-500 focus:outline-none"
                                />
                                <button onClick={handleChatIdSave} className="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg">Save</button>
                            </div>
                        </div>
                        <div className="flex items-center justify-between p-3 bg-[#0a0a0a] rounded-lg border border-[#2a2a2a]">
                            <span className="text-sm text-slate-300">Enable Alerts</span>
                            <button onClick={() => handleAlertToggle('enabled')} className={`w-10 h-5 rounded-full relative transition ${alertSettings.enabled ? 'bg-green-600' : 'bg-slate-700'}`}>
                                <div className={`absolute top-1 w-3 h-3 bg-white rounded-full transition-all ${alertSettings.enabled ? 'right-1' : 'left-1'}`}></div>
                            </button>
                        </div>
                        <button onClick={handleTestAlert} className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-white text-sm font-bold rounded-lg border border-slate-700 transition">
                            🔔 Send Test Alert
                        </button>
                    </div>
                </div>

                {/* Feedback */}
                <div className="bg-[#151515] border border-[#2a2a2a] rounded-xl p-6 md:col-span-2">
                    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                        <span>💬</span> Send Feedback
                    </h3>
                    {feedbackSent ? (
                        <div className="text-green-400 text-center py-4">✅ Thanks for your feedback!</div>
                    ) : (
                        <div className="space-y-4">
                            <textarea
                                value={feedback}
                                onChange={(e) => setFeedback(e.target.value)}
                                placeholder="Tell us what you think, report bugs, or suggest features..."
                                className="w-full bg-[#0a0a0a] border border-[#3a3a3a] text-white text-sm rounded-lg p-3 focus:border-blue-500 focus:outline-none h-24 resize-none"
                            />
                            <button onClick={handleFeedbackSubmit} className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg transition">
                                Send Feedback
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Footer Branding */}
            <div className="mt-12 pt-6 border-t border-[#2a2a2a] text-center">
                <p className="text-xs text-slate-600 font-mono mb-1">Momentum Trader v3.2.0</p>
                <p className="text-[10px] text-slate-700 italic">by Javier Gómez</p>
            </div>
        </div>
    );
}

export default Settings;
