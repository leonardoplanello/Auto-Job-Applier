import React, { useEffect, useState, useRef } from 'react';
import api, { API_BASE_URL } from '../lib/api';
import { Plus, Edit2, Trash2, Download, Upload, Search, X, Check } from 'lucide-react';

interface QAEntry {
  id: number;
  question: string;
  answer: string;
  field_type: string;
  times_used: number;
  notes: string | null;
  created_at: string;
}

export const QABank: React.FC = () => {
  const [qaList, setQaList] = useState<QAEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  // Form States
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [fieldType, setFieldType] = useState('text');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchQA = async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/api/qa', {
        params: { q: searchQuery }
      });
      setQaList(res.data);
    } catch (err) {
      console.error('Failed to load QA Entries:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchQA();
  }, [searchQuery]);

  const handleOpenAddModal = () => {
    setCurrentId(null);
    setQuestion('');
    setAnswer('');
    setFieldType('text');
    setNotes('');
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (entry: QAEntry) => {
    setCurrentId(entry.id);
    setQuestion(entry.question);
    setAnswer(entry.answer);
    setFieldType(entry.field_type);
    setNotes(entry.notes || '');
    setIsModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this answer from the Q&A bank?')) return;
    try {
      await api.delete(`/api/qa/${id}`);
      setQaList((prev) => prev.filter((qa) => qa.id !== id));
    } catch (err) {
      alert('Failed to delete answer.');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    const payload = { question, answer, field_type: fieldType, notes };
    
    try {
      if (currentId) {
        await api.put(`/api/qa/${currentId}`, payload);
      } else {
        await api.post('/api/qa', payload);
      }
      setIsModalOpen(false);
      fetchQA();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error saving answer in the Q&A bank.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleImportCsv = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/api/qa/import', formData, {
        headers: { 'Content-Type': undefined }
      });
      alert(res.data.message || 'Import completed successfully!');
      fetchQA();
    } catch (err) {
      alert('Failed to import CSV file.');
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Top action row */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Q&A Bank</h2>
          <p className="text-xs text-slate-500 mt-1">
            Here are the answers that the bot has learned. You can edit or bulk-import new ones.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleImportCsv}
            accept=".csv"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="glass-btn-secondary py-2 text-xs"
          >
            <Download className="w-3.5 h-3.5" />
            Import CSV
          </button>
          
          <a
            href={`${API_BASE_URL}/api/qa/export`}
            download
            className="glass-btn-secondary py-2 text-xs"
          >
            <Upload className="w-3.5 h-3.5" />
            Export CSV
          </a>

          <button
            onClick={handleOpenAddModal}
            className="glass-btn-primary py-2 text-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Answer
          </button>
        </div>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-500">
          <Search className="w-4 h-4" />
        </span>
        <input
          type="text"
          placeholder="Search question or answer..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full glass-input pl-10 text-sm"
        />
      </div>

      {/* Main Table */}
      {isLoading && qaList.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-slate-500 text-xs italic">
          Searching answers...
        </div>
      ) : qaList.length === 0 ? (
        <div className="h-64 flex flex-col items-center justify-center text-center text-slate-500">
          <Search className="w-12 h-12 text-slate-300 mb-3" />
          <p className="text-sm">No answers recorded in the Q&A bank.</p>
        </div>
      ) : (
        <div className="glass-panel overflow-hidden border-slate-200">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500 uppercase font-bold">
                  <th className="px-6 py-4">Original Question</th>
                  <th className="px-6 py-4">Saved Answer</th>
                  <th className="px-6 py-4">Type</th>
                  <th className="px-6 py-4 text-center">Used</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-xs text-slate-600 bg-white">
                {qaList.map((qa) => (
                  <tr key={qa.id} className="hover:bg-slate-50/50">
                    <td className="px-6 py-4 font-semibold text-slate-800 max-w-xs truncate" title={qa.question}>
                      {qa.question}
                    </td>
                    <td className="px-6 py-4 font-mono text-primary-600 font-bold max-w-xs truncate" title={qa.answer}>
                      {qa.answer}
                    </td>
                    <td className="px-6 py-4 capitalize">{qa.field_type}</td>
                    <td className="px-6 py-4 text-center font-bold text-slate-500">{qa.times_used}x</td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleOpenEditModal(qa)}
                          className="p-1.5 rounded bg-slate-50 text-slate-500 hover:text-slate-800 border border-slate-200"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(qa.id)}
                          className="p-1.5 rounded bg-red-50 text-red-600 hover:text-red-800 border border-red-100"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Edit/Add Modal Overlay */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md glass-panel shadow-2xl p-6 border-slate-200 animate-slide-up bg-white">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-800">
                {currentId ? 'Edit Answer' : 'New Q&A Answer'}
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 rounded-md text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase">Original Question</label>
                <textarea
                  required
                  rows={2}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="e.g. How many years of experience do you have with React?"
                  className="w-full glass-input text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase">Saved Answer</label>
                <input
                  type="text"
                  required
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  placeholder="e.g. 5"
                  className="w-full glass-input text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase">Field Type</label>
                  <select
                    value={fieldType}
                    onChange={(e) => setFieldType(e.target.value)}
                    className="w-full glass-input text-xs bg-white"
                  >
                    <option value="text">Text Input</option>
                    <option value="textarea">Text Area</option>
                    <option value="select">Dropdown Select</option>
                    <option value="radio">Radio Options</option>
                    <option value="number">Numeric</option>
                    <option value="checkbox">Checkbox</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-500 uppercase">Notes (optional)</label>
                <input
                  type="text"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Free notes"
                  className="w-full glass-input text-xs"
                />
              </div>

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
