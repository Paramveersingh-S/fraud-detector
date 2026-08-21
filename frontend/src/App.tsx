import React, { useState, useEffect, useCallback } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { 
  ShieldAlert, ShieldCheck, Activity, Brain, Server, Target, LayoutDashboard, Settings2, Shield
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceLine
} from 'recharts';

const SOCKET_URL = 'ws://localhost:8000/ws/feed';
const API_URL = 'http://localhost:8000';

interface Reason {
  feature: string;
  contribution: number;
}

interface Transaction {
  TransactionID: string;
  TransactionAmt: number;
  card1: number;
  addr1: number;
}

interface FlaggedEvent {
  txn: Transaction;
  score: number;
  reasons: Reason[];
  anomaly_score: number;
  expected_risk: number;
}

interface ChartDataPoint {
  time: string;
  score: number;
  amt: number;
}

function App() {
  const [feed, setFeed] = useState<FlaggedEvent[]>([]);
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
  const [threshold, setThreshold] = useState<number>(0.5);
  const [selectedTxn, setSelectedTxn] = useState<FlaggedEvent | null>(null);

  const { lastMessage, readyState } = useWebSocket(SOCKET_URL, {
    shouldReconnect: (closeEvent) => true,
    reconnectInterval: 3000,
  });

  useEffect(() => {
    // Fetch initial threshold
    fetch(`${API_URL}/v1/threshold`)
      .then(res => res.json())
      .then(data => setThreshold(data.threshold))
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (lastMessage !== null) {
      try {
        const data: FlaggedEvent = JSON.parse(lastMessage.data);
        setFeed(prev => [data, ...prev].slice(0, 100)); // Keep last 100
        
        setChartData(prev => {
          const now = new Date();
          const newPoint = {
            time: now.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            score: data.score,
            amt: data.txn.TransactionAmt
          };
          return [...prev, newPoint].slice(-30); // Keep last 30 for chart
        });
      } catch (e) {
        console.error("Failed to parse websocket message", e);
      }
    }
  }, [lastMessage]);

  const updateThreshold = async (newThreshold: number) => {
    try {
      await fetch(`${API_URL}/v1/threshold`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ threshold: newThreshold })
      });
      setThreshold(newThreshold);
    } catch (e) {
      console.error(e);
    }
  };

  const connectionStatus = {
    [ReadyState.CONNECTING]: 'Connecting',
    [ReadyState.OPEN]: 'Live',
    [ReadyState.CLOSING]: 'Closing',
    [ReadyState.CLOSED]: 'Disconnected',
    [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
  }[readyState];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-blue-900">
      {/* Navbar */}
      <nav className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <ShieldAlert className="w-8 h-8 text-red-500" />
            <span className="text-xl font-bold tracking-wide text-white">Fraud-Spike <span className="text-blue-500">Detector</span></span>
          </div>
          <div className="flex items-center space-x-6 text-sm">
            <div className="flex items-center space-x-2">
              <Server className="w-4 h-4 text-slate-400" />
              <span className="text-slate-400">Stream Status:</span>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${readyState === ReadyState.OPEN ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'}`}>
                {connectionStatus}
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-slate-400" />
              <span className="text-slate-400">Total Flagged:</span>
              <span className="font-mono text-white">{feed.length}</span>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 py-8 grid grid-cols-12 gap-6">
        
        {/* Left Column: Feed */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl">
            <div className="flex items-center space-x-2 mb-4">
              <Target className="w-5 h-5 text-blue-400" />
              <h2 className="text-lg font-semibold text-white">Live Anomalies</h2>
            </div>
            
            <div className="space-y-3 h-[600px] overflow-y-auto pr-2 custom-scrollbar">
              {feed.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-500 space-y-4">
                  <ShieldCheck className="w-12 h-12 opacity-50" />
                  <p>Listening for fraud spikes...</p>
                </div>
              ) : (
                feed.map((event, idx) => (
                  <div 
                    key={idx} 
                    onClick={() => setSelectedTxn(event)}
                    className="p-4 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:bg-slate-800 hover:border-blue-500/50 cursor-pointer transition-all duration-200 group"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-mono text-xs text-slate-400">#{event.txn.TransactionID}</span>
                      <div className="flex space-x-2">
                        <span className="px-2 py-1 rounded bg-red-500/10 text-red-400 text-xs font-bold border border-red-500/20" title="Supervised Probability">
                          P: {event.score.toFixed(3)}
                        </span>
                        <span className="px-2 py-1 rounded bg-purple-500/10 text-purple-400 text-xs font-bold border border-purple-500/20" title="Isolation Forest Score">
                          Z: {event.anomaly_score?.toFixed(3) ?? '0.000'}
                        </span>
                      </div>
                    </div>
                    <div className="flex justify-between items-baseline mt-2">
                      <div className="flex flex-col">
                        <span className="text-lg font-medium text-white">${event.txn.TransactionAmt.toFixed(2)}</span>
                        <span className="text-xs font-mono text-orange-400" title="Expected Financial Risk">Risk: ${(event.expected_risk || 0).toFixed(2)}</span>
                      </div>
                      <span className="text-xs text-slate-400 flex items-center group-hover:text-blue-400 transition-colors ml-auto">
                        View SHAP &rarr;
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Analytics & Control */}
        <div className="col-span-12 lg:col-span-8 space-y-6">
          
          {/* Rules Engine Control */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white flex items-center space-x-2">
                <Settings2 className="w-5 h-5 text-blue-400" />
                <span>Dynamic Rules Engine</span>
              </h2>
              <p className="text-sm text-slate-400 mt-1">Adjust the live probability threshold for blocking transactions.</p>
            </div>
            <div className="flex items-center space-x-4">
              <span className="font-mono text-xl text-white">{threshold.toFixed(2)}</span>
              <input 
                type="range" 
                min="0.01" max="0.99" step="0.01" 
                value={threshold}
                onChange={(e) => updateThreshold(parseFloat(e.target.value))}
                className="w-48 accent-blue-500 cursor-pointer"
              />
            </div>
          </div>

          {/* Real-time Chart */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
             <div className="flex items-center space-x-2 mb-6">
              <Activity className="w-5 h-5 text-blue-400" />
              <h2 className="text-lg font-semibold text-white">Score Trajectory (Flagged)</h2>
            </div>
            <div className="h-64 w-full">
              <ResponsiveContainer>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                  <XAxis dataKey="time" stroke="#64748b" fontSize={12} tickMargin={10} />
                  <YAxis stroke="#64748b" fontSize={12} domain={[0, 1]} />
                  <RechartsTooltip 
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc' }}
                    itemStyle={{ color: '#60a5fa' }}
                  />
                  <ReferenceLine y={threshold} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'insideTopLeft', value: 'Threshold', fill: '#ef4444', fontSize: 12 }} />
                  <Line type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={3} dot={{ r: 4, fill: '#3b82f6', strokeWidth: 0 }} activeDot={{ r: 6, fill: '#60a5fa' }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* SHAP Explanation Panel */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl h-[280px]">
             <div className="flex items-center space-x-2 mb-4">
              <Brain className="w-5 h-5 text-blue-400" />
              <h2 className="text-lg font-semibold text-white">AI Reasoning (SHAP)</h2>
            </div>
            {selectedTxn ? (
              <div className="space-y-4">
                <div className="flex justify-between items-center pb-3 border-b border-slate-800">
                  <span className="text-slate-400">Transaction ID: <span className="font-mono text-white">{selectedTxn.txn.TransactionID}</span></span>
                  <span className="text-slate-400">Score: <span className="font-mono text-red-400">{selectedTxn.score.toFixed(4)}</span></span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  {selectedTxn.reasons.slice(0,4).map((r, i) => (
                    <div key={i} className="flex justify-between items-center p-3 rounded bg-slate-800/50">
                      <span className="font-mono text-sm text-blue-300">{r.feature}</span>
                      <span className={`font-mono text-sm ${r.contribution > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                        {r.contribution > 0 ? '+' : ''}{r.contribution.toFixed(3)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-slate-500 pb-8">
                <p>Select a transaction from the feed to view AI explanations.</p>
              </div>
            )}
          </div>

        </div>
      </main>
    </div>
  );
}

export default App;
