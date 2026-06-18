import React, { useEffect, useState } from 'react';
import api, { API_BASE_URL } from '../lib/api';
import { Calendar, FileText, CheckCircle, ChevronRight, MessageSquare, Search, Upload } from 'lucide-react';
import { useBot } from '../hooks/useBot';

interface FilledField {
  label: string;
  value: string;
  source: string;
}

interface Application {
  id: number;
  job_id: number;
  status: string;
  fields_filled: FilledField[] | null;
  resume_used: string | null;
  submitted_at: string;
  notes: string | null;
  job?: {
    title: string;
    company: string;
    location: string;
    url: string;
  };
}

export const Applications: React.FC = () => {
  const [apps, setApps] = useState<Application[]>([]);
  const [selectedApp, setSelectedApp] = useState<Application | null>(null);
  const [notesText, setNotesText] = useState('');
  const { appSearchQuery, setAppSearchQuery } = useBot();
  const [isLoading, setIsLoading] = useState(false);
  const [isSavingNotes, setIsSavingNotes] = useState(false);

  const fetchApplications = async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/api/applications');
      setApps(res.data);
    } catch (err) {
      console.error('Failed to load applications:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchApplications();
  }, []);

  const handleSelectApp = (app: Application) => {
    setSelectedApp(app);
    setNotesText(app.notes || '');
  };

  const handleSaveNotes = async () => {
    if (!selectedApp) return;
    setIsSavingNotes(true);
    try {
      const res = await api.patch(`/api/applications/${selectedApp.id}`, {
        notes: notesText
      });
      setApps((prev) => prev.map((a) => (a.id === selectedApp.id ? res.data : a)));
      setSelectedApp(res.data);
      alert('Notes saved successfully.');
    } catch (err) {
      alert('Failed to save notes.');
    } finally {
      setIsSavingNotes(false);
    }
  };

  const filteredApps = apps.filter((app) => {
    const query = appSearchQuery.toLowerCase().trim();
    if (!query) return true;
    return (
      app.job?.title.toLowerCase().includes(query) ||
      app.job?.company.toLowerCase().includes(query) ||
      (app.notes && app.notes.toLowerCase().includes(query))
    );
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
      
      {/* Applications list */}
      <div className="lg:col-span-2 flex flex-col gap-4 overflow-hidden h-full">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Applications History</h2>
            <p className="text-xs text-slate-500 mt-1">View and annotate details of vacancies applied by the bot.</p>
          </div>
          
          <a
            href={`${API_BASE_URL}/api/applications/export`}
            download
            className="glass-btn-secondary py-2 text-xs"
          >
            <Upload className="w-3.5 h-3.5" />
            Export CSV
          </a>
        </div>

        {/* Search Input */}
        <div className="relative flex-shrink-0">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search applications..."
            value={appSearchQuery}
            onChange={(e) => setAppSearchQuery(e.target.value)}
            className="w-full bg-white border border-slate-200 rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 transition-shadow"
          />
        </div>

        {/* Scrollable list */}
        <div className="flex-1 overflow-y-auto space-y-3 pr-2">
          {isLoading ? (
            <div className="h-64 flex items-center justify-center text-slate-500 text-xs italic">
              Loading applications history...
            </div>
          ) : filteredApps.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center text-center text-slate-500">
              <Calendar className="w-12 h-12 text-slate-300 mb-3" />
              <p className="text-sm">No applications recorded.</p>
            </div>
          ) : (
            filteredApps.map((app) => (
              <div
                key={app.id}
                onClick={() => handleSelectApp(app)}
                className={`glass-card p-4 hover:border-slate-300 cursor-pointer flex items-center justify-between transition-all ${
                  selectedApp?.id === app.id ? 'border-primary-500 bg-primary-50' : ''
                }`}
              >
                <div className="flex items-start gap-4">
                  <div className="p-2.5 bg-emerald-50 rounded-lg text-emerald-600 mt-0.5 border border-emerald-100 flex-shrink-0">
                    <CheckCircle className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-800">{app.job?.title}</h4>
                    <p className="text-xs text-primary-600 font-semibold">{app.job?.company}</p>
                    <p className="text-[10px] text-slate-500 mt-1">
                      Applied on: {new Date(app.submitted_at).toLocaleDateString()} at{' '}
                      {new Date(app.submitted_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {app.notes && (
                    <div title="Contains notes">
                      <MessageSquare className="w-4 h-4 text-slate-400" />
                    </div>
                  )}
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Details Side Panel */}
      <div className="glass-panel border-slate-200 p-6 overflow-y-auto h-full flex flex-col">
        {selectedApp ? (
          <div className="space-y-6 flex-1 flex flex-col justify-between">
            <div className="space-y-5">
              <div>
                <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-100 px-2.5 py-0.5 rounded-full">
                  Application Submitted
                </span>
                <h3 className="text-base font-bold text-slate-800 mt-3">{selectedApp.job?.title}</h3>
                <p className="text-sm text-primary-600 font-semibold">{selectedApp.job?.company}</p>
                <p className="text-xs text-slate-500 mt-0.5">{selectedApp.job?.location}</p>
              </div>

              <hr className="border-slate-100" />

              {/* Fields filled listing */}
              {selectedApp.fields_filled && selectedApp.fields_filled.length > 0 && (
                <div className="space-y-2.5">
                  <span className="text-[10px] font-bold text-slate-500 uppercase block">Fields Filled</span>
                  <div className="space-y-1.5 max-h-[160px] overflow-y-auto pr-1">
                    {selectedApp.fields_filled.map((field, idx) => (
                      <div key={idx} className="bg-slate-50 p-2.5 rounded border border-slate-200 text-[10px] flex justify-between gap-4">
                        <span className="text-slate-500 truncate max-w-[50%]" title={field.label}>
                          {field.label}
                        </span>
                        <span className="text-slate-800 font-semibold text-right truncate max-w-[50%]" title={field.value}>
                          {field.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Resume path used */}
              {selectedApp.resume_used && (
                <div className="space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase block">Resume PDF Uploaded</span>
                  <div className="text-[10px] text-slate-700 flex items-center gap-1.5 p-2 bg-slate-50 border border-slate-200 rounded">
                    <FileText className="w-3.5 h-3.5 text-primary-600" />
                    <span className="truncate">{selectedApp.resume_used.split(/[/\\]/).pop()}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Manual Notes editing */}
            <div className="pt-4 border-t border-slate-200 mt-4 space-y-3">
              <label className="text-[10px] font-bold text-slate-500 uppercase block">
                My Follow-up Notes
              </label>
              <textarea
                value={notesText}
                onChange={(e) => setNotesText(e.target.value)}
                placeholder="e.g. Interview feedback, salary range agreed, recruiter contact details..."
                rows={4}
                className="w-full glass-input text-xs"
              />
              <button
                onClick={handleSaveNotes}
                disabled={isSavingNotes}
                className="w-full glass-btn-primary py-2 text-xs font-semibold"
              >
                Save Notes
              </button>
            </div>

          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-400">
            <FileText className="w-12 h-12 text-slate-300 mb-3" />
            <p className="text-xs italic">Select an application in the list to view filled details.</p>
          </div>
        )}
      </div>

    </div>
  );
};
