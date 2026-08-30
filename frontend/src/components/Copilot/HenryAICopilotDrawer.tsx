import React, { useState } from 'react';
import { Bot, Send, Sparkles, X, RefreshCw, Cpu, CheckCircle2, HelpCircle } from 'lucide-react';
import { askAICopilot } from '../../services/api';
import type { MissionState } from '../../types/mission';

interface HenryAICopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  selectedCraterId: string;
  mission: MissionState | null;
}

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  provider?: string;
  timestamp: string;
}

const QUICK_CHIPS = [
  "Analyze S-band CPR & DOP anomalies",
  "Evaluate Top Landing Site Safety",
  "Compare Rover Traverse Strategies",
  "Explain 3-Tier Volume Uncertainty",
  "Prepare Viva Defense Rationale"
];

export const HenryAICopilotDrawer: React.FC<HenryAICopilotDrawerProps> = ({
  isOpen,
  onClose,
  selectedCraterId,
  mission,
}) => {
  const [inputQuery, setInputQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome-1',
      sender: 'assistant',
      text: `Greetings! I am **Henry AI**, your lead Planetary Mission Specialist configured with Henry Labs Intelligence key. Ask me any question regarding ${mission?.selected_crater.name || 'South Polar'} radar anomalies, landing safety, or rover path planning.`,
      provider: 'Henry Labs AI',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  if (!isOpen) return null;

  const handleSend = async (queryText?: string) => {
    const textToSend = (queryText || inputQuery).trim();
    if (!textToSend || loading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!queryText) setInputQuery('');
    setLoading(true);

    try {
      const res = await askAICopilot(textToSend, selectedCraterId, mission);
      const assistantMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        sender: 'assistant',
        text: res.answer,
        provider: res.provider,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        text: `⚠️ **Henry AI Note**: ${err.message || 'Could not connect to backend AI copilot router.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearHistory = () => {
    setMessages([
      {
        id: 'welcome-reset',
        sender: 'assistant',
        text: 'Chat history reset. How can Henry AI assist your mission analysis?',
        provider: 'Henry Labs AI',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  return (
    <div className="fixed inset-0 z-[100] flex justify-end bg-slate-950/60 backdrop-blur-sm animate-in fade-in duration-200">
      {/* Click backdrop to close */}
      <div className="flex-1" onClick={onClose} />

      {/* Drawer Container */}
      <div className="w-full max-w-lg bg-slate-900 border-l border-cyan-500/30 h-full flex flex-col shadow-2xl z-10">
        {/* Drawer Header */}
        <div className="p-4 border-b border-slate-800 bg-slate-950/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-500/50 flex items-center justify-center text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.3)]">
              <Bot className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-extrabold text-sm text-slate-100 tracking-wide uppercase">
                  Henry AI Copilot
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 font-bold">
                  HENRY LABS
                </span>
              </div>
              <p className="text-[11px] text-slate-400 flex items-center gap-1.5 mt-0.5">
                <Cpu className="w-3 h-3 text-emerald-400" />
                Context: {mission?.selected_crater.name || 'South Polar Region'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleClearHistory}
              title="Clear History"
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-950 hover:text-rose-400 text-slate-400 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Quick Suggestion Chips */}
        <div className="p-3 border-b border-slate-800/60 bg-slate-900/60 flex items-center gap-2 overflow-x-auto scrollbar-none">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
          <span className="text-[10px] text-slate-400 uppercase font-mono flex-shrink-0">Quick Prompts:</span>
          {QUICK_CHIPS.map((chip, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(chip)}
              disabled={loading}
              className="whitespace-nowrap px-2.5 py-1 text-[11px] rounded-full bg-slate-800/80 hover:bg-cyan-950 hover:text-cyan-300 hover:border-cyan-500/40 border border-slate-700/60 text-slate-300 transition flex-shrink-0"
            >
              {chip}
            </button>
          ))}
        </div>

        {/* Messages Stream */}
        <div className="flex-1 p-4 overflow-y-auto space-y-4 font-sans text-xs">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.sender === 'user' ? 'items-end' : 'items-start'
              }`}
            >
              <div className="flex items-center gap-1.5 text-[10px] text-slate-400 mb-1 font-mono">
                {msg.sender === 'assistant' ? (
                  <>
                    <Bot className="w-3 h-3 text-cyan-400" />
                    <span className="text-cyan-400 font-bold">{msg.provider || 'Henry AI'}</span>
                  </>
                ) : (
                  <span>Mission Operator</span>
                )}
                <span>• {msg.timestamp}</span>
              </div>

              <div
                className={`max-w-[88%] p-3.5 rounded-2xl shadow-md space-y-2 ${
                  msg.sender === 'user'
                    ? 'bg-cyan-600 text-slate-950 font-medium rounded-br-none'
                    : 'bg-slate-800/90 text-slate-200 border border-slate-700/70 rounded-bl-none leading-relaxed'
                }`}
              >
                {/* Format simple bold/headers */}
                {msg.text.split('\n').map((line, i) => {
                  if (line.startsWith('### ')) {
                    return <h4 key={i} className="font-bold text-cyan-300 text-xs mt-1 mb-0.5">{line.replace('### ', '')}</h4>;
                  }
                  if (line.startsWith('• ')) {
                    return (
                      <div key={i} className="flex items-start gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0 mt-0.5" />
                        <span>{line.replace('• ', '')}</span>
                      </div>
                    );
                  }
                  return <p key={i}>{line}</p>;
                })}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-2 text-cyan-400 bg-cyan-950/30 border border-cyan-800/40 p-3 rounded-xl w-fit animate-pulse">
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span className="text-xs font-mono">Henry AI is analyzing mission parameters...</span>
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="p-3 border-t border-slate-800 bg-slate-950">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Ask Henry AI about CPR, hazards, landing sites..."
              disabled={loading}
              className="flex-1 bg-slate-900 border border-slate-700 focus:border-cyan-500 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none transition"
            />
            <button
              type="submit"
              disabled={loading || !inputQuery.trim()}
              className="p-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-40 text-slate-950 font-bold transition flex items-center justify-center"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
          <div className="flex items-center justify-between text-[10px] text-slate-400 mt-2 px-1 font-mono">
            <span className="flex items-center gap-1">
              <HelpCircle className="w-3 h-3 text-cyan-400" /> Environment API Key Enabled
            </span>
            <span>Henry Labs Intelligence Engine v2.0</span>
          </div>
        </div>
      </div>
    </div>
  );
};
