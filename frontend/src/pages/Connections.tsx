import React, { useState, useEffect, useRef } from 'react';
import api from '../lib/api';
import { 
  Users, Mail, Phone, Globe, Trash2, Edit2, Check, X, Search, 
  Settings, Send, ArrowUpRight, MessageSquare,
  Calendar, Briefcase, ExternalLink, Copy
} from 'lucide-react';

interface RecruiterContact {
  id: number;
  job_id?: number;
  name: string;
  linkedin_url: string;
  email?: string;
  phone?: string;
  websites: string[];
  connection_status: string;
  company?: string;
  notes?: string;
  discovered_at: string;
  updated_at: string;
  job?: {
    id: number;
    title: string;
    company: string;
    url: string;
  };
}

interface ContactLog {
  id: number;
  recruiter_id?: number;
  job_id?: number;
  template_id?: number;
  type: 'linkedin_message' | 'email';
  status: 'sent' | 'failed' | 'pending';
  subject?: string;
  body: string;
  sent_at: string;
  is_non_connected: boolean;
  recruiter?: RecruiterContact;
  job?: {
    id: number;
    title: string;
    company: string;
    url: string;
  };
}

interface MessageTemplate {
  id: number;
  name: string;
  language: string;
  type: 'linkedin_message' | 'email';
  subject?: string;
  body: string;
  is_active: boolean;
  used_day?: number;
  used_week?: number;
  used_month?: number;
  used_all?: number;
}

export const Connections: React.FC = () => {
  const [contacts, setContacts] = useState<RecruiterContact[]>([]);
  const [logs, setLogs] = useState<ContactLog[]>([]);
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [stats, setStats] = useState({ weekly_non_connected_sent: 0, weekly_non_connected_limit: 10 });
  
  const [activeTab, setActiveTab] = useState<'contacts' | 'templates'>('contacts');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedContactIds, setExpandedContactIds] = useState<Record<number, boolean>>({});
  
  // Editing state for recruiter contact notes
  const [editingContactId, setEditingContactId] = useState<number | null>(null);
  const [contactNotes, setContactNotes] = useState('');

  // Template variation states
  const [expandedTemplateId, setExpandedTemplateId] = useState<number | null>(null);
  const [editingTemplate, setEditingTemplate] = useState<MessageTemplate | null>(null);

  // New Template creation form state
  const [isCreatingLinkedin, setIsCreatingLinkedin] = useState(false);
  const [isCreatingEmail, setIsCreatingEmail] = useState(false);
  const [newTemplateName, setNewTemplateName] = useState('');
  const [newTemplateLanguage, setNewTemplateLanguage] = useState<'pt' | 'en'>('pt');
  const [newTemplateSubject, setNewTemplateSubject] = useState('');
  const [newTemplateBody, setNewTemplateBody] = useState('');

  // Focus tracking and cursor insertion refs
  const [activeField, setActiveField] = useState<'edit-body' | 'edit-subject' | 'create-body' | 'create-subject' | null>(null);
  
  const editBodyRef = useRef<HTMLTextAreaElement>(null);
  const editSubjectRef = useRef<HTMLInputElement>(null);
  const createBodyRef = useRef<HTMLTextAreaElement>(null);
  const createSubjectRef = useRef<HTMLInputElement>(null);

  const insertTextAtCursor = (
    ref: React.RefObject<HTMLTextAreaElement | HTMLInputElement | null>,
    textToInsert: string,
    updateValue: (val: string) => void
  ) => {
    const el = ref.current;
    if (!el) return;

    const start = el.selectionStart ?? 0;
    const end = el.selectionEnd ?? 0;
    const value = el.value;

    const newValue = value.substring(0, start) + textToInsert + value.substring(end);
    updateValue(newValue);

    setTimeout(() => {
      el.focus();
      el.setSelectionRange(start + textToInsert.length, start + textToInsert.length);
    }, 0);
  };

  const handleInsertPlaceholder = (placeholder: string) => {
    if (activeField === 'create-subject') {
      insertTextAtCursor(createSubjectRef, placeholder, setNewTemplateSubject);
    } else if (activeField === 'create-body') {
      insertTextAtCursor(createBodyRef, placeholder, setNewTemplateBody);
    } else if (activeField === 'edit-subject' && editingTemplate) {
      insertTextAtCursor(editSubjectRef, placeholder, (val) => {
        setEditingTemplate(prev => prev ? { ...prev, subject: val } : null);
      });
    } else if (activeField === 'edit-body' && editingTemplate) {
      insertTextAtCursor(editBodyRef, placeholder, (val) => {
        setEditingTemplate(prev => prev ? { ...prev, body: val } : null);
      });
    }
  };

  const toggleExpandContact = (id: number) => {
    setExpandedContactIds(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleCopyText = (text: string) => {
    navigator.clipboard.writeText(text);
    alert('Message text copied to clipboard!');
  };

  const fetchContacts = async () => {
    try {
      const res = await api.get('/api/connections');
      setContacts(res.data);
    } catch (err) {
      console.error('Failed to fetch contacts:', err);
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await api.get('/api/connections/logs');
      setLogs(res.data);
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    }
  };

  const fetchTemplates = async () => {
    try {
      const res = await api.get('/api/connections/templates');
      setTemplates(res.data);
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await api.get('/api/connections/stats');
      setStats(res.data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  useEffect(() => {
    fetchContacts();
    fetchLogs();
    fetchTemplates();
    fetchStats();
  }, []);

  const handleDeleteContact = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this recruiter contact?')) return;
    try {
      await api.delete(`/api/connections/${id}`);
      setContacts(prev => prev.filter(c => c.id !== id));
    } catch (err) {
      alert('Failed to delete recruiter contact.');
    }
  };

  const handleStartEditContact = (c: RecruiterContact) => {
    setEditingContactId(c.id);
    setContactNotes(c.notes || '');
  };

  const handleSaveContactNotes = async (id: number) => {
    try {
      const res = await api.put(`/api/connections/${id}`, { notes: contactNotes });
      setContacts(prev => prev.map(c => c.id === id ? res.data : c));
      setEditingContactId(null);
    } catch (err) {
      alert('Failed to save notes.');
    }
  };

  const handleStartEditTemplate = (t: MessageTemplate) => {
    if (expandedTemplateId === t.id) {
      setExpandedTemplateId(null);
      setEditingTemplate(null);
    } else {
      setExpandedTemplateId(t.id);
      setEditingTemplate({ ...t });
    }
  };

  const handleSaveTemplate = async () => {
    if (!editingTemplate) return;
    try {
      const res = await api.put(`/api/connections/templates/${editingTemplate.id}`, {
        name: editingTemplate.name,
        language: editingTemplate.language,
        subject: editingTemplate.subject,
        body: editingTemplate.body,
        is_active: editingTemplate.is_active
      });
      setTemplates(prev => prev.map(t => t.id === editingTemplate.id ? res.data : t));
      setExpandedTemplateId(null);
      setEditingTemplate(null);
      alert('Template updated successfully!');
    } catch (err) {
      alert('Failed to save template variation.');
    }
  };

  const handleToggleTemplateActive = async (t: MessageTemplate, activeState: boolean) => {
    try {
      const res = await api.put(`/api/connections/templates/${t.id}`, {
        is_active: activeState
      });
      setTemplates(prev => prev.map(item => item.id === t.id ? res.data : item));
      if (editingTemplate && editingTemplate.id === t.id) {
        setEditingTemplate(prev => prev ? { ...prev, is_active: activeState } : null);
      }
    } catch (err) {
      console.error('Failed to toggle template active status:', err);
    }
  };

  const handleCreateTemplate = async (type: 'linkedin_message' | 'email') => {
    if (!newTemplateName || !newTemplateBody) {
      alert('Please fill out the name and body.');
      return;
    }
    try {
      const res = await api.post('/api/connections/templates', {
        name: newTemplateName,
        language: newTemplateLanguage,
        type: type,
        subject: type === 'email' ? newTemplateSubject : undefined,
        body: newTemplateBody,
        is_active: true
      });
      setTemplates(prev => [...prev, res.data]);
      setNewTemplateName('');
      setNewTemplateLanguage('pt');
      setNewTemplateSubject('');
      setNewTemplateBody('');
      if (type === 'linkedin_message') {
        setIsCreatingLinkedin(false);
      } else {
        setIsCreatingEmail(false);
      }
      alert('Template created successfully!');
    } catch (err) {
      alert('Failed to create template variation.');
    }
  };

  const handleDeleteTemplate = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this template variation?')) return;
    try {
      await api.delete(`/api/connections/templates/${id}`);
      setTemplates(prev => prev.filter(t => t.id !== id));
      if (expandedTemplateId === id) {
        setExpandedTemplateId(null);
        setEditingTemplate(null);
      }
    } catch (err) {
      alert('Failed to delete template.');
    }
  };

  const filteredContacts = contacts.filter(c => {
    const query = searchQuery.toLowerCase();
    return (
      c.name.toLowerCase().includes(query) ||
      (c.company || '').toLowerCase().includes(query) ||
      (c.email || '').toLowerCase().includes(query) ||
      (c.notes || '').toLowerCase().includes(query)
    );
  });

  const placeholders = [
    '{recruiter_name}',
    '{recruiter_first_name}',
    '{job}',
    '{company}',
    '{candidate_name}',
    '{resume_link}'
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Title & Headers */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Connections Hub</h1>
          <p className="text-xs text-slate-500 font-medium">Manage recruiters, track outreach messages, and customize follow-up templates</p>
        </div>

        <div className="flex items-center gap-3 bg-white px-4 py-2.5 rounded-2xl border border-slate-200 shadow-sm self-start lg:self-center">
          <div className="p-2 bg-primary-50 rounded-xl text-primary-600 flex-shrink-0">
            <Send className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex justify-between text-[10px] font-bold text-slate-700 mb-1 gap-2">
              <span>Weekly InMails Limit</span>
              <span className={stats.weekly_non_connected_sent >= stats.weekly_non_connected_limit ? "text-rose-600 font-bold" : "text-primary-600"}>
                {stats.weekly_non_connected_sent} / {stats.weekly_non_connected_limit}
              </span>
            </div>
            <div className="w-32 bg-slate-100 rounded-full h-1.5 overflow-hidden">
              <div 
                className={`h-1.5 rounded-full transition-all duration-500 ${
                  stats.weekly_non_connected_sent >= stats.weekly_non_connected_limit 
                    ? 'bg-rose-500' 
                    : 'bg-primary-500'
                }`}
                style={{ width: `${Math.min(100, (stats.weekly_non_connected_sent / stats.weekly_non_connected_limit) * 100)}%` }}
              ></div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs Menu */}
      <div className="flex border-b border-slate-200 overflow-x-auto">
        <button
          onClick={() => setActiveTab('contacts')}
          className={`px-5 py-3 font-semibold text-xs border-b-2 transition-all flex items-center gap-2 cursor-pointer flex-shrink-0 ${
            activeTab === 'contacts'
              ? 'border-primary-500 text-primary-600 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <Users className="w-4 h-4" />
          Recruiter Contacts ({contacts.length})
        </button>
        <button
          onClick={() => setActiveTab('templates')}
          className={`px-5 py-3 font-semibold text-xs border-b-2 transition-all flex items-center gap-2 cursor-pointer flex-shrink-0 ${
            activeTab === 'templates'
              ? 'border-primary-500 text-primary-600 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          <Settings className="w-4 h-4" />
          Message Templates ({templates.length})
        </button>
      </div>

      {/* Tab Contents */}
      <div className="glass-panel p-6 border-slate-200 shadow-sm min-h-[400px]">
        {activeTab === 'contacts' && (
          <div className="space-y-6">
            {/* Search Bar */}
            <div className="relative max-w-md">
              <Search className="absolute left-3.5 top-3 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search recruiters, companies, or emails..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 text-xs rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:border-primary-500 focus:bg-white transition-all"
              />
            </div>

            {filteredContacts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                <Users className="w-12 h-12 stroke-[1.5] mb-2 text-slate-300" />
                <p className="text-sm font-medium">No recruiter contacts discovered yet.</p>
                <p className="text-xs opacity-75 mt-0.5">Contacts appear here automatically after jobs are applied.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredContacts.map(c => {
                  const recruiterLog = logs.find(l => l.recruiter_id === c.id);
                  const isExpanded = !!expandedContactIds[c.id];

                  return (
                    <div 
                      key={c.id} 
                      className="glass-card flex flex-col justify-between bg-white border border-slate-200 rounded-2xl p-5 hover:border-primary-300 hover:shadow-md transition-all duration-200 space-y-4"
                    >
                      {/* Top Header Row */}
                      <div className="flex justify-between items-start gap-2 text-left">
                        <div className="min-w-0">
                          <a 
                            href={c.linkedin_url} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            className="text-sm font-bold text-slate-800 hover:text-primary-600 flex items-center gap-1"
                          >
                            <span className="truncate">{c.name}</span>
                            <ArrowUpRight className="w-3.5 h-3.5 opacity-60 flex-shrink-0" />
                          </a>
                          <span className="text-xs text-slate-400 font-semibold">{c.company || 'Unknown Company'}</span>
                        </div>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold flex-shrink-0 ${
                          c.connection_status === '1st' 
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' 
                            : c.connection_status === '2nd' 
                            ? 'bg-amber-50 text-amber-700 border border-amber-100' 
                            : 'bg-slate-100 text-slate-600'
                        }`}>
                          {c.connection_status} Degree
                        </span>
                      </div>

                      {/* Linked Job Details */}
                      {c.job ? (
                        <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 flex gap-2.5 items-start text-left">
                          <Briefcase className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                          <div className="min-w-0 flex-1">
                            <span className="text-[9px] font-bold text-slate-400 uppercase block tracking-wider mb-0.5">Applied Job</span>
                            <a 
                              href={c.job.url} 
                              target="_blank" 
                              rel="noopener noreferrer" 
                              className="text-xs font-bold text-slate-800 hover:text-primary-600 flex items-center gap-1"
                            >
                              <span className="truncate block max-w-[180px]">{c.job.title}</span>
                              <ExternalLink className="w-3 h-3 opacity-60 flex-shrink-0" />
                            </a>
                            <span className="text-[10px] text-slate-500 font-semibold block truncate">{c.job.company}</span>
                          </div>
                        </div>
                      ) : (
                        <div className="bg-slate-50 border border-slate-100 border-dashed rounded-xl p-3 flex gap-2.5 items-start text-left text-slate-400">
                          <Briefcase className="w-4 h-4 mt-0.5 flex-shrink-0" />
                          <span className="text-xs font-medium italic">No job linked to this recruiter</span>
                        </div>
                      )}

                      {/* Contact Details */}
                      <div className="space-y-1.5 pt-1 text-xs text-left">
                        {c.email && (
                          <div className="flex items-center gap-2 text-slate-600">
                            <Mail className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                            <span className="truncate">{c.email}</span>
                          </div>
                        )}
                        {c.phone && (
                          <div className="flex items-center gap-2 text-slate-600">
                            <Phone className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                            <span>{c.phone}</span>
                          </div>
                        )}
                        {c.websites && c.websites.length > 0 && (
                          <div className="flex items-center gap-2 text-slate-600">
                            <Globe className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                            <a href={c.websites[0]} target="_blank" rel="noopener noreferrer" className="underline hover:text-primary-600 truncate">
                              Website
                            </a>
                          </div>
                        )}
                        {!c.email && !c.phone && (!c.websites || c.websites.length === 0) && (
                          <span className="text-slate-400 italic text-[11px]">No contact details found</span>
                        )}
                      </div>

                      {/* Outreach Message Logs */}
                      <div className="border-t border-slate-100 pt-3 text-left">
                        {recruiterLog ? (
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                recruiterLog.type === 'email' ? 'bg-primary-50 text-primary-700' : 'bg-indigo-50 text-indigo-700'
                              }`}>
                                {recruiterLog.type === 'email' ? 'Gmail Follow-up' : 'LinkedIn InMail'}
                              </span>
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                recruiterLog.status === 'sent' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'
                              }`}>
                                {recruiterLog.status.toUpperCase()}
                              </span>
                            </div>

                            <button
                              type="button"
                              onClick={() => toggleExpandContact(c.id)}
                              className="text-xs font-bold text-primary-600 hover:text-primary-700 flex items-center gap-1 cursor-pointer bg-transparent border-0 p-0"
                            >
                              <MessageSquare className="w-3.5 h-3.5" />
                              {isExpanded ? 'Hide outreach message' : 'View outreach message'}
                            </button>

                            {isExpanded && (
                              <div className="bg-slate-50 border border-slate-100 rounded-xl p-3 mt-2 text-left space-y-2 relative group">
                                <button
                                  onClick={() => handleCopyText(recruiterLog.body)}
                                  className="absolute top-2 right-2 p-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-500 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                                  title="Copy message"
                                >
                                  <Copy className="w-3.5 h-3.5" />
                                </button>
                                {recruiterLog.subject && (
                                  <div className="text-[11px] font-bold text-slate-800">
                                    <span className="text-slate-400 font-semibold">Subject:</span> {recruiterLog.subject}
                                  </div>
                                )}
                                <div className="text-[11px] font-mono text-slate-600 whitespace-pre-line leading-relaxed max-h-32 overflow-y-auto pr-6">
                                  {recruiterLog.body}
                                </div>
                                <div className="text-[9px] text-slate-400 flex items-center gap-1 font-semibold">
                                  <Calendar className="w-3 h-3" />
                                  <span>{new Date(recruiterLog.sent_at).toLocaleString()}</span>
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5 text-slate-400 text-xs">
                            <span className="w-2 h-2 rounded-full bg-slate-300"></span>
                            <span>No follow-up message sent yet</span>
                          </div>
                        )}
                      </div>

                      {/* Notes Section */}
                      <div className="border-t border-slate-100 pt-3 flex flex-col gap-1.5 text-left">
                        <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">Recruiter Notes</span>
                        {editingContactId === c.id ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={contactNotes}
                              onChange={(e) => setContactNotes(e.target.value)}
                              className="px-2 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs w-full focus:outline-none focus:border-primary-500 focus:bg-white"
                              placeholder="Add recruiter notes..."
                            />
                            <button 
                              onClick={() => handleSaveContactNotes(c.id)} 
                              className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded-lg flex-shrink-0"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                            <button 
                              onClick={() => setEditingContactId(null)} 
                              className="p-1.5 text-slate-400 hover:bg-slate-100 rounded-lg flex-shrink-0"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex justify-between items-start group/notes gap-2 min-h-6">
                            <span className="text-xs text-slate-600 font-medium">
                              {c.notes ? c.notes : <span className="text-slate-400 italic">No notes added.</span>}
                            </span>
                            <button 
                              onClick={() => handleStartEditContact(c)} 
                              className="opacity-0 group-hover/notes:opacity-100 text-slate-400 hover:text-slate-600 p-0.5 rounded transition-opacity"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Card Actions */}
                      <div className="border-t border-slate-100 pt-3 flex justify-end">
                        <button
                          onClick={() => handleDeleteContact(c.id)}
                          className="text-xs font-semibold text-rose-500 hover:text-rose-700 bg-rose-50/50 hover:bg-rose-50 px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          Delete Contact
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {activeTab === 'templates' && (
          <div className="space-y-8 animate-fade-in">
            {/* Section 1: LinkedIn Messages */}
            <div className="space-y-4">
              <div className="flex justify-between items-center border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2 text-left">
                  <span className="p-1.5 bg-indigo-50 text-indigo-600 rounded-lg"><Send className="w-4 h-4" /></span>
                  <h2 className="text-base font-bold text-slate-800">LinkedIn Message Templates</h2>
                </div>
                <button
                  onClick={() => {
                    setIsCreatingLinkedin(true);
                    setIsCreatingEmail(false);
                    setExpandedTemplateId(null);
                    setEditingTemplate(null);
                    setNewTemplateName('');
                    setNewTemplateLanguage('pt');
                    setNewTemplateBody('');
                  }}
                  className="glass-btn-primary py-2 px-3 text-xs"
                >
                  Add LinkedIn Template
                </button>
              </div>

              {/* Inline Create LinkedIn Template Card */}
              {isCreatingLinkedin && (
                <form 
                  onSubmit={(e) => { e.preventDefault(); handleCreateTemplate('linkedin_message'); }}
                  className="p-5 border border-primary-200 rounded-2xl bg-primary-50/10 shadow-sm space-y-4 text-left animate-slide-up"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-black text-primary-800 uppercase tracking-wider">New LinkedIn Template</h3>
                    <button 
                      type="button" 
                      onClick={() => setIsCreatingLinkedin(false)}
                      className="p-1 text-slate-400 hover:bg-slate-100 rounded-lg"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <label className="block text-xs font-bold text-slate-600">Template Name:</label>
                      <input
                        type="text"
                        placeholder="e.g. Friendly Short, Professional Formal"
                        value={newTemplateName}
                        onChange={(e) => setNewTemplateName(e.target.value)}
                        className="w-full px-3 py-2 text-xs rounded-xl bg-white border border-slate-200 focus:outline-none focus:border-primary-500"
                        required
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="block text-xs font-bold text-slate-600">Language:</label>
                      <select
                        value={newTemplateLanguage}
                        onChange={(e) => setNewTemplateLanguage(e.target.value as 'pt' | 'en')}
                        className="w-full px-3 py-2 text-xs rounded-xl bg-white border border-slate-200 focus:outline-none focus:border-primary-500 font-semibold text-slate-700"
                      >
                        <option value="pt">Portuguese (PT)</option>
                        <option value="en">English (EN)</option>
                      </select>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-1.5">
                      <label className="block text-xs font-bold text-slate-600">Message Body Template:</label>
                      <div className="flex flex-wrap gap-1 items-center">
                        <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider mr-1">Insert tags:</span>
                        {placeholders.map(p => (
                          <button
                            key={p}
                            type="button"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => handleInsertPlaceholder(p)}
                            className="px-1.5 py-0.5 bg-slate-100 hover:bg-primary-50 hover:text-primary-700 text-[9px] text-slate-600 rounded transition-all font-mono font-bold select-none cursor-pointer"
                          >
                            {p}
                          </button>
                        ))}
                      </div>
                    </div>
                    <textarea
                      ref={createBodyRef}
                      placeholder="Write your LinkedIn follow-up message template here..."
                      value={newTemplateBody}
                      onChange={(e) => setNewTemplateBody(e.target.value)}
                      onFocus={() => setActiveField('create-body')}
                      className="w-full px-4 py-3 text-xs font-mono rounded-xl bg-white border border-slate-200 focus:outline-none focus:border-primary-500 min-h-[160px]"
                      rows={6}
                      required
                    />
                  </div>

                  <div className="flex justify-end gap-2">
                    <button 
                      type="button" 
                      onClick={() => setIsCreatingLinkedin(false)}
                      className="glass-btn-secondary py-2 px-4 text-xs font-bold"
                    >
                      Cancel
                    </button>
                    <button 
                      type="submit" 
                      className="glass-btn-primary py-2 px-4 text-xs font-bold"
                    >
                      Create Template
                    </button>
                  </div>
                </form>
              )}

              {/* LinkedIn Templates Accordion List */}
              <div className="space-y-3">
                {templates.filter(t => t.type === 'linkedin_message').length === 0 ? (
                  <div className="p-6 border border-dashed border-slate-200 rounded-2xl text-center text-slate-400 text-xs font-medium">
                    No LinkedIn templates configured. Click 'Add LinkedIn Template' to create one.
                  </div>
                ) : (
                  templates.filter(t => t.type === 'linkedin_message').map(t => {
                    const isExpanded = expandedTemplateId === t.id;

                    return (
                      <div 
                        key={t.id}
                        className={`border rounded-2xl transition-all ${
                          isExpanded 
                            ? 'border-primary-500 bg-primary-50/10 shadow-sm' 
                            : 'border-slate-100 bg-slate-50/50 hover:bg-slate-50'
                        }`}
                      >
                        {/* Header Row (Click to expand) */}
                        <div 
                          onClick={() => handleStartEditTemplate(t)}
                          className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer select-none text-left"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            {/* Language Badge */}
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider flex-shrink-0 ${
                              t.language === 'pt' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' : 'bg-blue-50 text-blue-700 border border-blue-100'
                            }`}>
                              {t.language === 'pt' ? 'PT-BR' : 'EN'}
                            </span>
                            <span className="font-bold text-xs text-slate-800 truncate">{t.name}</span>
                          </div>

                          <div className="flex items-center justify-between sm:justify-end gap-4" onClick={(e) => e.stopPropagation()}>
                            <span className="text-[10px] text-slate-500 font-semibold">
                              Sent: <strong className="text-primary-600 font-bold">{t.used_all || 0}</strong> times
                            </span>

                            <div className="flex items-center gap-2">
                              {/* Toggle Checkbox */}
                              <label className="relative inline-flex items-center cursor-pointer">
                                <input 
                                  type="checkbox" 
                                  checked={t.is_active} 
                                  onChange={(e) => handleToggleTemplateActive(t, e.target.checked)}
                                  className="sr-only peer"
                                />
                                <div className="w-7 h-4 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-primary-600"></div>
                                <span className="ml-1 text-[9px] font-bold text-slate-500">{t.is_active ? 'Active' : 'Off'}</span>
                              </label>

                              {/* Delete button */}
                              <button
                                onClick={() => handleDeleteTemplate(t.id)}
                                className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-slate-100/50 transition-colors"
                                title="Delete template"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        </div>

                        {/* Editor Form Panel (Expanded) */}
                        {isExpanded && editingTemplate && (
                          <div className="p-5 border-t border-slate-100 bg-white rounded-b-2xl space-y-4 text-left animate-fade-in" onClick={(e) => e.stopPropagation()}>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                              <div className="space-y-1">
                                <label className="block text-xs font-bold text-slate-600">Template Name:</label>
                                <input
                                  type="text"
                                  value={editingTemplate.name}
                                  onChange={(e) => setEditingTemplate({ ...editingTemplate, name: e.target.value })}
                                  className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:border-primary-500 focus:bg-white transition-all font-semibold"
                                />
                              </div>
                              <div className="space-y-1">
                                <label className="block text-xs font-bold text-slate-600">Language:</label>
                                <select
                                  value={editingTemplate.language}
                                  onChange={(e) => setEditingTemplate({ ...editingTemplate, language: e.target.value })}
                                  className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:border-primary-500 focus:bg-white transition-all font-semibold text-slate-700"
                                >
                                  <option value="pt">Portuguese (PT)</option>
                                  <option value="en">English (EN)</option>
                                </select>
                              </div>
                            </div>

                            <div className="space-y-1.5">
                              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-1.5">
                                <label className="block text-xs font-bold text-slate-600">Message Body Template:</label>
                                <div className="flex flex-wrap gap-1 items-center">
                                  <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider mr-1">Insert tags:</span>
                                  {placeholders.map(p => (
                                    <button
                                      key={p}
                                      type="button"
                                      onMouseDown={(e) => e.preventDefault()}
                                      onClick={() => handleInsertPlaceholder(p)}
                                      className="px-1.5 py-0.5 bg-slate-100 hover:bg-primary-50 hover:text-primary-700 text-[9px] text-slate-600 rounded transition-all font-mono font-bold select-none cursor-pointer"
                                    >
                                      {p}
                                    </button>
                                  ))}
                                </div>
                              </div>
                              <textarea
                                ref={editBodyRef}
                                value={editingTemplate.body}
                                onChange={(e) => setEditingTemplate({ ...editingTemplate, body: e.target.value })}
                                onFocus={() => setActiveField('edit-body')}
                                className="w-full px-4 py-3 text-xs font-mono rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:border-primary-500 focus:bg-white transition-all min-h-[160px]"
                                rows={6}
                              />
                            </div>

                            <div className="flex justify-end gap-2">
                              <button 
                                type="button" 
                                onClick={() => { setExpandedTemplateId(null); setEditingTemplate(null); }}
                                className="glass-btn-secondary py-2 px-4 text-xs font-bold"
                              >
                                Cancel
                              </button>
                              <button
                                onClick={handleSaveTemplate}
                                className="glass-btn-primary py-2 px-4 text-xs font-bold flex items-center gap-1.5"
                              >
                                <Check className="w-4 h-4" />
                                Save Changes
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Section 2: Gmail Emails */}
            <div className="space-y-4">
              <div className="flex justify-between items-center border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2 text-left">
                  <span className="p-1.5 bg-emerald-50 text-emerald-600 rounded-lg"><Mail className="w-4 h-4" /></span>
                  <h2 className="text-base font-bold text-slate-800">Gmail Email Templates</h2>
                </div>
                <button
                  onClick={() => {
                    setIsCreatingEmail(true);
                    setIsCreatingLinkedin(false);
                    setExpandedTemplateId(null);
                    setEditingTemplate(null);
                    setNewTemplateName('');
                    setNewTemplateLanguage('pt');
                    setNewTemplateSubject('');
                    setNewTemplateBody('');
                  }}
                  className="glass-btn-primary py-2 px-3 text-xs"
                >
                  Add Email Template
                </button>
              </div>

              {/* Inline Create Email Template Card */}
              {isCreatingEmail && (
                <form 
                  onSubmit={(e) => { e.preventDefault(); handleCreateTemplate('email'); }}
                  className="p-5 border border-primary-200 rounded-2xl bg-primary-50/10 shadow-sm space-y-4 text-left animate-slide-up"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-black text-primary-800 uppercase tracking-wider">New Gmail Template</h3>
                    <button 
                      type="button" 
                      onClick={() => setIsCreatingEmail(false)}
                      className="p-1 text-slate-400 hover:bg-slate-100 rounded-lg"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <label className="block text-xs font-bold text-slate-600">Template Name:</label>
                      <input
                        type="text"
                        placeholder="e.g. Friendly Short, Professional Formal"
                        value={newTemplateName}
                        onChange={(e) => setNewTemplateName(e.target.value)}
                        className="w-full px-3 py-2 text-xs rounded-xl bg-white border border-slate-200 focus:outline-none focus:border-primary-500"
                        required
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="block text-xs font-bold text-slate-600">Language:</label>
                      <select
                        value={newTemplateLanguage}
                        onChange={(e) => setNewTemplateLanguage(e.target.value as 'pt' | 'en')}
                        className="w-full px-3 py-2 text-xs rounded-xl bg-white border border-slate-200 focus:outline-none focus:border-primary-500 font-semibold text-slate-700"
                      >
                        <option value="pt">Portuguese (PT)</option>
                        <option value="en">English (EN)</option>
                      </select>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <label className="block text-xs font-bold text-slate-600">Email Subject:</label>
                    <input
                      ref={createSubjectRef}
                      type="text"
                      placeholder="e.g. Candidatura - Vaga de {job}"
                      value={newTemplateSubject}
                      onChange={(e) => setNewTemplateSubject(e.target.value)}
                      onFocus={() => setActiveField('create-subject')}
                      className="w-full px-3 py-2 text-xs rounded-xl bg-white border border-slate-200 focus:outline-none focus:border-primary-500"
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-1.5">
                      <label className="block text-xs font-bold text-slate-600">Template Body:</label>
                      <div className="flex flex-wrap gap-1 items-center">
                        <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider mr-1">Insert tags:</span>
                        {placeholders.map(p => (
                          <button
                            key={p}
                            type="button"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => handleInsertPlaceholder(p)}
                            className="px-1.5 py-0.5 bg-slate-100 hover:bg-primary-50 hover:text-primary-700 text-[9px] text-slate-600 rounded transition-all font-mono font-bold select-none cursor-pointer"
                          >
                            {p}
                          </button>
                        ))}
                      </div>
                    </div>
                    <textarea
                      ref={createBodyRef}
                      placeholder="Write your email body template here..."
                      value={newTemplateBody}
                      onChange={(e) => setNewTemplateBody(e.target.value)}
                      onFocus={() => setActiveField('create-body')}
                      className="w-full px-4 py-3 text-xs font-mono rounded-xl bg-white border border-slate-200 focus:outline-none focus:border-primary-500 min-h-[160px]"
                      rows={6}
                      required
                    />
                  </div>

                  <div className="flex justify-end gap-2">
                    <button 
                      type="button" 
                      onClick={() => setIsCreatingEmail(false)}
                      className="glass-btn-secondary py-2 px-4 text-xs font-bold"
                    >
                      Cancel
                    </button>
                    <button 
                      type="submit" 
                      className="glass-btn-primary py-2 px-4 text-xs font-bold"
                    >
                      Create Template
                    </button>
                  </div>
                </form>
              )}

              {/* Email Templates Accordion List */}
              <div className="space-y-3">
                {templates.filter(t => t.type === 'email').length === 0 ? (
                  <div className="p-6 border border-dashed border-slate-200 rounded-2xl text-center text-slate-400 text-xs font-medium">
                    No email templates configured. Click 'Add Email Template' to create one.
                  </div>
                ) : (
                  templates.filter(t => t.type === 'email').map(t => {
                    const isExpanded = expandedTemplateId === t.id;

                    return (
                      <div 
                        key={t.id}
                        className={`border rounded-2xl transition-all ${
                          isExpanded 
                            ? 'border-primary-500 bg-primary-50/10 shadow-sm' 
                            : 'border-slate-100 bg-slate-50/50 hover:bg-slate-50'
                        }`}
                      >
                        {/* Header Row (Click to expand) */}
                        <div 
                          onClick={() => handleStartEditTemplate(t)}
                          className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer select-none text-left"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            {/* Language Badge */}
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider flex-shrink-0 ${
                              t.language === 'pt' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' : 'bg-blue-50 text-blue-700 border border-blue-100'
                            }`}>
                              {t.language === 'pt' ? 'PT-BR' : 'EN'}
                            </span>
                            <span className="font-bold text-xs text-slate-800 truncate">{t.name}</span>
                          </div>

                          <div className="flex items-center justify-between sm:justify-end gap-4" onClick={(e) => e.stopPropagation()}>
                            <span className="text-[10px] text-slate-500 font-semibold">
                              Sent: <strong className="text-primary-600 font-bold">{t.used_all || 0}</strong> times
                            </span>

                            <div className="flex items-center gap-2">
                              {/* Toggle Checkbox */}
                              <label className="relative inline-flex items-center cursor-pointer">
                                <input 
                                  type="checkbox" 
                                  checked={t.is_active} 
                                  onChange={(e) => handleToggleTemplateActive(t, e.target.checked)}
                                  className="sr-only peer"
                                />
                                <div className="w-7 h-4 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-primary-600"></div>
                                <span className="ml-1 text-[9px] font-bold text-slate-500">{t.is_active ? 'Active' : 'Off'}</span>
                              </label>

                              {/* Delete button */}
                              <button
                                onClick={() => handleDeleteTemplate(t.id)}
                                className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-slate-100/50 transition-colors"
                                title="Delete template"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </div>
                        </div>

                        {/* Editor Form Panel (Expanded) */}
                        {isExpanded && editingTemplate && (
                          <div className="p-5 border-t border-slate-100 bg-white rounded-b-2xl space-y-4 text-left animate-fade-in" onClick={(e) => e.stopPropagation()}>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                              <div className="space-y-1">
                                <label className="block text-xs font-bold text-slate-600">Template Name:</label>
                                <input
                                  type="text"
                                  value={editingTemplate.name}
                                  onChange={(e) => setEditingTemplate({ ...editingTemplate, name: e.target.value })}
                                  className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:border-primary-500 focus:bg-white transition-all font-semibold"
                                />
                              </div>
                              <div className="space-y-1">
                                <label className="block text-xs font-bold text-slate-600">Language:</label>
                                <select
                                  value={editingTemplate.language}
                                  onChange={(e) => setEditingTemplate({ ...editingTemplate, language: e.target.value })}
                                  className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:border-primary-500 focus:bg-white transition-all font-semibold text-slate-700"
                                >
                                  <option value="pt">Portuguese (PT)</option>
                                  <option value="en">English (EN)</option>
                                </select>
                              </div>
                            </div>

                            <div className="space-y-1">
                              <label className="block text-xs font-bold text-slate-600">Email Subject:</label>
                              <input
                                ref={editSubjectRef}
                                type="text"
                                value={editingTemplate.subject || ''}
                                onChange={(e) => setEditingTemplate({ ...editingTemplate, subject: e.target.value })}
                                onFocus={() => setActiveField('edit-subject')}
                                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:border-primary-500 focus:bg-white transition-all font-semibold"
                              />
                            </div>

                            <div className="space-y-1.5">
                              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-1.5">
                                <label className="block text-xs font-bold text-slate-600">Message Body Template:</label>
                                <div className="flex flex-wrap gap-1 items-center">
                                  <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider mr-1">Insert tags:</span>
                                  {placeholders.map(p => (
                                    <button
                                      key={p}
                                      type="button"
                                      onMouseDown={(e) => e.preventDefault()}
                                      onClick={() => handleInsertPlaceholder(p)}
                                      className="px-1.5 py-0.5 bg-slate-100 hover:bg-primary-50 hover:text-primary-700 text-[9px] text-slate-600 rounded transition-all font-mono font-bold select-none cursor-pointer"
                                    >
                                      {p}
                                    </button>
                                  ))}
                                </div>
                              </div>
                              <textarea
                                ref={editBodyRef}
                                value={editingTemplate.body}
                                onChange={(e) => setEditingTemplate({ ...editingTemplate, body: e.target.value })}
                                onFocus={() => setActiveField('edit-body')}
                                className="w-full px-4 py-3 text-xs font-mono rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:border-primary-500 focus:bg-white transition-all min-h-[160px]"
                                rows={6}
                              />
                            </div>

                            <div className="flex justify-end gap-2">
                              <button 
                                type="button" 
                                onClick={() => { setExpandedTemplateId(null); setEditingTemplate(null); }}
                                className="glass-btn-secondary py-2 px-4 text-xs font-bold"
                              >
                                Cancel
                              </button>
                              <button
                                onClick={handleSaveTemplate}
                                className="glass-btn-primary py-2 px-4 text-xs font-bold flex items-center gap-1.5"
                              >
                                <Check className="w-4 h-4" />
                                Save Changes
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
