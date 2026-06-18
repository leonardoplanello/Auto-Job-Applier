import React, { useEffect, useState } from 'react';
import api, { API_BASE_URL } from '../lib/api';
import { LogEntry } from '../components/LogEntry';
import type { LogEntry as LogType } from '../hooks/useBot';
import { Download, Search, RefreshCw, FileText } from 'lucide-react';

interface SessionData {
  id: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  jobs_applied: number;
}

export const Logs: React.FC = () => {
  const [logsList, setLogsList] = useState<LogType[]>([]);
  const [sessions, setSessions] = useState<SessionData[]>([]);
  const [selectedSession, setSelectedSession] = useState<string>('');
  const [levelFilter, setLevelFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const fetchSessions = async () => {
    try {
      const res = await api.get('/api/logs/sessions');
      setSessions(res.data);
      if (res.data.length > 0 && !selectedSession) {
        setSelectedSession(res.data[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch sessions list:', err);
    }
  };

  const fetchLogs = async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/api/logs', {
        params: {
          level: levelFilter || undefined,
          category: categoryFilter || undefined,
          session_id: selectedSession || undefined
        }
      });
      setLogsList(res.data);
    } catch (err) {
      console.error('Failed to load logs:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [selectedSession, levelFilter, categoryFilter]);

  const filteredLogs = logsList.filter((log) => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return true;
    return (
      log.message.toLowerCase().includes(q) ||
      (log.company && log.company.toLowerCase().includes(q)) ||
      (log.job_title && log.job_title.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6">
      
      {/* Filters Header Bar */}
      <div className="p-6 glass-panel border-slate-200 space-y-4 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-bold text-slate-800 uppercase tracking-wider">Sessions & Logs History</h2>
            <p className="text-xs text-slate-500 mt-0.5">Explore previous bot executions and debug details.</p>
          </div>
          
          {selectedSession && (
            <a
              href={`${API_BASE_URL}/api/logs/export?session_id=${selectedSession}`}
              download
              className="glass-btn-secondary py-2 text-xs"
            >
              <Download className="w-3.5 h-3.5" />
              Export Session (CSV)
            </a>
          )}
        </div>

        <hr className="border-slate-100" />

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          
          {/* Select Session ID */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold text-slate-500 uppercase">Session</label>
            <select
              value={selectedSession}
              onChange={(e) => setSelectedSession(e.target.value)}
              className="w-full glass-input text-xs bg-white text-slate-800"
            >
              <option value="">All Sessions</option>
              {sessions.map((s) => (
                <option key={s.id} value={s.id} className="text-slate-800">
                  {new Date(s.started_at).toLocaleString()} - {s.id.substring(0, 8)} ({s.status})
                </option>
              ))}
            </select>
          </div>

          {/* Severity Filter */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold text-slate-500 uppercase">Severity</label>
            <select
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
              className="w-full glass-input text-xs bg-white text-slate-800"
            >
              <option value="">All Severities</option>
              <option value="success">Success</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
              <option value="action">Manual Action</option>
              <option value="debug">Debug</option>
            </select>
          </div>

          {/* Category Filter */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold text-slate-500 uppercase">Category</label>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="w-full glass-input text-xs bg-white text-slate-800"
            >
              <option value="">All Categories</option>
              <option value="auth">Authentication</option>
              <option value="search">Job Search</option>
              <option value="apply">Job Application</option>
              <option value="qa">Q&A Questions</option>
              <option value="bot">Bot Engine</option>
              <option value="system">System</option>
            </select>
          </div>

          {/* Search Query */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold text-slate-500 uppercase">Filter Text</label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 flex items-center pl-2.5 text-slate-500">
                <Search className="w-3.5 h-3.5" />
              </span>
              <input
                type="text"
                placeholder="Search logs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full glass-input pl-8 text-xs text-slate-800 bg-white"
              />
            </div>
          </div>

        </div>
      </div>

      {/* Logs Table Area */}
      <div className="p-6 glass-panel border-slate-200 min-h-[360px] flex flex-col justify-between bg-white">
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <FileText className="w-4 h-4 text-primary-600" />
            Recorded Logs ({filteredLogs.length})
          </h3>
          <button
            onClick={fetchLogs}
            className="p-1 rounded text-slate-500 hover:text-slate-800"
            title="Reload Logs"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-2 max-h-[500px] pr-2">
          {isLoading ? (
            <div className="h-64 flex items-center justify-center text-slate-500 text-xs italic">
              Fetching execution logs...
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center text-center text-slate-500">
              <FileText className="w-12 h-12 text-slate-300 mb-3" />
              <p className="text-sm">No logs matched the active filters.</p>
            </div>
          ) : (
            filteredLogs.map((log) => (
              <LogEntry key={log.id} log={log} />
            ))
          )}
        </div>
      </div>

    </div>
  );
};
