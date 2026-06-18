import React, { useEffect, useState, useCallback } from 'react';
import ReactDOM from 'react-dom';
import api, { API_BASE_URL } from '../lib/api';
import { useBot, type Job } from '../hooks/useBot';
import {
  Check, X, Search, ExternalLink, Briefcase, Upload,
  Trash2, Ban, ListPlus, Zap, CheckSquare, Square,
  AlertTriangle, Loader2, LayoutGrid, List, GripVertical, FileText
} from 'lucide-react';

type BulkAction = 'skip' | 'approve' | 'prioritize' | 'delete' | 'blacklist';

interface ConfirmState {
  action: BulkAction;
  jobs: Job[];
}

const BULK_ACTION_META: Record<
  BulkAction,
  { label: string; icon: React.ReactNode; className: string }
> = {
  skip:       { label: 'Skip',              icon: React.createElement(X,       { className: 'w-3.5 h-3.5' }), className: 'text-amber-700 bg-white hover:bg-amber-50 border border-amber-200' },
  approve:    { label: 'Add to Queue',      icon: React.createElement(ListPlus,{ className: 'w-3.5 h-3.5' }), className: 'text-emerald-700 bg-white hover:bg-emerald-50 border border-emerald-200' },
  prioritize: { label: 'Prioritize',        icon: React.createElement(Zap,     { className: 'w-3.5 h-3.5' }), className: 'text-indigo-700 bg-white hover:bg-indigo-50 border border-indigo-200' },
  blacklist:  { label: 'Blacklist Company', icon: React.createElement(Ban,     { className: 'w-3.5 h-3.5' }), className: 'text-orange-700 bg-white hover:bg-orange-50 border border-orange-200' },
  delete:     { label: 'Delete',            icon: React.createElement(Trash2,  { className: 'w-3.5 h-3.5' }), className: 'text-rose-700 bg-white hover:bg-rose-50 border border-rose-200' },
};

export const Jobs: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const {
    jobSearchQuery: searchQuery,
    setJobSearchQuery: setSearchQuery,
    jobStatusFilter: statusFilter,
    setJobStatusFilter: setStatusFilter,
    jobsRefreshCounter,
    setAppSearchQuery,
    setSelectedJobIdForApp,
    setCurrentPage,
  } = useBot();

  const [selectedStatus, setSelectedStatus] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isBulkLoading, setIsBulkLoading] = useState(false);
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const fetchJobs = async (isBackgroundRefresh = false) => {
    if (!isBackgroundRefresh) {
      setIsLoading(true);
      setSelectedIds(new Set());
    }
    try {
      const res = await api.get('/api/jobs', {
        params: { status: statusFilter === 'all' ? undefined : statusFilter, limit: 1000 },
      });
      setJobs(res.data);
      
      // If doing a background refresh, keep selectedIds but remove any that no longer exist in the new data
      if (isBackgroundRefresh) {
        setSelectedIds(prev => {
          const validIds = new Set(res.data.map((j: Job) => j.id));
          const next = new Set<number>();
          prev.forEach(id => {
            if (validIds.has(id)) next.add(id);
          });
          return next;
        });
      }
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
    } finally {
      if (!isBackgroundRefresh) {
        setIsLoading(false);
      }
    }
  };

  useEffect(() => {
    setSelectedStatus('');
    fetchJobs(false);
  }, [statusFilter]);

  useEffect(() => {
    fetchJobs(true);
  }, [jobsRefreshCounter]);

  const handleApprove = async (jobId: number) => {
    try {
      await api.post(`/api/jobs/${jobId}/approve`, { mode: 'review' });
      setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: 'queued', skip_reason: undefined } : j));
    } catch (err) { console.error(err); }
  };

  const handleSkip = async (jobId: number) => {
    try {
      await api.post(`/api/jobs/${jobId}/skip`, { reason: 'Skipped by user' });
      setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: 'skipped', skip_reason: 'Skipped by user' } : j));
    } catch (err) { console.error(err); }
  };

  const handlePrioritize = async (jobId: number) => {
    try {
      await api.post('/api/jobs/bulk/prioritize', { job_ids: [jobId] });
      setJobs(prev => prev.map(j => j.id === jobId ? { ...j, priority: Date.now() } : j));
    } catch (err) { console.error(err); }
  };

  const [draggingJobIndex, setDraggingJobIndex] = useState<number | null>(null);

  const handleDragStart = (e: React.DragEvent, index: number) => {
    if (statusFilter !== 'queued') return;
    setDraggingJobIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent) => {
    if (statusFilter !== 'queued') return;
    e.preventDefault();
  };

  const handleDragEnd = () => {
    setDraggingJobIndex(null);
  };

  const handleDrop = async (e: React.DragEvent, targetIndex: number) => {
    e.preventDefault();
    if (statusFilter !== 'queued' || draggingJobIndex === null || draggingJobIndex === targetIndex) {
      setDraggingJobIndex(null);
      return;
    }

    const newSortedJobs = [...sortedJobs];
    const [draggedItem] = newSortedJobs.splice(draggingJobIndex, 1);
    newSortedJobs.splice(targetIndex, 0, draggedItem);
    
    // Optimistically update the list by assigning absolute priorities
    const orderedIds = newSortedJobs.map(j => j.id);
    const now = Date.now();
    const total = orderedIds.length;
    
    setJobs(prev => prev.map(j => {
      const idx = orderedIds.indexOf(j.id);
      if (idx !== -1) {
         return { ...j, priority: now + total - idx };
      }
      return j;
    }));

    setDraggingJobIndex(null);

    try {
      await api.post('/api/jobs/bulk/reorder', { job_ids: orderedIds });
    } catch (err) {
      console.error('Failed to reorder jobs:', err);
    }
  };

  const tabJobs = jobs.filter(job => statusFilter === 'all' || job.status === statusFilter);


  const filteredJobs = tabJobs.filter(job => {
    const query = searchQuery.toLowerCase().trim();
    if (query) {
      const match =
        job.title.toLowerCase().includes(query) ||
        job.company.toLowerCase().includes(query) ||
        (job.location && job.location.toLowerCase().includes(query));
      if (!match) return false;
    }
    if (statusFilter === 'all' && selectedStatus && job.status !== selectedStatus) return false;
    return true;
  });

  const sortedJobs = [...filteredJobs].sort((a, b) => {
    if (statusFilter === 'queued') {
      const priorityA = (a as any).priority || 0;
      const priorityB = (b as any).priority || 0;
      if (priorityA !== priorityB) {
        return priorityB - priorityA; // Descending
      }
      return new Date(a.discovered_at).getTime() - new Date(b.discovered_at).getTime(); // Ascending
    }
    return new Date(b.discovered_at).getTime() - new Date(a.discovered_at).getTime();
  });

  const visibleIds = sortedJobs.map(j => j.id);
  const allSelected = visibleIds.length > 0 && visibleIds.every(id => selectedIds.has(id));
  const someSelected = selectedIds.size > 0;

  const toggleJob = useCallback((id: number, index: number, event: React.MouseEvent) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (event.shiftKey && lastSelectedIndex !== null) {
        const start = Math.min(lastSelectedIndex, index);
        const end = Math.max(lastSelectedIndex, index);
        const targetIsSelected = prev.has(id);
        for (let i = start; i <= end; i++) {
          if (!targetIsSelected) {
            next.add(sortedJobs[i].id);
          } else {
            next.delete(sortedJobs[i].id);
          }
        }
      } else {
        next.has(id) ? next.delete(id) : next.add(id);
      }
      return next;
    });
    setLastSelectedIndex(index);
  }, [lastSelectedIndex, sortedJobs]);

  const toggleAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(visibleIds));
    }
  };

  const selectedJobs = sortedJobs.filter(j => selectedIds.has(j.id));

  const requiresConfirm = (action: BulkAction) => action === 'delete' || action === 'blacklist';

  const initiateBulkAction = (action: BulkAction) => {
    const actionableJobs = action === 'delete'
      ? selectedJobs
      : selectedJobs.filter(j => j.status !== 'applied');

    if (actionableJobs.length === 0) {
      setSelectedIds(new Set());
      return;
    }

    if (requiresConfirm(action)) {
      setConfirm({ action, jobs: actionableJobs });
    } else {
      executeBulkAction(action, actionableJobs);
    }
  };

  const executeBulkAction = async (action: BulkAction, targetJobs: Job[]) => {
    setConfirm(null);
    setIsBulkLoading(true);
    const ids = targetJobs.map(j => j.id);
    try {
      if (action === 'skip') {
        await api.post('/api/jobs/bulk/skip', { job_ids: ids });
        setJobs(prev => prev.map(j => ids.includes(j.id) ? { ...j, status: 'skipped', skip_reason: 'Skipped by user' } : j));
      } else if (action === 'approve') {
        await api.post('/api/jobs/bulk/approve', { job_ids: ids });
        setJobs(prev => prev.map(j => ids.includes(j.id) ? { ...j, status: 'queued', skip_reason: undefined } : j));
      } else if (action === 'prioritize') {
        await api.post('/api/jobs/bulk/prioritize', { job_ids: ids });
        const now = Date.now();
        setJobs(prev => prev.map(j => ids.includes(j.id) ? { ...j, status: 'queued', skip_reason: undefined, priority: now } : j));
      } else if (action === 'delete') {
        await api.post('/api/jobs/bulk/delete', { job_ids: ids });
        setJobs(prev => prev.filter(j => !ids.includes(j.id)));
      } else if (action === 'blacklist') {
        await api.post('/api/jobs/bulk/blacklist-company', { job_ids: ids });
      }
      setSelectedIds(new Set());
    } catch (err) {
      console.error('Bulk action failed:', err);
    } finally {
      setIsBulkLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'discovered': return <span className="text-[9px] font-bold text-blue-700 bg-blue-50 border border-blue-100 px-2 py-0.5 rounded-full uppercase flex-shrink-0">Discovered</span>;
      case 'queued':     return <span className="text-[9px] font-bold text-amber-700 bg-amber-50 border border-amber-100 px-2 py-0.5 rounded-full uppercase flex-shrink-0">Queued</span>;
      case 'applying':   return <span className="text-[9px] font-bold text-indigo-700 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded-full uppercase flex-shrink-0 animate-pulse">Applying</span>;
      case 'applied':    return <span className="text-[9px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded-full uppercase flex-shrink-0">Applied</span>;
      case 'skipped':    return <span className="text-[9px] font-bold text-rose-700 bg-rose-50 border border-rose-100 px-2 py-0.5 rounded-full uppercase flex-shrink-0">Skipped</span>;
      case 'failed':     return <span className="text-[9px] font-bold text-red-700 bg-red-50 border border-red-100 px-2 py-0.5 rounded-full uppercase flex-shrink-0">Failed</span>;
      case 'review_pending': return <span className="text-[9px] font-bold text-purple-700 bg-purple-50 border border-purple-100 px-2 py-0.5 rounded-full uppercase flex-shrink-0">Review Pending</span>;
      default: return <span className="text-[9px] font-bold text-slate-700 bg-slate-50 border border-slate-100 px-2 py-0.5 rounded-full uppercase flex-shrink-0">{status}</span>;
    }
  };

  const uniqueCompanies = confirm ? [...new Set(confirm.jobs.map(j => j.company))] : [];



  // Portal-rendered toolbar — escapes the overflow:auto container in App.tsx
  const toolbar = (
    <div
      style={{ position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 9999 }}
      className={`transition-all duration-300 ease-in-out ${someSelected ? 'translate-y-0 opacity-100' : 'translate-y-full opacity-0 pointer-events-none'}`}
    >
      <div className="max-w-5xl mx-auto px-4 pb-4">
        <div className="bg-slate-900 rounded-2xl shadow-2xl border border-slate-700 px-5 py-3.5 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="bg-primary-500 text-white text-xs font-bold px-2.5 py-1 rounded-full min-w-[28px] text-center">
              {selectedIds.size}
            </span>
            <span className="text-sm font-semibold text-slate-200">
              job{selectedIds.size !== 1 ? 's' : ''} selected
            </span>
          </div>
          <div className="w-px h-6 bg-slate-700 hidden sm:block" />
          <div className="flex flex-wrap gap-2 flex-1">
            {(Object.entries(BULK_ACTION_META) as [BulkAction, typeof BULK_ACTION_META[BulkAction]][])
              .map(([action, meta]) => (
                <button
                  key={action}
                  onClick={() => initiateBulkAction(action)}
                  disabled={isBulkLoading}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer disabled:opacity-50 ${meta.className}`}
                >
                  {isBulkLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : meta.icon}
                  {meta.label}
                </button>
              )
            )}
          </div>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-all cursor-pointer"
            title="Clear selection"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );

  // Portal-rendered confirmation modal
  const modal = confirm && (
    <div style={{ position: 'fixed', inset: 0, zIndex: 10000 }} className="flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setConfirm(null)} />
      <div className="relative bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-5 h-5 text-orange-600" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">
              {confirm.action === 'delete' ? 'Delete Jobs?' : 'Blacklist Companies?'}
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              {confirm.action === 'delete'
                ? `This will permanently delete ${confirm.jobs.length} job${confirm.jobs.length !== 1 ? 's' : ''} from the database. This cannot be undone.`
                : `This will add ${uniqueCompanies.length} compan${uniqueCompanies.length !== 1 ? 'ies' : 'y'} to the blacklist of all search criteria.`}
            </p>
          </div>
        </div>

        {confirm.action === 'blacklist' && (
          <div className="bg-orange-50 border border-orange-200 rounded-xl p-3 mb-4 max-h-40 overflow-y-auto">
            <p className="text-[10px] font-bold text-orange-700 uppercase mb-2">Companies to blacklist:</p>
            <div className="flex flex-wrap gap-1.5">
              {uniqueCompanies.map(c => (
                <span key={c} className="text-xs bg-orange-100 text-orange-800 border border-orange-200 px-2 py-0.5 rounded-full font-medium">{c}</span>
              ))}
            </div>
          </div>
        )}

        {confirm.action === 'delete' && (
          <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 mb-4 max-h-40 overflow-y-auto">
            <p className="text-[10px] font-bold text-rose-700 uppercase mb-2">Jobs to delete:</p>
            <div className="space-y-1">
              {confirm.jobs.slice(0, 8).map(j => (
                <p key={j.id} className="text-xs text-rose-800 truncate">
                  &bull; <span className="font-semibold">{j.title}</span> @ {j.company}
                </p>
              ))}
              {confirm.jobs.length > 8 && (
                <p className="text-xs text-rose-600 italic">... and {confirm.jobs.length - 8} more</p>
              )}
            </div>
          </div>
        )}

        <div className="flex gap-3">
          <button onClick={() => setConfirm(null)} className="flex-1 glass-btn-secondary py-2 text-sm cursor-pointer">Cancel</button>
          <button
            onClick={() => executeBulkAction(confirm.action, confirm.jobs)}
            className={`flex-1 py-2 text-sm font-semibold rounded-lg cursor-pointer transition-all text-white ${confirm.action === 'delete' ? 'bg-rose-600 hover:bg-rose-700' : 'bg-orange-600 hover:bg-orange-700'}`}
          >
            {confirm.action === 'delete' ? 'Delete' : 'Blacklist'}
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <div className="space-y-6 pb-28">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Jobs</h2>
            <p className="text-xs text-slate-500 mt-1">Manage the queue of jobs discovered by the bot.</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex bg-slate-100 p-1 border border-slate-200 rounded-lg hidden sm:flex">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-md transition-all cursor-pointer ${viewMode === 'grid' ? 'bg-white shadow text-primary-600' : 'text-slate-500 hover:text-slate-900'}`}
                title="Grid View"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-1.5 rounded-md transition-all cursor-pointer ${viewMode === 'list' ? 'bg-white shadow text-primary-600' : 'text-slate-500 hover:text-slate-900'}`}
                title="List View"
              >
                <List className="w-4 h-4" />
              </button>
            </div>
            <div className="flex flex-wrap bg-slate-100 p-1 border border-slate-200 rounded-lg gap-1">
              {(['all', 'discovered', 'queued', 'applied', 'skipped', 'failed'] as const).map(s => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`px-3 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${statusFilter === s ? 'bg-primary-600 text-white shadow' : 'text-slate-500 hover:text-slate-900'}`}
                >
                  {s === 'all' ? 'All Jobs' : s === 'discovered' ? 'New Discoveries' : s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
            <a href={`${API_BASE_URL}/api/jobs/export`} download className="glass-btn-secondary py-2 text-xs">
              <Upload className="w-3.5 h-3.5" />Export CSV
            </a>
          </div>
        </div>

        {/* Search Bar & Filters */}
        <div className="space-y-3">
          <div className="relative">
            <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-500"><Search className="w-4 h-4" /></span>
            <input
              type="text"
              placeholder="Filter by job title, company or location..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full glass-input pl-10 text-sm"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 bg-slate-50 p-3 rounded-lg border border-slate-200">
            {/* Select All */}
            <button
              onClick={toggleAll}
              title={allSelected ? 'Deselect all' : 'Select all visible'}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-xs font-semibold transition-all cursor-pointer flex-shrink-0 ${allSelected ? 'bg-primary-600 text-white border-primary-600' : 'bg-white text-slate-600 border-slate-200 hover:border-primary-400 hover:text-primary-600'}`}
            >
              {allSelected ? <CheckSquare className="w-3.5 h-3.5" /> : <Square className="w-3.5 h-3.5" />}
              {allSelected ? 'Deselect All' : 'Select All'}
            </button>

            {someSelected && (
              <span className="text-xs font-semibold text-primary-700 bg-primary-50 border border-primary-200 px-2.5 py-1 rounded-md flex-shrink-0">
                {selectedIds.size} selected
              </span>
            )}

            <div className="flex flex-wrap items-end gap-3 ml-auto">
              {statusFilter === 'all' && (
                <div className="flex flex-col gap-1 min-w-[130px]">
                  <span className="text-[10px] font-bold text-slate-500 uppercase">Status</span>
                  <select value={selectedStatus} onChange={e => setSelectedStatus(e.target.value)} className="w-full glass-input text-xs py-1.5 cursor-pointer bg-white">
                    <option value="">All Statuses</option>
                    {['discovered','queued','applying','applied','skipped','failed','review_pending'].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              )}



              {(searchQuery || selectedStatus) && (
                <button
                  onClick={() => { setSearchQuery(''); setSelectedStatus(''); }}
                  className="px-3 py-1.5 text-xs font-semibold text-rose-600 hover:bg-rose-50 border border-rose-200 rounded-md transition-all cursor-pointer bg-white"
                >
                  Clear Filters
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Grid / List */}
        {isLoading ? (
          <div className="h-64 flex items-center justify-center text-slate-500 text-xs italic">Fetching jobs from local database...</div>
        ) : sortedJobs.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-center text-slate-500">
            <Briefcase className="w-12 h-12 text-slate-300 mb-3" />
            <p className="text-sm">No jobs found for this listing.</p>
          </div>
        ) : (
          <div className={viewMode === 'grid' ? "grid grid-cols-1 md:grid-cols-2 gap-4" : "flex flex-col gap-3"}>
            {sortedJobs.map((job, index) => {
              const isSelected = selectedIds.has(job.id);
              return viewMode === 'grid' ? (
                <div
                  key={job.id}
                  draggable={statusFilter === 'queued'}
                  onDragStart={(e) => handleDragStart(e, index)}
                  onDragOver={handleDragOver}
                  onDragEnd={handleDragEnd}
                  onDrop={(e) => handleDrop(e, index)}
                  className={`glass-card flex flex-col justify-between p-4 transition-all duration-150 ${isSelected ? 'ring-2 ring-primary-400 bg-primary-50/30' : 'hover:ring-1 hover:ring-slate-200'} ${draggingJobIndex === index ? 'opacity-50' : ''}`}
                >
                  <div>
                    <div className="flex items-start justify-between gap-3 mb-2">
                      {statusFilter === 'queued' && (
                        <div className="cursor-grab active:cursor-grabbing p-1 -ml-2 -mt-1 text-slate-300 hover:text-slate-500 rounded transition-colors flex-shrink-0">
                          <GripVertical className="w-4 h-4" />
                        </div>
                      )}
                      {/* Checkbox */}
                      <button
                        onClick={(e) => toggleJob(job.id, index, e)}
                        className={`mt-0.5 flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-all cursor-pointer ${isSelected ? 'bg-primary-600 border-primary-600 text-white' : 'border-slate-300 bg-white hover:border-primary-400'}`}
                        aria-label={isSelected ? 'Deselect job' : 'Select job'}
                      >
                        {isSelected && <Check className="w-3 h-3" />}
                      </button>

                      <div className="flex-1 min-w-0">
                        <h4 className="text-base font-bold text-slate-800 line-clamp-1">{job.title}</h4>
                        <p className="text-xs text-primary-600 font-semibold">{job.company}</p>
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0">
                        {getStatusBadge(job.status)}
                        <a href={job.url} target="_blank" rel="noopener noreferrer" className="p-1.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-400 hover:text-slate-600">
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </div>
                    </div>

                    <p className="text-xs text-slate-500 mb-2 ml-7">
                      Location: {job.location || 'Not specified'} {job.remote ? '(Remote)' : ''}
                    </p>
                    <p className="text-[10px] text-slate-400 mb-3 ml-7">
                      Discovered: {new Date(job.discovered_at).toLocaleDateString()} at{' '}
                      {new Date(job.discovered_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>

                    {job.skip_reason && (
                      <div className="p-2.5 bg-red-50 text-red-700 rounded-lg text-[10px] border border-red-200 mb-3 ml-7">
                        <span className="font-bold block mb-0.5">{job.status === 'failed' ? 'Failure reason:' : 'Skip reason:'}</span> {job.skip_reason}
                      </div>
                    )}
                  </div>

                  {/* Per-card action buttons */}
                  <div className="flex gap-2 pt-3 border-t border-slate-100 mt-auto ml-7">
                    {job.status === 'discovered' && (
                      <>
                        <button onClick={() => handleSkip(job.id)} className="flex-1 glass-btn-secondary py-1.5 text-xs text-red-600 hover:bg-red-50 border-red-100 cursor-pointer"><X className="w-3.5 h-3.5" /> Skip</button>
                        <button onClick={() => handleApprove(job.id)} className="flex-1 glass-btn-success py-1.5 text-xs cursor-pointer"><Check className="w-3.5 h-3.5" /> Approve</button>
                      </>
                    )}
                    {job.status === 'skipped' && (
                      <button onClick={() => handleApprove(job.id)} className="w-full glass-btn-success py-1.5 text-xs cursor-pointer"><Check className="w-3.5 h-3.5" /> Add to Queue</button>
                    )}
                    {job.status === 'queued' && (
                      <>
                        <button onClick={() => handleSkip(job.id)} className="flex-1 glass-btn-secondary py-1.5 text-xs text-red-600 hover:bg-red-50 border-red-100 cursor-pointer"><X className="w-3.5 h-3.5" /> Skip</button>
                        <button onClick={() => handlePrioritize(job.id)} className="flex-1 glass-btn-secondary py-1.5 text-xs text-indigo-600 hover:bg-indigo-50 border-indigo-100 cursor-pointer"><Zap className="w-3.5 h-3.5" /> Prioritize</button>
                      </>
                    )}
                    {(job.status === 'failed' || job.status === 'review_pending') && (
                      <>
                        <button onClick={() => handleSkip(job.id)} className="flex-1 glass-btn-secondary py-1.5 text-xs text-red-600 hover:bg-red-50 border-red-100 cursor-pointer"><X className="w-3.5 h-3.5" /> Skip</button>
                        <button onClick={() => handleApprove(job.id)} className="flex-1 glass-btn-success py-1.5 text-xs cursor-pointer"><Check className="w-3.5 h-3.5" /> Queue Again</button>
                      </>
                    )}
                    {job.status === 'applied' && (
                      <>
                        <button onClick={() => { setSelectedJobIdForApp(job.id); setAppSearchQuery(''); setCurrentPage('applications'); }} className="flex-1 glass-btn-secondary py-1.5 text-xs text-primary-600 hover:bg-primary-50 border-primary-100 cursor-pointer"><FileText className="w-3.5 h-3.5" /> Details</button>
                        <button onClick={() => setConfirm({ action: 'delete', jobs: [job] })} className="flex-1 glass-btn-secondary py-1.5 text-xs text-rose-600 hover:bg-rose-50 border-rose-100 cursor-pointer"><Trash2 className="w-3.5 h-3.5" /> Delete</button>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <div
                  key={job.id}
                  draggable={statusFilter === 'queued'}
                  onDragStart={(e) => handleDragStart(e, index)}
                  onDragOver={handleDragOver}
                  onDragEnd={handleDragEnd}
                  onDrop={(e) => handleDrop(e, index)}
                  className={`glass-card p-3 flex items-center justify-between gap-4 transition-all duration-150 ${isSelected ? 'ring-2 ring-primary-400 bg-primary-50/30' : 'hover:ring-1 hover:ring-slate-200'} ${draggingJobIndex === index ? 'opacity-50' : ''}`}
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    {statusFilter === 'queued' && (
                      <div className="cursor-grab active:cursor-grabbing p-1 -ml-1 text-slate-300 hover:text-slate-500 rounded transition-colors flex-shrink-0">
                        <GripVertical className="w-4 h-4" />
                      </div>
                    )}
                    <button
                      onClick={(e) => toggleJob(job.id, index, e)}
                      className={`flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-all cursor-pointer ${isSelected ? 'bg-primary-600 border-primary-600 text-white' : 'border-slate-300 bg-white hover:border-primary-400'}`}
                      aria-label={isSelected ? 'Deselect job' : 'Select job'}
                    >
                      {isSelected && <Check className="w-3 h-3" />}
                    </button>
                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-slate-800 line-clamp-1">{job.title}</h4>
                        <a href={job.url} target="_blank" rel="noopener noreferrer" className="p-1 rounded bg-slate-50 border border-slate-200 text-slate-400 hover:text-slate-600 transition-colors">
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                      <p className="text-xs text-primary-600 font-semibold">{job.company}</p>
                      <p className="text-[10px] text-slate-500 mt-0.5 truncate">
                        {job.location || 'Not specified'} {job.remote ? '(Remote)' : ''} &bull; {new Date(job.discovered_at).toLocaleDateString()}
                      </p>
                      {job.skip_reason && (
                        <p className="text-[10px] text-red-600 mt-0.5 truncate bg-red-50 px-1.5 py-0.5 rounded border border-red-100 self-start max-w-full">
                          <span className="font-semibold">{job.status === 'failed' ? 'Failure reason:' : 'Skip reason:'}</span> {job.skip_reason}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-4 flex-shrink-0">
                    <div className="hidden sm:flex flex-col items-end">
                      {getStatusBadge(job.status)}
                    </div>

                    <div className="flex items-center gap-2">
                      {job.status === 'discovered' && (
                        <>
                          <button onClick={() => handleSkip(job.id)} title="Skip" className="glass-btn-secondary p-1.5 text-xs text-red-600 hover:bg-red-50 border-red-100 cursor-pointer"><X className="w-4 h-4" /></button>
                          <button onClick={() => handleApprove(job.id)} title="Approve" className="glass-btn-success p-1.5 text-xs cursor-pointer"><Check className="w-4 h-4" /></button>
                        </>
                      )}
                      {job.status === 'skipped' && (
                        <button onClick={() => handleApprove(job.id)} className="glass-btn-success py-1.5 px-3 text-xs cursor-pointer flex items-center gap-1"><Check className="w-3 h-3" /> Add</button>
                      )}
                      {job.status === 'queued' && (
                        <>
                          <button onClick={() => handleSkip(job.id)} title="Skip" className="glass-btn-secondary p-1.5 text-xs text-red-600 hover:bg-red-50 border-red-100 cursor-pointer"><X className="w-4 h-4" /></button>
                          <button onClick={() => handlePrioritize(job.id)} title="Prioritize" className="glass-btn-secondary p-1.5 text-xs text-indigo-600 hover:bg-indigo-50 border-indigo-100 cursor-pointer"><Zap className="w-4 h-4" /></button>
                        </>
                      )}
                      {(job.status === 'failed' || job.status === 'review_pending') && (
                        <>
                          <button onClick={() => handleSkip(job.id)} title="Skip" className="glass-btn-secondary p-1.5 text-xs text-red-600 hover:bg-red-50 border-red-100 cursor-pointer"><X className="w-4 h-4" /></button>
                          <button onClick={() => handleApprove(job.id)} title="Queue Again" className="glass-btn-success p-1.5 text-xs cursor-pointer"><Check className="w-4 h-4" /></button>
                        </>
                      )}
                      {job.status === 'applied' && (
                        <>
                          <button onClick={() => { setSelectedJobIdForApp(job.id); setAppSearchQuery(''); setCurrentPage('applications'); }} title="Details" className="glass-btn-secondary p-1.5 text-xs text-primary-600 hover:bg-primary-50 border-primary-100 cursor-pointer"><FileText className="w-4 h-4" /></button>
                          <button onClick={() => setConfirm({ action: 'delete', jobs: [job] })} title="Delete" className="glass-btn-secondary p-1.5 text-xs text-rose-600 hover:bg-rose-50 border-rose-100 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Toolbar & modal rendered via portals to escape overflow:auto in App.tsx */}
      {ReactDOM.createPortal(toolbar, document.body)}
      {modal && ReactDOM.createPortal(modal, document.body)}
    </>
  );
};
