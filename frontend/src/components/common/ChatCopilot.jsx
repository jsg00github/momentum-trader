import React, { useState, useEffect, useRef } from 'react';
import { API_BASE } from '../../api/client';

/**
 * ChatCopilot — floating AI assistant widget
 * Powered by Gemini 2.0, queries portfolio context via /api/chat/query
 */
function ChatCopilot() {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([
        { role: 'assistant', content: "Hello! I'm your Portfolio Copilot. Ask me anything about your positions, risk, or market trends. 📈" }
    ]);
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        if (isOpen) {
            scrollToBottom();
            inputRef.current?.focus();
        }
    }, [isOpen, messages]);

    const handleSend = async (text = null) => {
        const query = text || inputValue.trim();
        if (!query) return;

        // Add user message
        const newMessages = [...messages, { role: 'user', content: query }];
        setMessages(newMessages);
        setInputValue('');
        setIsLoading(true);

        try {
            // Prepare history for API (exclude first welcome message if needed, or keep it)
            const history = newMessages.length > 0 ? newMessages.map(m => ({ role: m.role, content: m.content })) : [];

            const res = await fetch(`${API_BASE}/chat/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, history })
            });

            if (res.ok) {
                const data = await res.json();
                setMessages([...newMessages, { role: 'assistant', content: data.response }]);
            } else {
                setMessages([...newMessages, { role: 'assistant', content: "⚠️ Sorry, I couldn't process your request. Please try again." }]);
            }
        } catch (err) {
            console.error(err);
            setMessages([...newMessages, { role: 'assistant', content: "❌ Network error. Please check your connection." }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const suggestions = [
        "How is my portfolio doing today?",
        "What is my biggest risk right now?",
        "Should I take profit on any winners?",
        "Summarize my sector exposure"
    ];

    return (
        <div className="fixed bottom-6 right-6 z-[100] flex flex-col items-end pointer-events-none">
            {/* Chat Window */}
            {isOpen && (
                <div className="bg-[#1e293b] w-[350px] h-[500px] rounded-2xl shadow-2xl border border-slate-700 flex flex-col overflow-hidden mb-4 pointer-events-auto animate-fade-in-up">
                    {/* Header */}
                    <div className="bg-gradient-to-r from-purple-900 to-blue-900 p-4 flex justify-between items-center border-b border-white/10">
                        <div className="flex items-center gap-2">
                            <span className="text-xl">🤖</span>
                            <div>
                                <h3 className="font-bold text-white text-sm">Portfolio Copilot</h3>
                                <p className="text-[10px] text-blue-200">Powered by Gemini 2.0</p>
                            </div>
                        </div>
                        <button onClick={() => setIsOpen(false)} className="text-white/70 hover:text-white transition">✕</button>
                    </div>

                    {/* Messages Area */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#0f172a]">
                        {messages.map((msg, idx) => (
                            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-xs sm:text-sm leading-relaxed shadow-sm ${msg.role === 'user'
                                    ? 'bg-blue-600 text-white rounded-br-none'
                                    : 'bg-[#334155] text-slate-200 rounded-bl-none border border-slate-600'
                                    }`}>
                                    {msg.role === 'assistant' ? (
                                        <div className="markdown-body" dangerouslySetInnerHTML={{
                                            __html: msg.content.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br/>')
                                        }} />
                                    ) : (
                                        msg.content
                                    )}
                                </div>
                            </div>
                        ))}
                        {isLoading && (
                            <div className="flex justify-start">
                                <div className="bg-[#334155] rounded-2xl rounded-bl-none px-4 py-3 border border-slate-600 flex gap-1.5 items-center">
                                    <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                    <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                    <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                                </div>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Suggestions (only if history is short) */}
                    {messages.length < 3 && (
                        <div className="px-4 pb-2 bg-[#0f172a] flex flex-wrap gap-2">
                            {suggestions.map((s, i) => (
                                <button
                                    key={i}
                                    onClick={() => handleSend(s)}
                                    className="text-[10px] bg-slate-800 text-slate-300 border border-slate-700 px-2 py-1 rounded-full hover:bg-slate-700 hover:text-white transition"
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Input Area */}
                    <div className="p-3 bg-[#1e293b] border-t border-slate-700">
                        <div className="flex gap-2">
                            <input
                                ref={inputRef}
                                type="text"
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Ask about your portfolio..."
                                className="flex-1 bg-slate-900 text-white text-xs sm:text-sm rounded-lg px-3 py-2 border border-slate-700 focus:outline-none focus:border-blue-500 transition placeholder-slate-500"
                                disabled={isLoading}
                            />
                            <button
                                onClick={() => handleSend()}
                                disabled={isLoading || !inputValue.trim()}
                                className="bg-blue-600 hover:bg-blue-500 text-white rounded-lg px-3 py-2 transition disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                ➤
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Toggle Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="bg-blue-600 hover:bg-blue-500 text-white p-4 rounded-full shadow-lg transition-transform hover:scale-110 pointer-events-auto flex items-center justify-center relative group"
            >
                {isOpen ? <span className="text-xl font-bold">✕</span> : <span className="text-2xl">💬</span>}

                {/* Tooltip */}
                {!isOpen && (
                    <span className="absolute right-full mr-4 px-3 py-1.5 bg-blue-600 text-white text-xs font-bold rounded-xl opacity-0 group-hover:opacity-100 transition whitespace-nowrap shadow-xl">
                        AI Copilot
                    </span>
                )}
            </button>
        </div>
    );
}

export default ChatCopilot;
