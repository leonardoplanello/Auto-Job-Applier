import React from 'react';
import { useBot, type LogEntry as LogType } from '../hooks/useBot';
import { CheckCircle2, XCircle, AlertTriangle, Info, HelpCircle } from 'lucide-react';

interface LogEntryProps {
  log: LogType;
}

export const LogEntry: React.FC<LogEntryProps> = ({ log }) => {
  const { setCurrentPage, setJobSearchQuery, setJobStatusFilter } = useBot();

  const handleViewInDashboard = () => {
    setCurrentPage('jobs');
    setJobStatusFilter('all');
    if (log.job_title) {
      setJobSearchQuery(log.job_title);
    } else if (log.company) {
      setJobSearchQuery(log.company);
    }
  };

  const getIcon = () => {
    switch (log.level) {
      case 'success':
        return <CheckCircle2 className="w-4 h-4 text-emerald-600" />;
      case 'error':
        return <XCircle className="w-4 h-4 text-red-600" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-amber-600" />;
      case 'action':
        return <HelpCircle className="w-4 h-4 text-cyan-600" />;
      case 'info':
      default:
        return <Info className="w-4 h-4 text-slate-500" />;
    }
  };

  const getLogColor = () => {
    switch (log.level) {
      case 'success': return 'text-emerald-700 font-medium';
      case 'error': return 'text-red-700 font-medium';
      case 'warning': return 'text-amber-700 font-medium';
      case 'action': return 'text-cyan-700 font-semibold';
      case 'info':
      default:
        return 'text-slate-700';
    }
  };

  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-200/80 hover:bg-slate-100/50 hover:border-slate-300 transition-all duration-150 text-xs leading-normal">
      <div className="flex-shrink-0 mt-0.5">{getIcon()}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-slate-400 font-mono font-medium">{formatTime(log.timestamp)}</span>
          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wide uppercase bg-slate-200/60 text-slate-600 border border-slate-300/40">
            {log.category}
          </span>
          {log.company && (
            <span className="text-[9px] px-1.5 py-0.5 rounded font-bold bg-primary-50 text-primary-700 border border-primary-100">
              {log.company}
            </span>
          )}
        </div>
        <p className={`${getLogColor()} break-words`}>{log.message}</p>
        
        <div className="flex flex-wrap items-center gap-2 mt-1">
          {log.job_url && (
            <a
              href={log.job_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] text-primary-600 hover:text-primary-800 underline font-medium"
            >
              View on LinkedIn
            </a>
          )}
          {log.job_url && (log.job_title || log.company) && (
            <span className="text-[10px] text-slate-300 select-none">•</span>
          )}
          {(log.job_title || log.company) && (
            <button
              onClick={handleViewInDashboard}
              className="text-[10px] text-primary-600 hover:text-primary-800 underline font-medium cursor-pointer bg-transparent border-none p-0"
            >
              View in Dashboard
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
