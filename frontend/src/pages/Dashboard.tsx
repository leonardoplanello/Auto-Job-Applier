import React, { useEffect, useState, useRef } from 'react';
import { useBot, type Job } from '../hooks/useBot';
import { StatCard } from '../components/StatCard';
import { LogEntry } from '../components/LogEntry';
import api from '../lib/api';
import { 
  Briefcase, CheckCircle2, AlertCircle, XCircle, 
  HelpCircle, Play, Pause, Square, RefreshCw, Layers,
  ExternalLink, GripVertical, ListPlus, Zap, X, Clock
} from 'lucide-react';


export const Dashboard: React.FC = () => {
  const { status, stats, logs, currentJob, sessionId, setCurrentPage, setJobSearchQuery, setJobStatusFilter, jobsRefreshCounter } = useBot();
  const [tasks, setTasks] = useState<any[]>([]);
  const [queuedCount, setQueuedCount] = useState<number>(0);
  const [queuedJobsList, setQueuedJobsList] = useState<Job[]>([]);
  const [automationMode, setAutomationMode] = useState<'manual' | 'auto'>('manual');
  const [popupMode, setPopupMode] = useState<'web' | 'desktop'>('web');
  const [isLoading, setIsLoading] = useState(false);
  const [limitReached, setLimitReached] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);



  // Drag and drop states for queue
  const [draggingQueueIndex, setDraggingQueueIndex] = useState<number | null>(null);

  const handleQueueDragStart = (e: React.DragEvent, index: number) => {
    setDraggingQueueIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleQueueDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleQueueDragEnd = () => {
    setDraggingQueueIndex(null);
  };

  const handleQueueDrop = async (e: React.DragEvent, targetIndex: number) => {
    e.preventDefault();
    if (draggingQueueIndex === null || draggingQueueIndex === targetIndex) {
      setDraggingQueueIndex(null);
      return;
    }

    const visibleCount = currentJob ? 5 : 15;
    const visibleJobs = [...queuedJobsList].slice(0, visibleCount);
    
    const [movedItem] = visibleJobs.splice(draggingQueueIndex, 1);
    visibleJobs.splice(targetIndex, 0, movedItem);
    
    const restJobs = [...queuedJobsList].slice(visibleCount);
    const newQueuedJobsList = [...visibleJobs, ...restJobs];
    
    setQueuedJobsList(newQueuedJobsList);
    setDraggingQueueIndex(null);

    try {
      const orderedIds = visibleJobs.map(j => j.id);
      await api.post('/api/jobs/bulk/reorder', { job_ids: orderedIds });
      
      const now = Date.now();
      const total = orderedIds.length;
      setQueuedJobsList(prev => prev.map(j => {
        const idx = orderedIds.indexOf(j.id);
        if (idx !== -1) {
           return { ...j, priority: now + total - idx };
        }
        return j;
      }));
    } catch (err) {
      console.error('Failed to reorder jobs:', err);
    }
  };



  // Fetch search criteria list and settings on mount
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const res = await api.get('/api/settings');
        if (res.data) {
          if (res.data.popup_mode) {
            setPopupMode(res.data.popup_mode);
          }
          if (res.data.bot_mode) {
            setAutomationMode(res.data.bot_mode === 'auto' ? 'auto' : 'manual');
          }
          if (res.data.bot_tasks_sequence) {
            setTasks(JSON.parse(res.data.bot_tasks_sequence));
          } else {
            setTasks([{ type: 'process_queue', target: 'all' }]);
          }
        }
      } catch (err) {
        console.error('Failed to load settings:', err);
      }
    };
    fetchInitialData();
  }, []);

  // Fetch queued count whenever bot status changes
  useEffect(() => {
    const fetchQueuedCount = async () => {
      try {
        const res = await api.get('/api/jobs', { params: { status: 'queued', limit: 100 } });
        const sorted = res.data.sort((a: any, b: any) => {
          const priorityA = a.priority || 0;
          const priorityB = b.priority || 0;
          if (priorityA !== priorityB) {
            return priorityB - priorityA;
          }
          return new Date(a.discovered_at).getTime() - new Date(b.discovered_at).getTime();
        });
        setQueuedCount(sorted.length);
        setQueuedJobsList(sorted);
      } catch (err) {
        console.error('Failed to load queued jobs count:', err);
      }
    };
    fetchQueuedCount();
  }, [status, jobsRefreshCounter]);

  // Fetch settings when bot status changes to checked/stopped/finished to see if limit is reached
  useEffect(() => {
    const checkLimitSetting = async () => {
      try {
        const res = await api.get('/api/settings');
        if (res.data && res.data.easy_apply_limit_reached === 'true') {
          setLimitReached(true);
        } else {
          setLimitReached(false);
        }
      } catch (err) {
        console.error('Failed to refresh settings:', err);
      }
    };
    checkLimitSetting();
  }, [status]);

  const handlePopupModeChange = async (mode: 'web' | 'desktop') => {
    setPopupMode(mode);
    try {
      await api.put(`/api/settings/popup_mode`, { value: mode });
    } catch (err) {
      console.error('Failed to update popup mode:', err);
    }
  };

  const handleAutomationModeChange = async (mode: 'manual' | 'auto') => {
    setAutomationMode(mode);
    const apiMode = mode === 'manual' ? 'review' : 'auto';
    try {
      await api.put(`/api/settings/bot_mode`, { value: apiMode });
    } catch (err) {
      console.error('Failed to update automation mode:', err);
    }
  };

  // Auto scroll logs container to bottom on new log additions
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = 0; // New logs are appended at the top of useBot array
    }
  }, [logs]);

  const handleStartBot = async () => {
    if (tasks.length === 0) {
      alert('Please configure at least one task in the Tasks Sequence to start.');
      return;
    }
    setIsLoading(true);
    setLimitReached(false);

    try {
      await api.post('/api/bot/start', {
        tasks: tasks,
        mode: automationMode === 'manual' ? 'review' : 'auto'
      });
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to start the bot.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStopBot = async () => {
    setIsLoading(true);
    try {
      await api.post('/api/bot/stop');
    } catch (err) {
      console.error('Failed to stop bot:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePauseBot = async () => {
    setIsLoading(true);
    try {
      await api.post('/api/bot/pause');
    } catch (err) {
      console.error('Failed to pause bot:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResumeBot = async () => {
    setIsLoading(true);
    try {
      await api.post('/api/bot/resume');
    } catch (err) {
      console.error('Failed to resume bot:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenLogWindow = async () => {
    try {
      await api.post('/api/logs/open-window', null, {
        params: { session_id: sessionId }
      });
    } catch (err) {
      console.error('Failed to open log window:', err);
    }
  };

  const isBotActive = !['idle', 'stopped', 'finished'].includes(status);

  return (
    <div className="space-y-6">
      
      {limitReached && (
        <div className="p-5 border border-amber-200 bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl shadow-sm transition-all duration-300 flex items-start gap-4">
          <div className="p-2 bg-amber-100 text-amber-700 rounded-lg flex-shrink-0 animate-pulse">
            <AlertCircle className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h4 className="text-base font-bold text-amber-900">
              You reached today’s Easy Apply limit
            </h4>
            <p className="text-sm text-amber-700 leading-relaxed font-medium">
              Great effort applying today. We limit Easy Apply submissions to help ensure each application gets the right attention. Save this job and continue applying tomorrow. <a href="https://www.linkedin.com/help/linkedin/answer/a519888" target="_blank" rel="noopener noreferrer" className="underline font-bold hover:text-amber-900 transition-colors">Learn more</a>
            </p>
          </div>
        </div>
      )}

      {/* Session Control Panel */}
      <div className="p-6 glass-panel border-slate-200">
        <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
          <Layers className="w-5 h-5 text-primary-600" />
          Automation Control
        </h3>
        
        <div className="flex flex-wrap items-end gap-6">
          {/* Compressed Tasks Sequence View */}
          <div className="flex-1 min-w-[280px] space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-400 uppercase block">Tasks Sequence</label>
              <button 
                onClick={() => setCurrentPage('tasks')}
                className="text-[10px] font-bold text-primary-600 hover:text-primary-800 uppercase tracking-wider"
              >
                Edit Tasks
              </button>
            </div>
            
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 min-h-[38px] flex items-center justify-between">
              <div className="flex flex-col gap-1 w-full">
                {tasks.length === 0 ? (
                  <span className="text-xs text-slate-500 italic">No tasks configured.</span>
                ) : (
                  <>
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
                      <span className="bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded text-[10px]">{tasks.length}</span>
                      <span>Task(s) configured to run in order</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-[10px] text-slate-500 truncate">
                      {tasks.slice(0, 2).map((t, i) => (
                        <span key={i} className="flex items-center gap-1">
                          {i > 0 && <span>→</span>}
                          <span className="bg-white border border-slate-200 px-1.5 py-0.5 rounded truncate max-w-[120px]">
                            {t.type === 'process_queue' ? `Queue (${t.target})` : 'Search'}
                          </span>
                        </span>
                      ))}
                      {tasks.length > 2 && <span className="text-slate-400">+{tasks.length - 2} more</span>}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Automation Mode */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-400 uppercase block">Automation Mode</label>
            <div className="flex bg-slate-100 p-1 border border-slate-200 rounded-lg">
              <button
                disabled={isBotActive}
                onClick={() => handleAutomationModeChange('manual')}
                className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                  automationMode === 'manual'
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                Manual Review
              </button>
              <button
                disabled={isBotActive}
                onClick={() => handleAutomationModeChange('auto')}
                className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                  automationMode === 'auto'
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                100% Automatic
              </button>
            </div>
          </div>

          {/* Popup Mode */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-400 uppercase block">Popup Mode</label>
            <div className="flex bg-slate-100 p-1 border border-slate-200 rounded-lg">
              <button
                disabled={isBotActive}
                onClick={() => handlePopupModeChange('web')}
                className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                  popupMode === 'web'
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                Web Only
              </button>
              <button
                disabled={isBotActive}
                onClick={() => handlePopupModeChange('desktop')}
                className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                  popupMode === 'desktop'
                    ? 'bg-primary-600 text-white shadow-sm'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                Desktop (Python)
              </button>
            </div>
          </div>

          {/* Action Button */}
          <div className="flex items-center gap-2">
            {isBotActive ? (
              <>
                {status === 'paused' ? (
                  <button
                    disabled={isLoading}
                    onClick={handleResumeBot}
                    className="glass-btn-primary py-2.5 px-6 font-semibold"
                  >
                    <Play className="w-4 h-4 fill-current" />
                    Resume Session
                  </button>
                ) : (
                  <button
                    disabled={isLoading}
                    onClick={handlePauseBot}
                    className="glass-btn bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 py-2.5 px-6 font-semibold"
                  >
                    <Pause className="w-4 h-4" />
                    Pause Session
                  </button>
                )}
                <button
                  disabled={isLoading}
                  onClick={handleStopBot}
                  className="glass-btn-danger py-2.5 px-6 font-semibold"
                >
                  <Square className="w-4 h-4 fill-current" />
                  Stop Automation
                </button>
              </>
            ) : (
              <button
                disabled={isLoading || tasks.length === 0}
                onClick={handleStartBot}
                className="glass-btn-primary py-2.5 px-6 font-semibold"
              >
                <Play className="w-4 h-4 fill-current" />
                Start Session
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
        <StatCard
          title="Discovered"
          value={stats.found}
          icon={<Briefcase className="w-5 h-5" />}
          colorClass="text-blue-600 bg-blue-50 border-blue-200"
          onClick={() => {
            setCurrentPage('jobs');
            setJobStatusFilter('discovered');
          }}
        />
        <StatCard
          title="Pending"
          value={queuedCount}
          icon={<Clock className="w-5 h-5" />}
          colorClass="text-purple-600 bg-purple-50 border-purple-200"
          onClick={() => {
            setCurrentPage('jobs');
            setJobStatusFilter('queued');
          }}
        />
        <StatCard
          title="Applied"
          value={stats.applied}
          icon={<CheckCircle2 className="w-5 h-5" />}
          colorClass="text-emerald-600 bg-emerald-50 border-emerald-200"
          onClick={() => {
            setCurrentPage('jobs');
            setJobStatusFilter('applied');
          }}
        />
        <StatCard
          title="Skipped"
          value={stats.skipped}
          icon={<AlertCircle className="w-5 h-5" />}
          colorClass="text-amber-600 bg-amber-50 border-amber-200"
          onClick={() => {
            setCurrentPage('jobs');
            setJobStatusFilter('skipped');
          }}
        />
        <StatCard
          title="Failed"
          value={stats.failed}
          icon={<XCircle className="w-5 h-5" />}
          colorClass="text-red-600 bg-red-50 border-red-200"
          onClick={() => {
            setCurrentPage('jobs');
            setJobStatusFilter('failed');
          }}
        />
        <StatCard
          title="Popups Shown"
          value={stats.popups}
          icon={<HelpCircle className="w-5 h-5" />}
          colorClass="text-cyan-600 bg-cyan-50 border-cyan-200"
        />
      </div>

      {/* Logging & Active Job Details Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Logs Feed Column */}
        <div className="lg:col-span-2 p-6 glass-panel border-slate-200 flex flex-col h-[480px]">
          <div className="flex items-center justify-between mb-4 flex-shrink-0">
            <div className="flex items-center gap-3">
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                <RefreshCw className={`w-4 h-4 text-primary-600 ${isBotActive ? 'animate-spin' : ''}`} />
                Real-time Logs Console
              </h3>
              <button
                onClick={handleOpenLogWindow}
                className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-semibold text-primary-600 bg-primary-50 hover:bg-primary-100 border border-primary-200 rounded transition"
                title="Open logs in a separate Python desktop window"
              >
                <ExternalLink className="w-3 h-3" />
                Open Window
              </button>
            </div>
            <span className="text-[10px] text-slate-400 font-semibold">Showing last 300 entries</span>
          </div>

          <div 
            ref={logContainerRef}
            className="flex-1 overflow-y-auto space-y-2 pr-2"
          >
            {logs.length === 0 ? (
              <div className="h-full flex items-center justify-center text-slate-400 text-xs italic">
                No logs recorded in this session. Click "Start Session" to begin.
              </div>
            ) : (
              logs.map((log) => (
                <LogEntry key={log.id} log={log} />
              ))
            )}
          </div>
        </div>

        {/* Current Job Detail Card */}
        <div className="p-6 glass-panel border-slate-200 h-[480px] overflow-y-auto flex flex-col">
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 flex-shrink-0">
            Focused Job
          </h3>
          
          {currentJob ? (
            <div className="space-y-4 mb-6">
              <div>
                <h4 className="text-base font-bold text-slate-800">{currentJob.title}</h4>
                <p className="text-sm text-primary-600 font-semibold">{currentJob.company}</p>
                <p className="text-xs text-slate-500 mt-1">{currentJob.location} {currentJob.remote ? '(Remote)' : ''}</p>
              </div>

              <hr className="border-slate-100" />

              <div>
                <span className="text-[10px] font-bold text-slate-400 uppercase block mb-1">Queue Status</span>
                <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-primary-50 text-primary-700 border border-primary-200 capitalize">
                  {currentJob.status}
                </span>
              </div>

              {currentJob.description && (
                <div>
                  <span className="text-[10px] font-bold text-slate-400 uppercase block mb-2">Description Summary</span>
                  <div className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-200 leading-relaxed max-h-[120px] overflow-y-auto whitespace-pre-wrap">
                    {currentJob.description}
                  </div>
                </div>
              )}
              
              <div className="flex flex-col gap-2">
                <div className="flex gap-2">
                  <a
                    href={currentJob.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 glass-btn-secondary py-2 text-center text-xs font-semibold"
                  >
                    Open on LinkedIn
                  </a>
                  <button
                    onClick={() => {
                      setCurrentPage('jobs');
                      setJobStatusFilter('all');
                      if (currentJob.title) {
                        setJobSearchQuery(currentJob.title);
                      }
                    }}
                    className="flex-1 glass-btn-secondary py-2 text-center text-xs font-semibold cursor-pointer"
                  >
                    View in Jobs
                  </button>
                </div>
                <button
                  onClick={async () => {
                    try {
                      await api.post(`/api/jobs/${currentJob.id}/skip`, { reason: 'Skipped manually from dashboard' });
                    } catch (e) {
                      console.error('Failed to skip job:', e);
                    }
                  }}
                  className="w-full glass-btn bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 py-2 text-center text-xs font-semibold cursor-pointer"
                >
                  Skip Job
                </button>
              </div>
            </div>
          ) : (
            <div className="flex-shrink-0 flex flex-col items-center justify-center text-center text-slate-400 p-4 mb-6 pt-10">
              <Briefcase className="w-12 h-12 text-slate-300 mb-3" />
              <p className="text-xs italic">No active job currently in progress.</p>
            </div>
          )}

          {/* Up Next List */}
          <div className={currentJob ? "mt-auto" : "mt-2 flex-1 flex flex-col"}>
            <h4 className="text-[10px] font-bold text-slate-400 uppercase mb-3 flex items-center gap-2 flex-shrink-0">
              <ListPlus className="w-3.5 h-3.5" /> Up Next ({queuedJobsList.filter(j => j.id !== currentJob?.id).length})
            </h4>
            <div className={`space-y-2 ${!currentJob ? "overflow-y-auto pr-2" : ""}`}>
              {queuedJobsList.filter(j => j.id !== currentJob?.id).length === 0 ? (
                <div className="text-xs text-slate-400 italic text-center py-4 bg-slate-50 rounded-lg border border-slate-100">
                  Queue is empty
                </div>
              ) : (
                queuedJobsList.filter(j => j.id !== currentJob?.id).slice(0, currentJob ? 5 : 15).map((job: any, index: number) => (
                  <div
                    key={job.id}
                    draggable
                    onDragStart={(e) => handleQueueDragStart(e, index)}
                    onDragOver={handleQueueDragOver}
                    onDragEnd={handleQueueDragEnd}
                    onDrop={(e) => handleQueueDrop(e, index)}
                    className={`p-2.5 rounded-lg border flex items-center justify-between gap-2 transition-all ${draggingQueueIndex === index ? 'opacity-50 border-primary-400 bg-primary-50' : 'border-slate-100 bg-slate-50 hover:bg-slate-100'}`}
                  >
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <div className="cursor-grab active:cursor-grabbing p-1 -ml-1 text-slate-300 hover:text-slate-500 rounded transition-colors">
                        <GripVertical className="w-3.5 h-3.5" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-slate-800 truncate">{job.title}</p>
                        <p className="text-[10px] text-slate-500 truncate">{job.company}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button
                        onClick={async () => {
                          try {
                            await api.post('/api/jobs/bulk/prioritize', { job_ids: [job.id] });
                            setQueuedJobsList(prev => {
                              const updated = prev.map(j => j.id === job.id ? { ...j, priority: Date.now() } : j);
                              return updated.sort((a, b) => {
                                const pA = a.priority || 0;
                                const pB = b.priority || 0;
                                if (pA !== pB) return pB - pA;
                                return new Date(a.discovered_at).getTime() - new Date(b.discovered_at).getTime();
                              });
                            });
                          } catch (e) {
                            console.error('Failed to prioritize job:', e);
                          }
                        }}
                        className="p-1.5 rounded text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors cursor-pointer"
                        title="Prioritize Job"
                      >
                        <Zap className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            await api.post(`/api/jobs/${job.id}/skip`, { reason: 'Skipped from dashboard queue' });
                            setQueuedJobsList(prev => prev.filter(j => j.id !== job.id));
                            setQueuedCount(prev => prev - 1);
                          } catch (e) {
                            console.error('Failed to skip job:', e);
                          }
                        }}
                        className="p-1.5 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                        title="Skip (Remove from Queue)"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

      </div>

    </div>
  );
};
