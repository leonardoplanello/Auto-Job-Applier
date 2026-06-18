import React, { useEffect, useState } from 'react';
import api from '../lib/api';
import { Plus, Edit2, Trash2, Check, X, Layers, AlertCircle, Copy, GripVertical } from 'lucide-react';

interface SearchCriteria {
  id: number;
  name: string;
  keywords: string[];
  location: string;
  remote_only: boolean;
  date_posted_filter: string;
  experience_levels: string[];
  blacklist_companies: string[];
  blacklist_keywords: string[];
  max_per_session: number;
  is_active: boolean;
  company?: string;
}

export const SearchCriteria: React.FC = () => {
  const [criteriaList, setCriteriaList] = useState<SearchCriteria[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Drag and drop states
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggingIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDragEnd = () => {
    setDraggingIndex(null);
  };

  const handleDrop = async (e: React.DragEvent, targetIndex: number) => {
    e.preventDefault();
    if (draggingIndex === null || draggingIndex === targetIndex) {
      setDraggingIndex(null);
      return;
    }

    const newList = [...criteriaList];
    const [draggedItem] = newList.splice(draggingIndex, 1);
    newList.splice(targetIndex, 0, draggedItem);
    
    setCriteriaList(newList);
    setDraggingIndex(null);

    try {
      const orderedIds = newList.map(c => c.id);
      await api.post('/api/search/reorder', orderedIds);
    } catch (err) {
      console.error('Failed to save reordered search criteria:', err);
      alert('Failed to save criteria order.');
      fetchCriteria();
    }
  };

  // Form states
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [name, setName] = useState('');
  const [companyText, setCompanyText] = useState('');
  const [keywordsText, setKeywordsText] = useState('');
  const [locationText, setLocationText] = useState('');
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [dateFilter, setDateFilter] = useState('past_week');
  const [selectedExpLevels, setSelectedExpLevels] = useState<string[]>([]);
  const [blacklistCompaniesText, setBlacklistCompaniesText] = useState('');
  const [blacklistKeywordsText, setBlacklistKeywordsText] = useState('');
  const [maxPerSession, setMaxPerSession] = useState(10);
  const [isActive, setIsActive] = useState(true);

  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchCriteria = async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/api/search');
      setCriteriaList(res.data);
    } catch (err) {
      console.error('Failed to load search criteria:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCriteria();
  }, []);

  const handleOpenAddModal = () => {
    setCurrentId(null);
    setName('');
    setCompanyText('');
    setKeywordsText('');
    setLocationText('Brazil');
    setRemoteOnly(false);
    setDateFilter('past_week');
    setSelectedExpLevels(['mid_senior', 'senior']);
    setBlacklistCompaniesText('');
    setBlacklistKeywordsText('');
    setMaxPerSession(10);
    setIsActive(true);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (c: SearchCriteria) => {
    setCurrentId(c.id);
    setName(c.name);
    setCompanyText(c.company || '');
    setKeywordsText(c.keywords.join(', '));
    setLocationText(c.location || '');
    setRemoteOnly(c.remote_only);
    setDateFilter(c.date_posted_filter);
    setSelectedExpLevels(c.experience_levels || []);
    setBlacklistCompaniesText((c.blacklist_companies || []).join(', '));
    setBlacklistKeywordsText((c.blacklist_keywords || []).join(', '));
    setMaxPerSession(c.max_per_session);
    setIsActive(c.is_active);
    setIsModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this search criteria?')) return;
    try {
      await api.delete(`/api/search/${id}`);
      setCriteriaList((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      alert('Failed to delete search criteria.');
    }
  };

  const handleDuplicate = async (c: SearchCriteria) => {
    try {
      const payload = {
        name: `${c.name} (Copy)`,
        company: c.company,
        keywords: c.keywords,
        location: c.location,
        remote_only: c.remote_only,
        date_posted_filter: c.date_posted_filter,
        experience_levels: c.experience_levels || [],
        blacklist_companies: c.blacklist_companies || [],
        blacklist_keywords: c.blacklist_keywords || [],
        max_per_session: c.max_per_session,
        is_active: c.is_active,
      };
      await api.post('/api/search', payload);
      fetchCriteria();
    } catch (err) {
      console.error('Failed to duplicate search criteria:', err);
      alert('Failed to duplicate search criteria.');
    }
  };

  const handleToggleExpLevel = (level: string) => {
    setSelectedExpLevels((prev) =>
      prev.includes(level) ? prev.filter((l) => l !== level) : [...prev, level]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    const splitAndClean = (text: string) =>
      text
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0);

    const payload = {
      name,
      company: companyText.trim() || undefined,
      keywords: splitAndClean(keywordsText),
      location: locationText.trim(),
      remote_only: remoteOnly,
      date_posted_filter: dateFilter,
      experience_levels: selectedExpLevels,
      blacklist_companies: splitAndClean(blacklistCompaniesText),
      blacklist_keywords: splitAndClean(blacklistKeywordsText),
      max_per_session: maxPerSession,
      is_active: isActive,
    };

    try {
      if (currentId) {
        await api.put(`/api/search/${currentId}`, payload);
      } else {
        await api.post('/api/search', payload);
      }
      setIsModalOpen(false);
      fetchCriteria();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to save search criteria.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const expLevels = [
    { name: 'internship', label: 'Internship' },
    { name: 'entry_level', label: 'Entry Level' },
    { name: 'associate', label: 'Associate' },
    { name: 'mid_senior', label: 'Mid-Senior' },
    { name: 'director', label: 'Director' },
    { name: 'executive', label: 'Executive' },
  ];

  return (
    <div className="space-y-6">
      
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Search Criteria</h2>
          <p className="text-xs text-slate-500 mt-1">
            Configure keywords and location parameters for the job search engine.
          </p>
        </div>

        <button
          onClick={handleOpenAddModal}
          className="glass-btn-primary py-2 text-xs"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Criteria
        </button>
      </div>

      {/* List criteria */}
      {isLoading && criteriaList.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-slate-500 text-xs italic">
          Loading search parameters...
        </div>
      ) : criteriaList.length === 0 ? (
        <div className="p-8 glass-panel text-center text-slate-500 max-w-lg mx-auto mt-8 space-y-4">
          <AlertCircle className="w-10 h-10 text-primary-500 mx-auto" />
          <h4 className="font-bold text-slate-800">No Search Criteria Defined</h4>
          <p className="text-xs">
            To start applying for jobs, you must first define at least one search filter (keywords, location, etc.).
          </p>
          <button onClick={handleOpenAddModal} className="glass-btn-primary mx-auto text-xs py-2">
            Create First Filter
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {criteriaList.map((c, index) => (
            <div 
              key={c.id} 
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, index)}
              className={`glass-card flex flex-col justify-between transition-all duration-200 ${
                draggingIndex === index ? 'opacity-40 scale-[0.98] border-dashed border-primary-350' : ''
              }`}
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <h4 className="text-base font-bold text-slate-800 flex items-center gap-2">
                    <div
                      draggable
                      onDragStart={(e) => handleDragStart(e, index)}
                      onDragEnd={handleDragEnd}
                      className="cursor-grab active:cursor-grabbing text-slate-400 hover:text-slate-655 p-0.5 rounded transition-colors"
                      title="Drag to reorder"
                    >
                      <GripVertical className="w-4 h-4" />
                    </div>
                    <Layers className="w-4 h-4 text-primary-600" />
                    {c.name}
                  </h4>
                  <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                    c.is_active ? 'bg-emerald-100 text-emerald-700 border border-emerald-200' : 'bg-slate-100 text-slate-600 border border-slate-200'
                  }`}>
                    {c.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                <div className="space-y-2 text-xs">
                  <div>
                    <span className="font-semibold text-slate-500">Keywords: </span>
                    <span className="text-slate-800">{c.keywords.join(', ')}</span>
                  </div>
                  <div>
                    <span className="font-semibold text-slate-500">Location: </span>
                    <span className="text-slate-800">{c.location || 'Any'}</span>
                  </div>
                  {c.company && (
                    <div>
                      <span className="font-semibold text-slate-500">Company: </span>
                      <span className="text-slate-800">{c.company}</span>
                    </div>
                  )}
                  <div>
                    <span className="font-semibold text-slate-500">Filters: </span>
                    <span className="text-slate-800">
                      {c.remote_only ? 'Remote Only' : 'Any Workplace'} • {c.date_posted_filter.replace('_', ' ')} • Max {c.max_per_session} per session
                    </span>
                  </div>
                  {c.blacklist_companies.length > 0 && (
                    <div>
                      <span className="font-semibold text-red-500">Blacklisted Companies: </span>
                      <span className="text-slate-700">{c.blacklist_companies.join(', ')}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex justify-end gap-2 mt-4 pt-3 border-t border-slate-100">
                <button
                  onClick={() => handleOpenEditModal(c)}
                  className="glass-btn-secondary py-1 px-3 text-xs"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                  Edit
                </button>
                <button
                  onClick={() => handleDuplicate(c)}
                  className="glass-btn bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 py-1 px-3 text-xs"
                >
                  <Copy className="w-3.5 h-3.5" />
                  Duplicate
                </button>
                <button
                  onClick={() => handleDelete(c.id)}
                  className="glass-btn bg-red-50 hover:bg-red-100 text-red-600 border border-red-100 py-1 px-3 text-xs"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Editor Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-lg glass-panel p-6 animate-slide-up max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-800">
                {currentId ? 'Edit Search Filter' : 'New Search Filter'}
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 rounded-md text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Filter Name & Company */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Filter Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Backend Dev Brazil"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Company</label>
                  <input
                    type="text"
                    placeholder="e.g. Google (Optional)"
                    value={companyText}
                    onChange={(e) => setCompanyText(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
              </div>

              {/* Keywords & Location */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Keywords (comma-separated)</label>
                  <input
                    type="text"
                    required
                    placeholder="Python Developer, Backend"
                    value={keywordsText}
                    onChange={(e) => setKeywordsText(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Location</label>
                  <input
                    type="text"
                    placeholder="e.g. Brazil or United States"
                    value={locationText}
                    onChange={(e) => setLocationText(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
              </div>

              {/* Toggles */}
              <div className="flex items-center justify-between gap-4 py-2 border-y border-slate-100">
                <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={remoteOnly}
                    onChange={(e) => setRemoteOnly(e.target.checked)}
                    className="accent-primary-600 rounded"
                  />
                  Remote Only
                </label>

                <div className="flex items-center gap-2">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Limit:</label>
                  <input
                    type="number"
                    min="1"
                    max="50"
                    value={maxPerSession}
                    onChange={(e) => setMaxPerSession(parseInt(e.target.value) || 10)}
                    className="glass-input text-xs w-16 text-center py-1"
                  />
                </div>
              </div>

              {/* Date Filter & Experience Levels */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Date Posted</label>
                  <select
                    value={dateFilter}
                    onChange={(e) => setDateFilter(e.target.value)}
                    className="w-full glass-input text-xs bg-white"
                  >
                    <option value="any">Any Time</option>
                    <option value="past_day">Past 24 Hours</option>
                    <option value="past_week">Past Week</option>
                    <option value="past_month">Past Month</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Experience Levels</label>
                  <div className="flex flex-wrap gap-1.5 max-h-[80px] overflow-y-auto">
                    {expLevels.map((lvl) => (
                      <button
                        type="button"
                        key={lvl.name}
                        onClick={() => handleToggleExpLevel(lvl.name)}
                        className={`px-2 py-0.5 rounded text-[10px] font-medium border transition-all ${
                          selectedExpLevels.includes(lvl.name)
                            ? 'bg-primary-50 text-primary-700 border-primary-300'
                            : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'
                        }`}
                      >
                        {lvl.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Blacklists */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Blacklist Companies</label>
                  <input
                    type="text"
                    placeholder="Separate with commas"
                    value={blacklistCompaniesText}
                    onChange={(e) => setBlacklistCompaniesText(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Blacklist Keywords</label>
                  <input
                    type="text"
                    placeholder="e.g. Senior, Leader"
                    value={blacklistKeywordsText}
                    onChange={(e) => setBlacklistKeywordsText(e.target.value)}
                    className="w-full glass-input text-xs"
                  />
                </div>
              </div>

              {/* Active Toggle */}
              <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer select-none py-1">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="accent-primary-600 rounded"
                />
                Is Active Filter
              </label>

              {/* Submit Buttons */}
              <div className="flex gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="flex-1 glass-btn-secondary text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 glass-btn-primary text-xs"
                >
                  <Check className="w-3.5 h-3.5" />
                  {isSubmitting ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
