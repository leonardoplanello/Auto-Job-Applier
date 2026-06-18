import React from 'react';
import { useBot } from '../hooks/useBot';
import api from '../lib/api';
import { Play, Pause, Square, Loader2, SkipForward } from 'lucide-react';

export const BotStatusBar: React.FC = () => {
  const { status, currentJob } = useBot();

  if (status === 'stopped' || status === 'idle' || status === 'finished') {
    return null;
  }

  const handlePause = async () => {
    try {
      await api.post('/api/bot/pause');
    } catch (err) {
      console.error('Failed to pause bot:', err);
    }
  };

  const handleResume = async () => {
    try {
      await api.post('/api/bot/resume');
    } catch (err) {
      console.error('Failed to resume bot:', err);
    }
  };

  const handleStop = async () => {
    try {
      await api.post('/api/bot/stop');
    } catch (err) {
      console.error('Failed to stop bot:', err);
    }
  };

  const handleSkip = async () => {
    if (!currentJob?.id) return;
    try {
      await api.post(`/api/jobs/${currentJob.id}/skip`, { reason: 'Skipped manually from dashboard' });
    } catch (err) {
      console.error('Failed to skip job:', err);
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'idle':
        return 'bg-slate-100 text-slate-500 border-slate-200';
      case 'running':
      case 'applying':
      case 'searching':
        return 'bg-primary-50 text-primary-700 border-primary-200';
      case 'paused':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'waiting_login':
      case 'waiting_user':
      case 'review_pending':
        return 'bg-cyan-50 text-cyan-700 border-cyan-200';
      case 'finished':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'stopped':
        return 'bg-red-50 text-red-700 border-red-200';
      default:
        return 'bg-slate-100 text-slate-500 border-slate-200';
    }
  };

  const getStatusLabel = () => {
    switch (status) {
      case 'idle': return 'Idle';
      case 'running': return 'Running';
      case 'checking_auth': return 'Checking Login';
      case 'waiting_login': return 'Waiting Login';
      case 'searching': return 'Searching Jobs';
      case 'queued': return 'Queued';
      case 'review_pending': return 'Review Pending';
      case 'applying': return 'Applying';
      case 'waiting_user': return 'Waiting User';
      case 'finished': return 'Finished';
      case 'stopped': return 'Stopped';
      case 'paused': return 'Paused';
      default: return status;
    }
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-4 glass-panel border-slate-200 mb-6">
      <div className="flex items-center gap-3">
        {/* Status Indicator */}
        <div className={`flex items-center gap-2 px-3 py-1 text-xs font-semibold rounded-full border ${getStatusColor()}`}>
          {['running', 'applying', 'searching', 'checking_auth'].includes(status) && (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          )}
          <span>{getStatusLabel()}</span>
        </div>

        {/* Current Job Display */}
        {currentJob && status !== 'idle' && (
          <div className="text-sm">
            <span className="text-slate-500 font-medium">Processing: </span>
            <span className="font-bold text-slate-800">{currentJob.title}</span>
            <span className="text-slate-500"> @ {currentJob.company}</span>
          </div>
        )}
      </div>

      {/* Control Actions */}
      {status !== 'idle' && status !== 'finished' && status !== 'stopped' && (
        <div className="flex items-center gap-2">
          {status === 'paused' ? (
            <button
              onClick={handleResume}
              className="glass-btn bg-primary-600 hover:bg-primary-500 text-white text-xs px-3 py-1.5"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              Resume
            </button>
          ) : (
            <button
              onClick={handlePause}
              className="glass-btn bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 text-xs px-3 py-1.5"
            >
              <Pause className="w-3.5 h-3.5" />
              Pause
            </button>
          )}

          {currentJob && (
            <button
              onClick={handleSkip}
              className="glass-btn bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs px-3 py-1.5"
            >
              <SkipForward className="w-3.5 h-3.5" />
              Skip Job
            </button>
          )}
          
          <button
            onClick={handleStop}
            className="glass-btn bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 text-xs px-3 py-1.5"
          >
            <Square className="w-3.5 h-3.5 fill-current" />
            Stop
          </button>
        </div>
      )}
    </div>
  );
};
