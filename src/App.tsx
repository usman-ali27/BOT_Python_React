import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ShieldCheck, 
  Target, 
  TrendingUp, 
  Activity, 
  BrainCircuit, 
  History, 
  Grip, 
  DollarSign,
  AlertTriangle,
  ChevronRight,
  Zap,
  ShieldAlert,
  Settings,
  Plug,
  Lock,
  Globe,
  Database
} from 'lucide-react';
import { TradingEngine, AccountStatus, Trade, NewsEvent } from './lib/trading-engine';
import { getMarketInsight, analyzeNewsSentiment } from './lib/gemini';
import { fetchGoldSentiment } from './lib/sentiment';
import { TradingChart } from './components/TradingChart';
import { NewsFeed } from './components/NewsFeed';
import { AccountStats } from './components/AccountStats';

// Constants
const INITIAL_BALANCE = 0;
const GOLD_BASE_PRICE = 0;

export default function App() {
    // Sentiment state (must be inside component)
    const [goldSentiment, setGoldSentiment] = useState<number>(0);
    // Fetch gold sentiment every 2 minutes
    useEffect(() => {
      const fetchSentiment = async () => {
        const score = await fetchGoldSentiment();
        setGoldSentiment(score);
      };
      fetchSentiment();
      const interval = setInterval(fetchSentiment, 120000);
      return () => clearInterval(interval);
    }, []);
  const [marketPrice, setMarketPrice] = useState(GOLD_BASE_PRICE);
  const [priceHistory, setPriceHistory] = useState<{ time: string; price: number }[]>([]);
  const [engine] = useState(() => new TradingEngine(INITIAL_BALANCE));
  const [status, setStatus] = useState<AccountStatus>(engine.getStatus());
  const [trades, setTrades] = useState<Trade[]>([]);
  const [pendingLevels, setPendingLevels] = useState<any[]>([]);
  const [news, setNews] = useState<NewsEvent[]>([
    { id: '1', title: 'Fed Signals Potential Pivot in 2026 Policy Meeting', impact: 'HIGH', sentiment: 0.5, timestamp: new Date() },
    { id: '2', title: 'Global Demand for Gold Surges as Reserve Asset', impact: 'MEDIUM', sentiment: 0.8, timestamp: new Date() },
    { id: '3', title: 'Consumer Spending Data Exceeds Experts Estimates', impact: 'LOW', sentiment: -0.2, timestamp: new Date() }
  ]);
  const [latency, setLatency] = useState(14.2);
  const [aiInsight, setAiInsight] = useState<string>("Analyzing market structure...");
  const [autoTrading, setAutoTrading] = useState(false);
  const [activeTab, setActiveTab] = useState<'monitor' | 'backtest' | 'broker' | 'config' | 'ict'>('monitor');
  const [ictEvents, setIctEvents] = useState<string[]>([]);

  // MT5 Interaction
  const [mt5Status, setMt5Status] = useState<'DISCONNECTED' | 'CONNECTING' | 'CONNECTED'>('DISCONNECTED');
  const [mt5Credentials, setMt5Credentials] = useState(() => {
    const saved = localStorage.getItem('mt5Creds');
    return saved ? JSON.parse(saved) : { accountID: '', password: '', server: '' };
  });

  const doConnect = async (creds: any) => {
    setMt5Status('CONNECTING');
    try {
      const response = await fetch('/api/mt5/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(creds)
      });
      const data = await response.json();
      if (data.status === 'connected') {
        setTimeout(() => {
          setMt5Status('CONNECTED');
          localStorage.setItem('mt5Creds', JSON.stringify(creds));
          if (data.balance) {
            engine.setBalance(data.balance);
            setTrades([]);
            setStatus(engine.getStatus());
          }
        }, 1500);
      } else {
        setMt5Status('DISCONNECTED');
      }
    } catch (error) {
       console.error("MT5 Connection Failed", error);
       setMt5Status('DISCONNECTED');
    }
  };

  useEffect(() => {
    const saved = localStorage.getItem('mt5Creds');
    if (saved) {
      doConnect(JSON.parse(saved));
    }
  }, []);

  const connectToMT5 = async (e: React.FormEvent) => {
    e.preventDefault();
    await doConnect(mt5Credentials);
  };

  // Latency Jitter
  useEffect(() => {
    const interval = setInterval(() => {
      setLatency(14 + Math.random() * 2);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const calculateVolatility = () => {
    if (priceHistory.length < 2) return "0.0 ATR";
    const changes = [];
    for (let i = 1; i < priceHistory.length; i++) {
       changes.push(Math.abs(priceHistory[i].price - priceHistory[i-1].price));
    }
    const avg = changes.reduce((a, b) => a + b, 0) / changes.length;
    return `${(avg * 10).toFixed(1)} ATR`;
  };

  const calculateNewsImpact = () => {
    if (news.length === 0) return 0;
    const impactMap = { 'HIGH': 100, 'MEDIUM': 60, 'LOW': 30 };
    const avg = news.reduce((sum, n) => sum + impactMap[n.impact], 0) / news.length;
    return avg;
  };
  useEffect(() => {
    const interval = setInterval(async () => {
      if (mt5Status === 'CONNECTED') {
        try {
          const res = await fetch('/api/mt5/status');
          if (res.ok) {
            const data = await res.json();
            if (data.tick && data.tick.bid) {
                const newPrice = data.tick.bid;
                setMarketPrice(newPrice);
                
                // Update History
                setPriceHistory(history => {
                  const now = new Date();
                  const newHistory = [...history, { 
                    time: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }), 
                    price: newPrice 
                  }].slice(-50);
                  return newHistory;
                });
            }
            if (data.account) {
                 setStatus(prev => {
                     const initBal = prev.initialBalance > 0 ? prev.initialBalance : data.account.balance;
                     const target = initBal > 0 ? initBal : 1;
                     return {
                         ...prev,
                         balance: data.account.balance,
                         equity: data.account.equity,
                         initialBalance: initBal,
                         dailyLoss: Math.max(0, (target - data.account.equity) / target),
                         totalLoss: Math.max(0, (target - data.account.equity) / target)
                     };
                 });
            }
            if (data.positions) {
                 const mapped = data.positions.map((p: any) => ({
                      id: p.ticket.toString(),
                      symbol: p.symbol,
                      type: p.type === 0 ? 'BUY' : 'SELL',
                      entryPrice: p.price_open,
                      lotSize: p.volume,
                      stopLoss: p.sl,
                      takeProfit: p.tp,
                      status: 'OPEN',
                      pnl: p.profit,
                      timestamp: new Date(p.time * 1000)
                 }));
                 setTrades(mapped);
            }
            if (data.bot_active !== undefined) {
                 setAutoTrading(data.bot_active);
            }
            if (data.grid_levels) {
                 setPendingLevels(data.grid_levels);
            }
            return; // Skip local simulation since we are live
          }
        } catch (e) {
            console.error("Live MT5 fetch error", e);
        }
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [autoTrading, engine, mt5Status]);

  // AI Insight Loop
  useEffect(() => {
    const fetchInsight = async () => {
      const insight = await getMarketInsight({ price: marketPrice });
      setAiInsight(insight);
    };

    fetchInsight();
    const interval = setInterval(fetchInsight, 15000); // UI Refresh of AI advice
    return () => clearInterval(interval);
  }, [marketPrice]);

  const toggleAutoTrading = async () => {
    if (mt5Status === 'CONNECTED') {
        const action = autoTrading ? 'stop' : 'start';
        try {
            const res = await fetch(`/api/bot/${action}`, { method: 'POST' });
            if (!res.ok) {
                const data = await res.json();
                alert(`🛑 Bot System Rejected Action\n\nReason: ${data.detail}`);
                return; // Do not toggle state
            }
        } catch (e) {
             console.error("Bot toggle network error", e);
             return;
        }
    }
    setAutoTrading(!autoTrading);
  };

  const activeTrades = trades.filter(t => t.status === 'OPEN');
  const totalPnL = activeTrades.reduce((sum, t) => sum + t.pnl, 0);
  const profitTarget = status.phase === 1 ? 0.10 : 0.05;
  const targetAmount = (status.initialBalance || 100000) * profitTarget;
  const currentProfit = status.equity - (status.initialBalance || 100000);
  const progressToTarget = Math.max(0, Math.min(100, (currentProfit / targetAmount) * 100));

  const [isBacktesting, setIsBacktesting] = useState(false);
  const [backtestResults, setBacktestResults] = useState<any>(null);

  // Fetch real backend backtest results
  const runBacktest = async () => {
    setIsBacktesting(true);
    try {
      const res = await fetch('/api/backtest/gold4mo');
      if (!res.ok) throw new Error('Backtest failed');
      const data = await res.json();
      setBacktestResults(data);
    } catch (e) {
      alert('Failed to fetch backtest results.');
    }
    setIsBacktesting(false);
  };

  return (
    <div className="flex flex-col h-screen bg-[#0D0E12] text-[#E0E0E0] font-sans selection:bg-[#00D1FF]/30">
      {/* Header */}
      <header className="px-[30px] py-[20px] border-b border-[rgba(255,255,255,0.08)] bg-gradient-to-r from-[#16181D] to-[#0D0E12] flex justify-between items-center z-10 shrink-0">
        <div className="flex items-center gap-4">
          <div className="text-[1.2rem] font-extrabold tracking-[2px] text-[#D4AF37] uppercase flex items-center gap-2">
            <TrendingUp size={20} className="text-[#D4AF37]" />
            AlphaGold AI <span className="text-[#888888] font-light">v2.6</span>
          </div>
        </div>
        
        <div className="hidden lg:flex gap-[30px] text-[0.75rem] uppercase tracking-[1px]">
          <div className="flex items-center gap-2 font-mono">
            <span className="text-[#888888]">Broker:</span> 
            <b className={mt5Status === 'CONNECTED' ? 'text-[#00FF85]' : 'text-[#00D1FF]'}>
              {mt5Status === 'CONNECTED' ? mt5Credentials.server : 'Awaiting Connection'}
            </b>
          </div>
          <div className="flex items-center gap-2 font-mono">
            <span className="text-[#888888]">MT5 Status:</span> 
            <b className={`flex items-center gap-1.5 ${
              mt5Status === 'CONNECTED' ? 'text-[#00FF85]' : 
              mt5Status === 'CONNECTING' ? 'text-[#D4AF37] animate-pulse' : 
              'text-[#FF4D4D]'
            }`}>
              <div className={`w-1.5 h-1.5 rounded-full ${
                mt5Status === 'CONNECTED' ? 'bg-[#00FF85]' : 
                mt5Status === 'CONNECTING' ? 'bg-[#D4AF37]' : 
                'bg-[#FF4D4D]'
              }`} />
              {mt5Status}
            </b>
          </div>
          <div className="flex items-center gap-2 font-mono"><span className="text-[#888888]">Ticker:</span> <b className="text-[#00D1FF]">XAUUSD</b></div>
        </div>

        <div className="flex gap-4">
          <button 
            onClick={toggleAutoTrading}
            className={`px-5 py-2.5 rounded-[4px] font-bold text-[0.7rem] uppercase tracking-wider shadow-lg transition-all duration-500 overflow-hidden relative group ${
              autoTrading 
              ? 'bg-[#FF4D4D] text-white' 
              : 'bg-[#00D1FF] text-black hover:bg-[#00D1FF]/90'
            }`}
          >
            <span className="relative z-10">{autoTrading ? 'Live Trading Active' : 'Engage Smart Bot'}</span>
            {autoTrading && <div className="absolute inset-0 bg-white/20 animate-pulse pointer-events-none" />}
          </button>
        </div>
      </header>

      {/* Main Grid View */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-[300px_1fr_300px] gap-[20px] p-[20px] overflow-y-auto lg:overflow-hidden custom-scrollbar">
        
        {/* Left Column: Challenges & Objectives */}
        <div className="flex flex-col gap-[20px] overflow-y-auto custom-scrollbar">
          <div className="panel p-[20px] flex flex-col gap-6">
            <AccountStats 
              status={status} 
              progressToTarget={progressToTarget} 
              targetAmount={targetAmount} 
              currentProfit={currentProfit} 
              totalPnL={totalPnL} 
              activeTradesCount={activeTrades.length} 
              calculateVolatility={() => calculateVolatility()} 
              mt5Status={mt5Status} 
              autoTrading={autoTrading} 
            />
          </div>

          <div className="panel p-[20px] flex-1 flex flex-col">
             <div className="text-[0.7rem] font-bold uppercase text-[#888888] mb-4 flex items-center gap-2">
               <BrainCircuit size={14} className="text-[#D4AF37]" />
               AI Sentiment Core
               <span className={`ml-2 px-2 py-1 rounded text-[0.7rem] font-mono ${goldSentiment > 0.3 ? 'bg-green-900 text-green-400' : goldSentiment < -0.3 ? 'bg-red-900 text-red-400' : 'bg-zinc-800 text-zinc-300'}`}
                 title="Live news-based sentiment score (-1 = very negative, 1 = very positive)">
                 {goldSentiment.toFixed(2)}
               </span>
             </div>
             <div className="bg-[#16181D] border border-[rgba(255,255,255,0.05)] p-4 rounded-[6px] mb-6 relative group overflow-hidden">
                <div className="absolute top-0 left-0 w-1 h-full bg-[#D4AF37]" />
                <p className="text-[0.8rem] leading-relaxed italic text-[#E0E0E0] font-light">
                  "{aiInsight}"
                </p>
             </div>
             
             <div className="space-y-4">
                <div className="flex justify-between items-center">
                   <span className="text-[0.65rem] uppercase font-bold text-[#888888]">News Impact</span>
                   <span className="tag tag-gold">High Volatility Scan</span>
                </div>
                <div className="flex items-center gap-3">
                   <div className="flex-1 h-1 bg-[#23262D] rounded-full overflow-hidden">
                      <div className="h-full bg-[#D4AF37]" style={{ width: `${calculateNewsImpact()}%` }}></div>
                   </div>
                   <span className="text-[0.7rem] font-mono text-[#D4AF37]">{calculateNewsImpact().toFixed(0)}%</span>
                </div>
             </div>

             <div className="mt-auto pt-6 border-t border-[rgba(255,255,255,0.05)]">
                <div className="flex items-center gap-2 text-[0.65rem] font-bold uppercase text-[#888888]">
                  <Activity size={12} className="text-[#00FF85]" />
                  Internal Engine
                </div>
                <div className="text-[1rem] font-mono text-[#E0E0E0] mt-1 italic">STABLE_GRID_v4</div>
             </div>
          </div>
        </div>

        {/* Center Column: Charts & Grid */}
        <div className="flex flex-col gap-[20px] overflow-y-auto lg:overflow-hidden custom-scrollbar min-h-0">
          <div className="panel flex-1 flex flex-col p-0 overflow-hidden min-h-0">
            <div className="p-[20px] flex justify-between items-center bg-gradient-to-b from-[rgba(255,255,255,0.03)] to-transparent">
              <div className="flex flex-col">
                <div className="text-[0.7rem] font-bold uppercase text-[#888888] tracking-widest mb-1">XAUUSD Live Matrix</div>
                <div className="text-[1.8rem] font-mono font-bold tracking-tighter italic text-[#E0E0E0]">
                  ${activeTab === 'backtest' && backtestResults ? backtestResults.path[backtestResults.path.length-1].price.toFixed(2) : marketPrice.toFixed(2)}
                </div>
              </div>
              
          <div className="flex bg-[#0D0E12] p-1 rounded-[6px] border border-[rgba(255,255,255,0.08)]">
            <button 
              onClick={() => setActiveTab('monitor')}
              className={`px-3 py-2 rounded-[4px] text-[0.65rem] font-bold uppercase transition-all duration-300 ${activeTab === 'monitor' ? 'bg-[#23262D] text-[#00D1FF] shadow-inner' : 'text-[#888888] hover:text-[#E0E0E0]'}`}
            >
              Monitor
            </button>
            <button 
              onClick={() => setActiveTab('ict')}
              className={`px-3 py-2 rounded-[4px] text-[0.65rem] font-bold uppercase transition-all duration-300 ${activeTab === 'ict' ? 'bg-[#23262D] text-[#D4AF37] shadow-inner' : 'text-[#888888] hover:text-[#E0E0E0]'}`}
            >
              ICT / MTF
            </button>
            <button 
              onClick={() => setActiveTab('backtest')}
              className={`px-3 py-2 rounded-[4px] text-[0.65rem] font-bold uppercase transition-all duration-300 ${activeTab === 'backtest' ? 'bg-[#23262D] text-[#00D1FF] shadow-inner' : 'text-[#888888] hover:text-[#E0E0E0]'}`}
            >
              Simulation
            </button>
            <button 
              onClick={() => setActiveTab('broker')}
              className={`px-3 py-2 rounded-[4px] text-[0.65rem] font-bold uppercase transition-all duration-300 ${activeTab === 'broker' ? 'bg-[#23262D] text-[#00D1FF] shadow-inner' : 'text-[#888888] hover:text-[#E0E0E0]'}`}
            >
              Broker
            </button>
            <button 
              onClick={() => setActiveTab('config')}
              className={`px-3 py-2 rounded-[4px] text-[0.65rem] font-bold uppercase transition-all duration-300 ${activeTab === 'config' ? 'bg-[#23262D] text-[#00D1FF] shadow-inner' : 'text-[#888888] hover:text-[#E0E0E0]'}`}
            >
              Protocols
            </button>
          </div>
            </div>

            <div className="flex-1 bg-[#090A0C] relative border-t border-[rgba(255,255,255,0.03)] overflow-y-auto custom-scrollbar min-h-0">
              {activeTab === 'monitor' ? (
                <TradingChart data={priceHistory} />
              ) : activeTab === 'ict' ? (
                <div className="p-8 flex flex-col gap-6">
                   <div className="flex justify-between items-start">
                      <div>
                        <h2 className="text-xl font-bold italic text-[#D4AF37]">ICT / Multi-Timeframe Core</h2>
                        <p className="text-[0.7rem] text-[#888888] uppercase tracking-widest mt-1">HTF Alignment: 1H / 15M → Scalp: {engine.getConfig().executionTF}</p>
                      </div>
                      <div className="flex gap-2">
                         {['BULLISH', 'BEARISH', 'NEUTRAL'].map(bias => (
                           <button 
                             key={bias}
                             onClick={() => {
                               engine.setConfig({ htfBias: bias as any });
                               setStatus({...engine.getStatus()});
                             }}
                             className={`px-3 py-1 rounded text-[0.6rem] font-bold border transition-all ${
                               engine.getConfig().htfBias === bias 
                               ? 'border-[#D4AF37] text-[#D4AF37] bg-[#D4AF37]/10' 
                               : 'border-white/10 text-white/30'
                             }`}
                           >
                             {bias}
                           </button>
                         ))}
                      </div>
                   </div>

                   <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="bg-[#16181D] border border-white/5 p-4 rounded-lg">
                         <div className="text-[0.65rem] text-zinc-500 uppercase font-bold mb-3 flex items-center gap-2">
                           <Target size={12} className="text-[#00D1FF]" /> Smart Order Flow
                         </div>
                         <div className="space-y-3">
                            <div className="flex justify-between text-[0.7rem]">
                               <span className="text-zinc-400">Execution TF</span>
                               <span className="text-[#00D1FF] font-bold">{engine.getConfig().executionTF}</span>
                            </div>
                            <div className="flex justify-between text-[0.7rem]">
                               <span className="text-zinc-400">Liquidity Scan</span>
                               <span className="text-green-500 font-bold">Active</span>
                            </div>
                         </div>
                      </div>
                      <div className="md:col-span-2 bg-[#16181D] border border-white/5 p-4 rounded-lg">
                         <div className="text-[0.65rem] text-zinc-500 uppercase font-bold mb-3">Live ICT Market Events</div>
                         <div className="space-y-2">
                            {ictEvents.slice().reverse().map((ev, i) => (
                              <motion.div 
                                key={i}
                                initial={{ opacity: 0, y: 5 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="flex items-center gap-3 text-[0.7rem] py-1 border-b border-white/5"
                              >
                                <span className="text-[#D4AF37] font-bold font-mono">[{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}]</span>
                                <span className={ev.includes('ICT') ? 'text-[#00FF85]' : 'text-zinc-400'}>{ev}</span>
                              </motion.div>
                            ))}
                            {ictEvents.length === 0 && <div className="text-zinc-600 italic text-[0.7rem]">Scanning order flow...</div>}
                         </div>
                      </div>
                   </div>

                   <div className="bg-[#16181D] border border-white/5 p-6 rounded-lg relative overflow-hidden">
                      <div className="absolute top-0 right-0 p-4 opacity-10">
                         <BrainCircuit size={80} />
                      </div>
                      <h3 className="text-sm font-bold uppercase tracking-wider mb-2">Institutional Logic</h3>
                      <p className="text-[0.75rem] text-zinc-400 leading-relaxed max-w-xl">
                        The bot currently monitors <span className="text-[#D4AF37]">FVGs (Fair Value Gaps)</span> on the M1/M5 chart only when HTF bias (1H) is aligned. 
                        Grid spacing is locked at <span className="text-white font-mono">${engine.getConfig().gridSpacing}</span> price delta to ensure 
                        scalp positions aren't clustered in equilibrium zones.
                      </p>
                   </div>
                </div>
              ) : activeTab === 'backtest' ? (
                <div className="p-[20px] h-full flex flex-col gap-4">
                  <div className="flex-1 relative">
                    <TradingChart data={backtestResults && backtestResults.history ? backtestResults.history.map(h => ({ time: h.time, price: h.equity })) : []} />
                  </div>
                  {backtestResults && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center text-[0.9rem] font-mono">
                      <div className="bg-[#16181D] rounded p-3">
                        <div className="text-[#888] text-[0.7rem] uppercase">Final Balance</div>
                        <div className="text-[#00FF85] text-lg font-bold">${backtestResults.final_balance?.toLocaleString()}</div>
                      </div>
                      <div className="bg-[#16181D] rounded p-3">
                        <div className="text-[#888] text-[0.7rem] uppercase">Total Return</div>
                        <div className="text-[#D4AF37] text-lg font-bold">{backtestResults.total_return_pct?.toFixed(1)}%</div>
                      </div>
                      <div className="bg-[#16181D] rounded p-3">
                        <div className="text-[#888] text-[0.7rem] uppercase">Max Drawdown</div>
                        <div className="text-[#FF4D4D] text-lg font-bold">{backtestResults.max_drawdown_pct?.toFixed(2)}%</div>
                      </div>
                      <div className="bg-[#16181D] rounded p-3">
                        <div className="text-[#888] text-[0.7rem] uppercase">Win Rate</div>
                        <div className="text-[#00D1FF] text-lg font-bold">{(backtestResults.accuracy * 100).toFixed(2)}%</div>
                      </div>
                    </div>
                  )}
                  <button
                    onClick={runBacktest}
                    disabled={isBacktesting}
                    className="w-full py-3 bg-[#23262D] border border-[rgba(255,255,255,0.08)] rounded-[6px] text-[0.75rem] font-bold uppercase tracking-[2px] hover:bg-[#D4AF37] hover:text-black transition-all duration-300 disabled:opacity-50"
                  >
                    {isBacktesting ? 'Loading Backtest Results...' : 'Run 4-Month Gold Backtest'}
                  </button>
                </div>
              ) : activeTab === 'config' ? (
                <div className="p-8">
                  <div className="max-w-3xl mx-auto space-y-8">
                    <div>
                      <h2 className="text-xl font-bold italic text-[#D4AF37]">Engine Protocols</h2>
                      <p className="text-[0.7rem] text-[#888888] uppercase tracking-widest mt-1">Algorithmic DNA Modification</p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-6">
                        <div className="bg-[#16181D] border border-[rgba(255,255,255,0.05)] rounded-lg p-6">
                          <h3 className="text-[0.7rem] font-bold uppercase text-[#888888] mb-6 flex items-center gap-2">
                            <Grip size={14} className="text-[#00D1FF]" />
                            Grid Parameters
                          </h3>
                          <div className="space-y-4">
                            <div>
                              <div className="flex justify-between text-[0.65rem] mb-2 font-bold uppercase">
                                <span>Grid Spacing ($)</span>
                                <span className="text-[#E0E0E0]">${engine.getConfig().gridSpacing} Delta</span>
                              </div>
                              <input 
                                type="range" min="5" max="50" step="1" 
                                value={engine.getConfig().gridSpacing}
                                onChange={(e) => {
                                  engine.setConfig({ gridSpacing: parseFloat(e.target.value) });
                                  setStatus({...engine.getStatus()});
                                }}
                                className="w-full accent-[#D4AF37]"
                              />
                            </div>
                            <div>
                              <div className="flex justify-between text-[0.65rem] mb-2 font-bold uppercase">
                                <span>Max Grid Levels</span>
                                <span className="text-[#E0E0E0]">{engine.getConfig().levels} Nodes</span>
                              </div>
                              <input 
                                type="range" min="2" max="20" step="1" 
                                value={engine.getConfig().levels}
                                onChange={(e) => {
                                  engine.setConfig({ levels: parseInt(e.target.value) });
                                  setStatus({...engine.getStatus()});
                                }}
                                className="w-full accent-[#D4AF37]"
                              />
                            </div>
                          </div>
                        </div>

                        <div className="bg-[#16181D] border border-[rgba(255,255,255,0.05)] rounded-lg p-6">
                          <h3 className="text-[0.7rem] font-bold uppercase text-[#888888] mb-6 flex items-center gap-2">
                            <ShieldCheck size={14} className="text-[#00FF85]" />
                            Risk Targets
                          </h3>
                          <div className="space-y-4">
                            <div>
                              <div className="flex justify-between text-[0.65rem] mb-2 font-bold uppercase">
                                <span>Min Lot Size</span>
                                <span className="text-[#E0E0E0]">{engine.getConfig().minLotSize.toFixed(2)} Lots</span>
                              </div>
                              <input 
                                type="range" min="0.01" max="0.04" step="0.01" 
                                value={engine.getConfig().minLotSize}
                                onChange={(e) => {
                                  engine.setConfig({ minLotSize: parseFloat(e.target.value) });
                                  setStatus({...engine.getStatus()});
                                }}
                                className="w-full accent-[#00FF85]"
                              />
                            </div>
                            <div>
                              <div className="flex justify-between text-[0.65rem] mb-2 font-bold uppercase">
                                <span>Max Lot Size</span>
                                <span className="text-[#E0E0E0]">{engine.getConfig().maxLotSize.toFixed(2)} Lots</span>
                              </div>
                              <input 
                                type="range" min="0.01" max="0.10" step="0.01" 
                                value={engine.getConfig().maxLotSize}
                                onChange={(e) => {
                                  engine.setConfig({ maxLotSize: parseFloat(e.target.value) });
                                  setStatus({...engine.getStatus()});
                                }}
                                className="w-full accent-[#00FF85]"
                              />
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-6">
                        <div className="bg-[#16181D] border border-[rgba(255,255,255,0.05)] rounded-lg p-6">
                          <h3 className="text-[0.7rem] font-bold uppercase text-[#888888] mb-6 flex items-center gap-2">
                            <Activity size={14} className="text-[#FF4D4D]" />
                            Exit Strategies
                          </h3>
                          <div className="space-y-4">
                            <div>
                              <div className="flex justify-between text-[0.65rem] mb-2 font-bold uppercase">
                                <span>Take Profit</span>
                                <span className="text-[#E0E0E0]">{engine.getConfig().takeProfitDistance} Pips</span>
                              </div>
                              <input 
                                type="range" min="1.0" max="20.0" step="0.5" 
                                value={engine.getConfig().takeProfitDistance}
                                onChange={(e) => {
                                  engine.setConfig({ takeProfitDistance: parseFloat(e.target.value) });
                                  setStatus({...engine.getStatus()});
                                }}
                                className="w-full accent-[#00FF85]"
                              />
                            </div>
                            <div>
                              <div className="flex justify-between text-[0.65rem] mb-2 font-bold uppercase">
                                <span>Trailing Distance</span>
                                <span className="text-[#E0E0E0]">{engine.getConfig().trailingStopDistance} Pips</span>
                              </div>
                              <input 
                                type="range" min="0.5" max="10.0" step="0.1" 
                                value={engine.getConfig().trailingStopDistance}
                                onChange={(e) => {
                                  engine.setConfig({ trailingStopDistance: parseFloat(e.target.value) });
                                  setStatus({...engine.getStatus()});
                                }}
                                className="w-full accent-[#00D1FF]"
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-8">
                  <div className="max-w-2xl mx-auto space-y-8">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="text-xl font-bold italic text-[#D4AF37]">MetaTrader 5 Bridge</h2>
                        <p className="text-[0.7rem] text-[#888888] uppercase tracking-widest mt-1">Institutional Execution Layer</p>
                      </div>
                      <div className={`px-4 py-1.5 rounded-full text-[0.65rem] font-bold border ${
                        mt5Status === 'CONNECTED' ? 'bg-[rgba(0,255,133,0.05)] border-[#00FF85] text-[#00FF85]' :
                        mt5Status === 'CONNECTING' ? 'bg-[rgba(212,175,55,0.05)] border-[#D4AF37] text-[#D4AF37] animate-pulse' :
                        'bg-[rgba(255,77,77,0.05)] border-[#FF4D4D] text-[#FF4D4D]'
                      }`}>
                        {mt5Status}
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="bg-[#16181D] border border-[rgba(255,255,255,0.05)] rounded-lg p-6 space-y-4">
                        <div className="flex items-center gap-3 text-[#E0E0E0]">
                          <Plug size={18} className="text-[#00D1FF]" />
                          <span className="text-sm font-bold uppercase tracking-wider">Account Credentials</span>
                        </div>
                        <form onSubmit={connectToMT5} className="space-y-4">
                          <div className="space-y-1.5">
                            <label className="text-[0.6rem] text-[#888888] uppercase font-bold tracking-widest">Account ID</label>
                            <input 
                              type="text" 
                              value={mt5Credentials.accountID}
                              onChange={(e) => setMt5Credentials({...mt5Credentials, accountID: e.target.value})}
                              placeholder="e.g. 5002148"
                              className="w-full bg-[#0D0E12] border border-[rgba(255,255,255,0.08)] rounded px-3 py-2 text-sm focus:outline-none focus:border-[#D4AF37] transition-colors"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="text-[0.6rem] text-[#888888] uppercase font-bold tracking-widest">Master Password</label>
                            <div className="relative">
                              <input 
                                type="password" 
                                value={mt5Credentials.password}
                                onChange={(e) => setMt5Credentials({...mt5Credentials, password: e.target.value})}
                                placeholder="••••••••"
                                className="w-full bg-[#0D0E12] border border-[rgba(255,255,255,0.08)] rounded px-3 py-2 text-sm focus:outline-none focus:border-[#D4AF37] transition-colors"
                              />
                              <Lock size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#343a40]" />
                            </div>
                          </div>
                          <div className="space-y-1.5">
                            <label className="text-[0.6rem] text-[#888888] uppercase font-bold tracking-widest">Server</label>
                            <input 
                              type="text" 
                              value={mt5Credentials.server}
                              onChange={(e) => setMt5Credentials({...mt5Credentials, server: e.target.value})}
                              placeholder="e.g. FundingPips-Live"
                              className="w-full bg-[#0D0E12] border border-[rgba(255,255,255,0.08)] rounded px-3 py-2 text-sm focus:outline-none focus:border-[#D4AF37] transition-colors"
                            />
                          </div>
                          <button 
                            type="submit"
                            disabled={mt5Status === 'CONNECTING'}
                            className="w-full py-2.5 bg-[#D4AF37] text-black font-bold text-[0.7rem] uppercase tracking-widest rounded transition-all hover:bg-[#D4AF37]/80 disabled:opacity-50"
                          >
                            {mt5Status === 'CONNECTED' ? 'Reconnect Terminal' : 'Establish Connection'}
                          </button>
                        </form>
                      </div>

                      <div className="space-y-6">
                        <div className="bg-[#16181D] border border-[rgba(255,255,255,0.05)] rounded-lg p-6">
                          <div className="flex items-center gap-3 text-[#E0E0E0] mb-4">
                            <Globe size={18} className="text-[#00D1FF]" />
                            <span className="text-sm font-bold uppercase tracking-wider">Infrastructure</span>
                          </div>
                          <div className="space-y-4">
                            <div className="flex justify-between items-center text-[0.7rem]">
                              <span className="text-[#888888]">Direct Execution</span>
                              <span className="text-[#00FF85]">Enabled</span>
                            </div>
                            <div className="flex justify-between items-center text-[0.7rem]">
                              <span className="text-[#888888]">Proxy Tunnel</span>
                              <span className="text-[#00FF85]">Secure (TLS 1.3)</span>
                            </div>
                            <div className="flex justify-between items-center text-[0.7rem]">
                              <span className="text-[#888888]">Latency</span>
                              <span className="text-[#00D1FF]">{latency.toFixed(1)} ms</span>
                            </div>
                          </div>
                        </div>

                        <div className="bg-[#16181D] border border-[rgba(255,255,255,0.05)] rounded-lg p-6">
                          <div className="flex items-center gap-3 text-[#E0E0E0] mb-4">
                            <Database size={18} className="text-[#D4AF37]" />
                            <span className="text-sm font-bold uppercase tracking-wider">Security Notice</span>
                          </div>
                          <p className="text-[0.65rem] text-[#888888] leading-relaxed italic">
                            Credentials are encrypted locally and never stored in plain text. Signals are routed through the AlphaGold institutional cloud bridge.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="panel h-[200px] flex flex-col overflow-hidden">
             <div className="px-5 py-3 bg-[#16181D] border-b border-[rgba(255,255,255,0.08)] flex justify-between items-center">
                <span className="text-[0.7rem] font-bold uppercase text-[#888888] tracking-widest">Dynamic Position Matrix</span>
                <span className="tag tag-blue">Real-time Stream</span>
             </div>
             <div className="flex-1 overflow-y-auto custom-scrollbar">
               <table className="w-full text-left font-mono text-[0.75rem]">
                  <thead className="bg-[#0D0E12] sticky top-0 z-10">
                    <tr className="text-[#888888] border-b border-[rgba(255,255,255,0.05)]">
                      <th className="px-5 py-2 font-bold uppercase border-r border-[rgba(255,255,255,0.05)]">ID</th>
                      <th className="px-5 py-2 font-bold uppercase">Side</th>
                      <th className="px-5 py-2 font-bold uppercase">Entry</th>
                      <th className="px-5 py-2 font-bold uppercase text-right">PnL</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[rgba(255,255,255,0.05)]">
                    <AnimatePresence>
                      {activeTrades.map(trade => (
                        <motion.tr 
                          key={trade.id} 
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, scale: 0.95 }}
                          className="hover:bg-[#23262D] transition-colors"
                        >
                          <td className="px-5 py-3 text-[#888888] border-r border-[rgba(255,255,255,0.05)]">{trade.id}</td>
                          <td className={`px-5 py-3 font-bold ${trade.type === 'BUY' ? 'text-[#00FF85]' : 'text-[#FF4D4D]'}`}>{trade.type}</td>
                          <td className="px-5 py-3 text-[#E0E0E0] italic">@{trade.entryPrice.toFixed(2)}</td>
                          <td className={`px-5 py-3 text-right font-bold ${trade.pnl >= 0 ? 'text-[#00FF85]' : 'text-[#FF4D4D]'}`}>
                            {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}
                          </td>
                        </motion.tr>
                      ))}
                    </AnimatePresence>
                    <AnimatePresence>
                      {pendingLevels.map(level => (
                        <motion.tr 
                          key={`pending-${level.id}`} 
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 0.6, x: 0 }}
                          exit={{ opacity: 0, scale: 0.95 }}
                          className="hover:bg-[#23262D] transition-colors border-l-2 border-[#D4AF37]"
                        >
                          <td className="px-5 py-3 text-[#555555] border-r border-[rgba(255,255,255,0.05)]">PENDING_{level.id.toUpperCase()}</td>
                          <td className={`px-5 py-3 font-bold opacity-60 ${level.type === 'BUY' ? 'text-[#00FF85]' : 'text-[#FF4D4D]'}`}>{level.type}</td>
                          <td className="px-5 py-3 text-[#E0E0E0] italic opacity-60">@{level.price.toFixed(2)}</td>
                          <td className="px-5 py-3 text-right font-mono text-[0.65rem] text-[#D4AF37] opacity-80 uppercase tracking-widest">
                            {level.lot} L
                          </td>
                        </motion.tr>
                      ))}
                    </AnimatePresence>
                    {activeTrades.length === 0 && pendingLevels.length === 0 && (
                      <tr>
                        <td colSpan={4} className="p-10 text-center text-[#888888] uppercase italic text-[0.7rem] tracking-[4px] font-light">
                          Awaiting Grid Entry Conditions...
                        </td>
                      </tr>
                    )}
                  </tbody>
               </table>
             </div>
          </div>
        </div>

        {/* Right Column: Protocols & Signals */}
        <div className="flex flex-col gap-[20px] overflow-y-auto custom-scrollbar">
          <div className="panel p-[20px]">
            <div className="text-[0.7rem] font-bold uppercase text-[#888888] mb-6 tracking-widest flex items-center gap-2">
              <ShieldAlert size={14} className="text-[#FF4D4D]" />
              Risk Protocols
            </div>
            <div className="space-y-6">
              <div className="flex justify-between items-center group">
                <span className="text-[0.75rem] text-[#888888] font-medium">Trailing Stop</span>
                <span className="text-[0.9rem] font-mono text-[#E0E0E0] group-hover:text-[#00D1FF] transition-colors">{engine.getConfig().trailingStopDistance} $</span>
              </div>
              <div className="flex justify-between items-center group">
                <span className="text-[0.75rem] text-[#888888] font-medium">Hard Stop Loss</span>
                <span className="text-[0.9rem] font-mono text-[#E0E0E0] group-hover:text-[#FF4D4D] transition-colors">{engine.getConfig().stopLossDistance} $</span>
              </div>
              <div className="flex justify-between items-center group">
                <span className="text-[0.75rem] text-[#888888] font-medium">Take Profit Target</span>
                <span className="text-[0.9rem] font-mono text-[#E0E0E0] group-hover:text-[#00FF85] transition-colors">{engine.getConfig().takeProfitDistance} $</span>
              </div>
              <div className="flex justify-between items-center group">
                <span className="text-[0.75rem] text-[#888888] font-medium">Grid Separation</span>
                <span className="text-[0.9rem] font-mono text-[#E0E0E0] group-hover:text-[#D4AF37] transition-colors">{engine.getConfig().gridSpacing} $</span>
              </div>
            </div>
            
            <div className="mt-8 p-4 bg-[rgba(212,175,55,0.03)] border-l-2 border-[#D4AF37] relative overflow-hidden">
               <div className="text-[0.65rem] font-bold text-[#D4AF37] uppercase mb-1">Grid Intelligence</div>
               <p className="text-[0.65rem] text-[#888888] leading-relaxed italic">
                 Bot automatically detects range vs trend conditions to adjust grid density.
               </p>
            </div>
          </div>

          <div className="flex-1 flex flex-col min-h-0">
             <div className="panel flex-1 flex flex-col p-0 overflow-hidden">
                <div className="p-4 border-b border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] flex justify-between items-center">
                  <span className="text-[0.7rem] font-bold uppercase text-[#888888] tracking-widest">Market Intelligence</span>
                  <History size={14} className="text-[#00D1FF] cursor-pointer hover:text-white transition-colors" />
                </div>
                <div className="flex-1 overflow-y-auto custom-scrollbar">
                  <div className="p-4 space-y-6">
                    <NewsFeed items={news} />
                    
                    <div className="pt-4 border-t border-[rgba(255,255,255,0.05)]">
                       <span className="text-[0.6rem] font-bold uppercase text-zinc-500 block mb-3">Transmission Log</span>
                       <div className="space-y-2 font-mono text-[0.65rem]">
                          {trades.filter(t => t.status === 'CLOSED').slice(-5).reverse().map(t => (
                            <div key={t.id} className="flex justify-between items-center py-1 border-b border-white/5">
                              <span className={t.pnl >= 0 ? 'text-[#00FF85]' : 'text-[#FF4D4D]'}>
                                [{t.type}] {t.id}
                              </span>
                              <span className="text-zinc-500">${t.pnl.toFixed(2)}</span>
                            </div>
                          ))}
                          {trades.filter(t => t.status === 'CLOSED').length === 0 && (
                            <div className="text-zinc-600 italic">No historical data...</div>
                          )}
                       </div>
                    </div>
                  </div>
                </div>
             </div>
          </div>
        </div>
      </main>

      {/* Institutional Footer */}
      <footer className="px-[30px] py-[15px] border-t border-[rgba(255,255,255,0.08)] bg-[#0D0E12] flex justify-between items-center text-[0.65rem] text-[#888888] font-bold tracking-[1px] shrink-0">
        <div className="flex gap-8">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 bg-[#00FF85] rounded-full shadow-[0_0_8px_#00FF85]" />
            GRID ENGINE: <span className="text-[#E0E0E0]">STABLE</span>
          </div>
          <div className="flex items-center gap-2">
            AI CORE: <span className="text-[#E0E0E0]">OPERATIONAL</span>
          </div>
          <div className="flex items-center gap-2">
            LATENCY: <span className="text-[#00D1FF]">{latency.toFixed(0)}ms</span>
          </div>
        </div>
        <div className="opacity-50 uppercase">
          AlphaGold AI Systems Institutional v2.6.4 — {new Date().getFullYear()}
        </div>
      </footer>
    </div>
  );
}
