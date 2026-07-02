import React, { useState, useEffect, useRef } from 'react';
import { useBot } from '../hooks/useBot';
import { useWebSocket } from '../hooks/useWebSocket';
import { AlertCircle, HelpCircle, Check, Play, SkipForward, ExternalLink, Square, Minimize2, Maximize2, UploadCloud, FileText, Trash2, X, ChevronsRight } from 'lucide-react';
import api from '../lib/api';

function deduplicateString(text?: string): string {
  if (!text) return "";
  const normalized = text.replace(/\s+/g, ' ').trim();
  const words = normalized.split(' ');
  const nWords = words.length;
  
  if (nWords >= 2) {
    for (let half = Math.floor(nWords / 2); half >= 1; half--) {
      const part1 = words.slice(0, half).join(' ');
      const part2 = words.slice(half, 2 * half).join(' ');
      
      const norm1 = part1.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
      const norm2 = part2.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
      
      if (norm1 === norm2 && norm1) {
        const remaining = words.slice(2 * half).join(' ');
        return remaining ? part1 + ' ' + remaining : part1;
      }
    }
  }

  const nChars = normalized.length;
  for (let halfLen = Math.floor(nChars / 2); halfLen >= 3; halfLen--) {
    const part1 = normalized.slice(0, halfLen).trim();
    const part2 = normalized.slice(halfLen, 2 * halfLen).trim();
    
    const norm1 = part1.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
    const norm2 = part2.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
    
    if (norm1 === norm2 && norm1) {
      const remaining = normalized.slice(2 * halfLen).trim();
      return remaining ? part1 + ' ' + remaining : part1;
    }
  }

  return text;
}

export const PopupModal: React.FC = () => {
  const { activePopup, currentJob } = useBot();
  const { answerPopup, skipJob, closePopup, manualDone } = useWebSocket();
  
  const [textAnswer, setTextAnswer] = useState('');
  const [selectAnswer, setSelectAnswer] = useState('');
  const [numberAnswer, setNumberAnswer] = useState<number>(0);
  const [checkboxAnswer, setCheckboxAnswer] = useState(false);
  const [saveAnswer, setSaveAnswer] = useState(true);
  const [isMinimized, setIsMinimized] = useState(false);

  // States for file upload
  const [uploadedFile, setUploadedFile] = useState<{ filepath: string; filename: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [selectedLinkedInFile, setSelectedLinkedInFile] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // States for manual review edit popup
  const [tempFields, setTempFields] = useState<any[]>([]);
  const [editingFieldLabel, setEditingFieldLabel] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<any>('');

  // States for confirm_message and confirm_email
  const [editedMessageText, setEditedMessageText] = useState<string>('');
  const [editedEmailSubject, setEditedEmailSubject] = useState<string>('');
  const [editedEmailBody, setEditedEmailBody] = useState<string>('');

  useEffect(() => {
    if (activePopup) {
      const defaultText = activePopup.current_value !== undefined ? String(activePopup.current_value) : '';
      setTextAnswer(defaultText);

      const defaultSelect = activePopup.current_value !== undefined ? String(activePopup.current_value) : (activePopup.options?.[0] || '');
      setSelectAnswer(defaultSelect);

      let defaultNum = 0;
      if (activePopup.current_value !== undefined) {
        const parsed = parseInt(String(activePopup.current_value));
        defaultNum = isNaN(parsed) ? 0 : parsed;
      } else {
        defaultNum = activePopup.min !== undefined ? activePopup.min : 0;
      }
      setNumberAnswer(defaultNum);

      const defaultCheckbox = activePopup.current_value !== undefined ? (String(activePopup.current_value) === 'true' || String(activePopup.current_value) === '1' || String(activePopup.current_value).toLowerCase() === 'yes') : false;
      setCheckboxAnswer(defaultCheckbox);

      setSaveAnswer(true);
      setUploadedFile(null);
      setUploading(false);
      setDragActive(false);
      setSelectedLinkedInFile(activePopup.options && activePopup.options.length > 0 ? activePopup.options[0] : '');
      if (activePopup.type === 'review_submit' && activePopup.fields) {
        setTempFields(JSON.parse(JSON.stringify(activePopup.fields)));
      } else {
        setTempFields([]);
      }
      setEditingFieldLabel(null);
      setEditValue('');

      // Initialize follow-up message & email states
      setEditedMessageText(activePopup.type === 'confirm_message' ? String(activePopup.current_value || '') : '');
      setEditedEmailSubject(activePopup.type === 'confirm_email' ? String(activePopup.subject || '') : '');
      setEditedEmailBody(activePopup.type === 'confirm_email' ? String(activePopup.current_value || '') : '');
    }
  }, [activePopup]);

  useEffect(() => {
    const preventDefault = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
    };
    window.addEventListener('dragover', preventDefault);
    window.addEventListener('drop', preventDefault);
    return () => {
      window.removeEventListener('dragover', preventDefault);
      window.removeEventListener('drop', preventDefault);
    };
  }, []);

  if (!activePopup) return null;

  if (isMinimized) {
    return (
      <div className="fixed bottom-6 right-6 z-50 animate-bounce-short">
        <button
          onClick={() => setIsMinimized(false)}
          className="flex items-center gap-3 px-5 py-3 bg-primary-600 text-white font-semibold rounded-full shadow-lg hover:bg-primary-700 hover:shadow-xl transition-all border-2 border-white/20"
        >
          <Maximize2 className="w-5 h-5" />
          <span>Pending Action ({activePopup.company || currentJob?.company || 'Job'})</span>
        </button>
      </div>
    );
  }

  const handleStopBot = async () => {
    try {
      await api.post('/api/bot/stop');
    } catch (e) {
      console.error('Failed to stop bot', e);
    }
  };

  const handleClosePopup = () => {
    closePopup(activePopup.popup_id);
  };

  const jobUrl = activePopup.job_url || currentJob?.url;

  const startEditing = (label: string, currentValue: any) => {
    setEditingFieldLabel(label);
    setEditValue(currentValue);
  };

  const saveEdit = (label: string) => {
    setTempFields(prev =>
      prev.map(f => (f.label === label ? { ...f, value: String(editValue) } : f))
    );
    setEditingFieldLabel(null);
  };

  const cancelEdit = () => {
    setEditingFieldLabel(null);
  };

  const renderEditInput = (field: any) => {
    if (field.field_type === 'select' || field.field_type === 'radio') {
      if (field.options && field.options.length > 0) {
        return (
          <select
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="w-full glass-input text-xs bg-white py-1 px-2 border rounded text-slate-800"
          >
            {field.options.map((opt: string) => (
              <option key={opt} value={opt} className="text-slate-900">
                {opt}
              </option>
            ))}
          </select>
        );
      }
    }
    
    if (field.field_type === 'checkbox') {
      const isTrue = editValue === 'true' || editValue === true || String(editValue).toLowerCase() === 'yes';
      return (
        <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
          <input
            type="checkbox"
            checked={isTrue}
            onChange={(e) => setEditValue(e.target.checked ? 'Yes' : 'No')}
            className="accent-primary-600 rounded"
          />
          Yes / Checked
        </label>
      );
    }

    if (field.field_type === 'textarea') {
      return (
        <textarea
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          className="w-full glass-input text-xs py-1.5 px-2 border rounded text-slate-800 min-h-[80px] resize-y"
          rows={3}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.shiftKey)) {
              e.preventDefault();
              saveEdit(field.label);
            }
          }}
        />
      );
    }

    if (field.field_type === 'number') {
      return (
        <input
          type="number"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          className="w-full glass-input text-xs py-1 px-2 border rounded text-slate-800"
        />
      );
    }

    // Default to textarea
    return (
      <textarea
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        className="w-full glass-input text-xs py-1.5 px-2 border rounded text-slate-800 min-h-[60px] resize-y"
        rows={2}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.shiftKey)) {
            e.preventDefault();
            saveEdit(field.label);
          }
        }}
      />
    );
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      await handleFileUpload(e.target.files[0]);
    }
  };

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/api/profile/upload-file', formData, {
        headers: {
          'Content-Type': undefined,
        },
      });
      setUploadedFile({
        filepath: response.data.filepath,
        filename: response.data.filename,
      });
    } catch (error) {
      console.error('File upload failed:', error);
      alert('Failed to upload file. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const clearUploadedFile = () => {
    setUploadedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (activePopup.type === 'question_text') {
      answerPopup(activePopup.popup_id, textAnswer, saveAnswer);
    } else if (activePopup.type === 'question_select') {
      answerPopup(activePopup.popup_id, selectAnswer, saveAnswer);
    } else if (activePopup.type === 'question_number') {
      answerPopup(activePopup.popup_id, numberAnswer, saveAnswer);
    } else if (activePopup.type === 'question_file') {
      if (selectedLinkedInFile) {
        answerPopup(activePopup.popup_id, `__use_linkedin_file__:${selectedLinkedInFile}`, false);
      } else if (uploadedFile) {
        answerPopup(activePopup.popup_id, uploadedFile.filepath, false);
      }
    } else if (activePopup.type === 'question_checkbox') {
      answerPopup(activePopup.popup_id, checkboxAnswer ? 'Yes' : 'No', saveAnswer);
    } else if (activePopup.type === 'confirm_message') {
      answerPopup(activePopup.popup_id, editedMessageText, true);
    } else if (activePopup.type === 'confirm_email') {
      answerPopup(activePopup.popup_id, {
        subject: editedEmailSubject,
        body: editedEmailBody
      }, true);
    }
  };

  const handleConfirm = () => {
    if (activePopup.type === 'confirm') {
      answerPopup(activePopup.popup_id, true, false);
    } else if (activePopup.type === 'confirm_message') {
      answerPopup(activePopup.popup_id, editedMessageText, true);
    } else if (activePopup.type === 'confirm_email') {
      answerPopup(activePopup.popup_id, {
        subject: editedEmailSubject,
        body: editedEmailBody
      }, true);
    }
  };

  const handleCancel = () => {
    if (activePopup.type === 'confirm') {
      answerPopup(activePopup.popup_id, false, false);
    } else if (activePopup.type === 'confirm_message' || activePopup.type === 'confirm_email') {
      answerPopup(activePopup.popup_id, null, false);
    }
  };

  const errorElement = activePopup.error_message ? (
    <div className="flex items-start gap-2.5 p-3.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl text-xs font-medium animate-fade-in shadow-sm">
      <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="font-bold mb-0.5">Validation Error:</p>
        <p className="opacity-95 leading-relaxed">{activePopup.error_message}</p>
      </div>
    </div>
  ) : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-lg overflow-hidden glass-panel shadow-2xl animate-slide-up border-slate-200">
        
        {/* Floating current task banner */}
        <div className="px-6 py-3 bg-primary-50 border-b border-primary-100 text-xs text-primary-700 font-semibold tracking-wide flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span>PAUSED IN APPLICATION</span>
            <span className="opacity-50">|</span>
            <span className="text-primary-900">{activePopup.company || currentJob?.company || 'LinkedIn'}</span>
          </div>
          <div className="flex items-center gap-4">
            {jobUrl && (
              <button 
                type="button"
                onClick={() => window.open(jobUrl, '_blank')} 
                className="flex items-center gap-1.5 text-primary-600 hover:text-primary-800 transition-colors"
                title="View job"
              >
                <ExternalLink className="w-4 h-4" />
                <span>View Job</span>
              </button>
            )}
            <button 
              type="button"
              onClick={handleStopBot} 
              className="flex items-center gap-1.5 text-rose-600 hover:text-rose-800 transition-colors"
              title="Stop bot"
            >
              <Square className="w-4 h-4" />
              <span>Stop Bot</span>
            </button>
            <button 
              type="button"
              onClick={handleClosePopup} 
              className="flex items-center gap-1.5 text-slate-600 hover:text-slate-800 transition-colors"
              title="Close popup"
            >
              <X className="w-4 h-4" />
              <span>Close</span>
            </button>
            <button 
              type="button"
              onClick={() => setIsMinimized(true)} 
              className="flex items-center gap-1.5 text-slate-600 hover:text-slate-800 transition-colors"
              title="Go to dashboard"
            >
              <Minimize2 className="w-4 h-4" />
              <span>Dashboard</span>
            </button>
          </div>
        </div>

        <div className="p-6">
          <div className="flex items-start gap-4 mb-4">
            <div className="p-2.5 bg-primary-50 rounded-lg text-primary-600 border border-primary-100">
              {activePopup.type === 'manual_action' ? (
                <AlertCircle className="w-6 h-6 animate-pulse" />
              ) : (
                <HelpCircle className="w-6 h-6" />
              )}
            </div>
            <div className="flex-1">
              <div className="mb-2">
                {(activePopup.job_title || currentJob?.title) && (
                  <p className="text-xs text-slate-500 mb-0.5">
                    Job: <span className="text-slate-800 font-semibold">{activePopup.job_title || currentJob?.title}</span>
                  </p>
                )}
                {(activePopup.company || currentJob?.company) && (
                  <p className="text-[11px] text-slate-400">
                    Company: <span className="text-slate-600 font-medium">{activePopup.company || currentJob?.company}</span>
                  </p>
                )}
              </div>
              <h3 className="text-lg font-bold text-slate-900">{activePopup.title}</h3>
            </div>
          </div>

          <hr className="border-slate-100 my-4" />

          {/* Form container */}
          <form onSubmit={handleSubmit} className="space-y-5">
            
            {/* TYPE 1: Manual Action */}
            {activePopup.type === 'manual_action' && (
              <div className="space-y-4">
                <p className="text-sm text-slate-600 leading-relaxed bg-slate-50 p-4 rounded-lg border border-slate-200">
                  {deduplicateString(activePopup.message)}
                </p>
                <button
                  type="button"
                  onClick={() => manualDone(activePopup.popup_id)}
                  className="w-full glass-btn-primary py-2.5"
                >
                  <Play className="w-4 h-4 fill-current" />
                  {activePopup.action_label || 'Done / Continue'}
                </button>
              </div>
            )}

            {/* TYPE 2: Question Text */}
            {activePopup.type === 'question_text' && (
              <div className="space-y-4">
                <label className="block text-sm font-semibold text-slate-700">
                  "{deduplicateString(activePopup.question)}"
                </label>
                {errorElement}
                <textarea
                  required
                  placeholder={activePopup.field_hint || 'Write your answer...'}
                  value={textAnswer}
                  onChange={(e) => setTextAnswer(e.target.value)}
                  className="w-full glass-input text-sm min-h-[100px] resize-y py-2 px-3"
                  autoFocus
                  rows={4}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.shiftKey)) {
                      e.preventDefault();
                      handleSubmit(e);
                    }
                  }}
                />
                <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={saveAnswer}
                    onChange={(e) => setSaveAnswer(e.target.checked)}
                    className="accent-primary-600 rounded"
                  />
                  Remember this answer (save in Q&A Bank)
                </label>
                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => skipJob(activePopup.popup_id)}
                    className="flex-1 glass-btn-secondary"
                  >
                    <SkipForward className="w-4 h-4" />
                    Skip this job
                  </button>
                  <button
                    type="button"
                    onClick={() => answerPopup(activePopup.popup_id, '__skip_question__', false)}
                    className="flex-1 glass-btn-secondary"
                  >
                    <ChevronsRight className="w-4 h-4" />
                    Skip Question
                  </button>
                  <button type="submit" className="flex-1 glass-btn-primary">
                    <Check className="w-4 h-4" />
                    Confirm
                  </button>
                </div>
              </div>
            )}

            {/* TYPE 3: Question Select */}
            {activePopup.type === 'question_select' && (
              <div className="space-y-4">
                <label className="block text-sm font-semibold text-slate-700">
                  "{deduplicateString(activePopup.question)}"
                </label>
                {errorElement}
                {activePopup.options && activePopup.options.length > 4 ? (
                  <select
                    value={selectAnswer}
                    onChange={(e) => setSelectAnswer(e.target.value)}
                    className="w-full glass-input text-sm bg-white"
                  >
                    {activePopup.options.map((opt) => (
                      <option key={opt} value={opt} className="text-slate-900">
                        {opt}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="space-y-2">
                    {activePopup.options?.map((opt) => (
                      <label
                        key={opt}
                        className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                          selectAnswer === opt
                            ? 'border-primary-500 bg-primary-50 text-primary-700 font-bold'
                            : 'border-slate-200 bg-slate-50/50 hover:border-slate-300 text-slate-600'
                        }`}
                      >
                        <input
                          type="radio"
                          name="popup_option"
                          value={opt}
                          checked={selectAnswer === opt}
                          onChange={() => setSelectAnswer(opt)}
                          className="accent-primary-600"
                        />
                        {opt}
                      </label>
                    ))}
                  </div>
                )}

                <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={saveAnswer}
                    onChange={(e) => setSaveAnswer(e.target.checked)}
                    className="accent-primary-600 rounded"
                  />
                  Remember this answer (save in Q&A Bank)
                </label>
                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => skipJob(activePopup.popup_id)}
                    className="flex-1 glass-btn-secondary"
                  >
                    <SkipForward className="w-4 h-4" />
                    Skip this job
                  </button>
                  <button
                    type="button"
                    onClick={() => answerPopup(activePopup.popup_id, '__skip_question__', false)}
                    className="flex-1 glass-btn-secondary"
                  >
                    <ChevronsRight className="w-4 h-4" />
                    Skip Question
                  </button>
                  <button type="submit" className="flex-1 glass-btn-primary">
                    <Check className="w-4 h-4" />
                    Confirm
                  </button>
                </div>
              </div>
            )}

            {/* TYPE 4: Question Number */}
            {activePopup.type === 'question_number' && (
              <div className="space-y-4">
                <label className="block text-sm font-semibold text-slate-700">
                  "{deduplicateString(activePopup.question)}"
                </label>
                {errorElement}
                <input
                  type="number"
                  required
                  min={activePopup.min ?? 0}
                  max={activePopup.max ?? 100}
                  value={numberAnswer}
                  onChange={(e) => setNumberAnswer(parseInt(e.target.value) || 0)}
                  className="w-full glass-input text-sm"
                  autoFocus
                />
                <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={saveAnswer}
                    onChange={(e) => setSaveAnswer(e.target.checked)}
                    className="accent-primary-600 rounded"
                  />
                  Remember this answer (save in Q&A Bank)
                </label>
                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => skipJob(activePopup.popup_id)}
                    className="flex-1 glass-btn-secondary"
                  >
                    <SkipForward className="w-4 h-4" />
                    Skip this job
                  </button>
                  <button
                    type="button"
                    onClick={() => answerPopup(activePopup.popup_id, '__skip_question__', false)}
                    className="flex-1 glass-btn-secondary"
                  >
                    <ChevronsRight className="w-4 h-4" />
                    Skip Question
                  </button>
                  <button type="submit" className="flex-1 glass-btn-primary">
                    <Check className="w-4 h-4" />
                    Confirm
                  </button>
                </div>
              </div>
            )}

            {/* TYPE 8: Question Checkbox */}
            {activePopup.type === 'question_checkbox' && (
              <div className="space-y-4">
                <label className="block text-sm font-semibold text-slate-700">
                  "{deduplicateString(activePopup.question)}"
                </label>
                {errorElement}
                <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl">
                  <label className="flex items-center gap-3 text-sm text-slate-700 cursor-pointer select-none font-medium">
                    <input
                      type="checkbox"
                      checked={checkboxAnswer}
                      onChange={(e) => setCheckboxAnswer(e.target.checked)}
                      className="accent-primary-600 rounded w-4 h-4 cursor-pointer"
                      autoFocus
                    />
                    Yes / Checked
                  </label>
                </div>
                <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={saveAnswer}
                    onChange={(e) => setSaveAnswer(e.target.checked)}
                    className="accent-primary-600 rounded"
                  />
                  Remember this answer (save in Q&A Bank)
                </label>
                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => skipJob(activePopup.popup_id)}
                    className="flex-1 glass-btn-secondary"
                  >
                    <SkipForward className="w-4 h-4" />
                    Skip this job
                  </button>
                  <button
                    type="button"
                    onClick={() => answerPopup(activePopup.popup_id, '__skip_question__', false)}
                    className="flex-1 glass-btn-secondary"
                  >
                    <ChevronsRight className="w-4 h-4" />
                    Skip Question
                  </button>
                  <button type="submit" className="flex-1 glass-btn-primary">
                    <Check className="w-4 h-4" />
                    Confirm
                  </button>
                </div>
              </div>
            )}

            {/* TYPE 7: Question File (Upload cover letter, resume, etc.) */}
            {activePopup.type === 'question_file' && (
              <div className="space-y-4 animate-fade-in">
                <label className="block text-sm font-semibold text-slate-700">
                  "{deduplicateString(activePopup.question)}"
                </label>
                {errorElement}
                {activePopup.message && (
                  <p className="text-xs text-slate-500 italic">
                    {deduplicateString(activePopup.message)}
                  </p>
                )}

                {/* Option selector if LinkedIn files exist */}
                {activePopup.options && activePopup.options.length > 0 && (
                  <div className="space-y-2.5">
                    <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                      Select a file already on LinkedIn
                    </span>
                    <div className="grid grid-cols-1 gap-2">
                      {activePopup.options.map((opt: string) => (
                        <label
                          key={opt}
                          className={`flex items-center gap-3 p-3 rounded-xl border text-xs cursor-pointer transition-all ${
                            selectedLinkedInFile === opt
                              ? 'border-primary-500 bg-primary-50/30 text-primary-900 font-semibold shadow-sm'
                              : 'border-slate-200 hover:border-slate-300 text-slate-600 bg-slate-50/20 hover:bg-slate-50/60'
                          }`}
                        >
                          <input
                            type="radio"
                            name="linkedin_file"
                            value={opt}
                            checked={selectedLinkedInFile === opt}
                            onChange={() => {
                              setSelectedLinkedInFile(opt);
                              clearUploadedFile();
                            }}
                            className="accent-primary-600 w-4 h-4 cursor-pointer"
                          />
                          <FileText className={`w-4 h-4 flex-shrink-0 ${selectedLinkedInFile === opt ? 'text-primary-500' : 'text-slate-400'}`} />
                          <span className="truncate flex-1">{opt}</span>
                        </label>
                      ))}

                      <label
                        className={`flex items-center gap-3 p-3 rounded-xl border text-xs cursor-pointer transition-all ${
                          selectedLinkedInFile === ''
                            ? 'border-primary-500 bg-primary-50/30 text-primary-900 font-semibold shadow-sm'
                            : 'border-slate-200 hover:border-slate-300 text-slate-600 bg-slate-50/20 hover:bg-slate-50/60'
                        }`}
                      >
                        <input
                          type="radio"
                          name="linkedin_file"
                          value=""
                          checked={selectedLinkedInFile === ''}
                          onChange={() => {
                            setSelectedLinkedInFile('');
                          }}
                          className="accent-primary-600 w-4 h-4 cursor-pointer"
                        />
                        <UploadCloud className={`w-4 h-4 flex-shrink-0 ${selectedLinkedInFile === '' ? 'text-primary-500' : 'text-slate-400'}`} />
                        <span className="flex-1">Upload a new file...</span>
                      </label>
                    </div>
                  </div>
                )}

                {/* Upload zone: show if there are no options, or if "Upload a new file..." is selected */}
                {(!activePopup.options || activePopup.options.length === 0 || selectedLinkedInFile === '') && (
                  <div
                    onDragEnter={handleDrag}
                    onDragOver={handleDrag}
                    onDragLeave={handleDrag}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-300 flex flex-col items-center justify-center gap-3 ${
                      dragActive
                        ? 'border-primary-500 bg-primary-50/50 scale-[0.98]'
                        : 'border-slate-300 hover:border-primary-400 bg-slate-50/30 hover:bg-slate-50/80'
                    }`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      className="hidden"
                      onChange={handleFileChange}
                      accept=".pdf,.doc,.docx,.txt,.rtf,.jpg,.jpeg,.png,.gif,.pdf,.doc,.docx,.txt,.JPG,.JPEG,.PNG,.GIF"
                    />

                    {uploading ? (
                      <div className="flex flex-col items-center gap-2">
                        <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
                        <p className="text-xs font-semibold text-primary-600">Uploading file...</p>
                      </div>
                    ) : uploadedFile ? (
                      <div className="flex items-center gap-3 bg-emerald-50 text-emerald-800 border border-emerald-200 px-4 py-3 rounded-lg w-full" onClick={(e) => e.stopPropagation()}>
                        <FileText className="w-8 h-8 text-emerald-600 flex-shrink-0" />
                        <div className="flex-1 text-left min-w-0">
                          <p className="text-xs font-bold truncate">{uploadedFile.filename}</p>
                          <p className="text-[10px] text-emerald-600">Ready to submit</p>
                        </div>
                        <button
                          type="button"
                          onClick={clearUploadedFile}
                          className="p-1 hover:bg-emerald-100 rounded text-emerald-700 transition-colors"
                          title="Remove file"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ) : (
                      <>
                        <div className="p-3 bg-white shadow-sm rounded-full text-slate-400 group-hover:text-primary-500 transition-colors">
                          <UploadCloud className="w-6 h-6" />
                        </div>
                        <div>
                          <p className="text-xs font-bold text-slate-700">
                            Drag & drop your file here, or <span className="text-primary-600 underline">browse</span>
                          </p>
                          <p className="text-[10px] text-slate-400 mt-1">
                            Supports {activePopup.file_hint || 'PDF, DOC, DOCX, TXT'} (Max 512 KB)
                          </p>
                        </div>
                      </>
                    )}
                  </div>
                )}

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => skipJob(activePopup.popup_id)}
                    className="flex-1 glass-btn-secondary"
                  >
                    <SkipForward className="w-4 h-4" />
                    Skip this job
                  </button>
                  <button
                    type="button"
                    onClick={() => answerPopup(activePopup.popup_id, '__skip_question__', false)}
                    className="flex-1 glass-btn-secondary"
                  >
                    <ChevronsRight className="w-4 h-4" />
                    Skip Question
                  </button>
                  <button
                    type="submit"
                    className="flex-1 glass-btn-primary"
                    disabled={(!uploadedFile && !selectedLinkedInFile) || uploading}
                  >
                    <Check className="w-4 h-4" />
                    Confirm & Submit
                  </button>
                </div>
              </div>
            )}

            {/* TYPE 5: Confirmation */}
            {activePopup.type === 'confirm' && (
              <div className="space-y-4">
                <p className="text-sm text-slate-600 leading-relaxed bg-slate-50 p-4 rounded-lg border border-slate-200">
                  {deduplicateString(activePopup.message)}
                </p>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={handleCancel}
                    className="flex-1 glass-btn-secondary text-xs"
                  >
                    {activePopup.cancel_label || 'Cancel / Skip'}
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirm}
                    className="flex-1 glass-btn-primary text-xs"
                  >
                    <Check className="w-4 h-4" />
                    {activePopup.confirm_label || 'Confirm'}
                  </button>
                </div>
              </div>
            )}

            {/* TYPE: Confirm Message */}
            {activePopup.type === 'confirm_message' && (
              <div className="space-y-4">
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs text-slate-600 space-y-1">
                  <p><span className="font-bold text-slate-800">Recruiter:</span> {activePopup.recruiter_name} ({activePopup.connection_status} degree)</p>
                  <p><span className="font-bold text-slate-800">Job:</span> {activePopup.job_title} @ {activePopup.company}</p>
                </div>
                <div className="space-y-2">
                  <label className="block text-xs font-bold text-slate-700">LinkedIn Message Body (Editable):</label>
                  <textarea
                    value={editedMessageText}
                    onChange={(e) => setEditedMessageText(e.target.value)}
                    className="w-full text-xs font-mono p-3 bg-slate-50 border border-slate-200 rounded-lg min-h-[120px] focus:outline-none focus:border-primary-500"
                    rows={6}
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={handleCancel}
                    className="flex-1 glass-btn-secondary text-xs"
                  >
                    Skip Message
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirm}
                    className="flex-1 glass-btn-primary text-xs"
                  >
                    <Check className="w-4 h-4" />
                    Send Message
                  </button>
                </div>
              </div>
            )}

            {/* TYPE: Confirm Email */}
            {activePopup.type === 'confirm_email' && (
              <div className="space-y-4">
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs text-slate-600 space-y-1">
                  <p><span className="font-bold text-slate-800">Recruiter:</span> {activePopup.recruiter_name} | <span className="font-bold text-slate-800">Email:</span> {activePopup.email}</p>
                  <p><span className="font-bold text-slate-800">Job:</span> {activePopup.job_title} @ {activePopup.company}</p>
                </div>
                <div className="space-y-2">
                  <label className="block text-xs font-bold text-slate-700">Email Subject:</label>
                  <input
                    type="text"
                    value={editedEmailSubject}
                    onChange={(e) => setEditedEmailSubject(e.target.value)}
                    className="w-full text-xs p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-primary-500"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-xs font-bold text-slate-700">Email Body (Editable):</label>
                  <textarea
                    value={editedEmailBody}
                    onChange={(e) => setEditedEmailBody(e.target.value)}
                    className="w-full text-xs font-mono p-3 bg-slate-50 border border-slate-200 rounded-lg min-h-[150px] focus:outline-none focus:border-primary-500"
                    rows={8}
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={handleCancel}
                    className="flex-1 glass-btn-secondary text-xs"
                  >
                    Skip Email
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirm}
                    className="flex-1 glass-btn-primary text-xs"
                  >
                    <Check className="w-4 h-4" />
                    Send Email
                  </button>
                </div>
              </div>
            )}


            {/* TYPE 6: Review Submit */}
            {activePopup.type === 'review_submit' && (
              <div className="space-y-4">
                <p className="text-sm text-slate-600 leading-relaxed">
                  {deduplicateString(activePopup.message) || 'Please review the information filled by the bot below. You can edit any field before submitting.'}
                </p>
                
                <div className="max-h-64 overflow-y-auto pr-1 space-y-3 border border-slate-100 rounded-lg p-2 bg-slate-50/30">
                  {tempFields.map((field, idx) => {
                    const isEditing = editingFieldLabel === field.label;
                    return (
                      <div key={idx} className="p-3 rounded-lg border border-slate-100 bg-white shadow-sm flex flex-col gap-2 transition-all">
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                            {deduplicateString(field.label)}
                          </span>
                          {field.source !== 'user_edit' && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 font-semibold uppercase">
                              {field.source || 'resolved'}
                            </span>
                          )}
                        </div>

                        {isEditing ? (
                          <div className="space-y-2 mt-1">
                            {renderEditInput(field)}
                            <div className="flex gap-2 justify-end">
                              <button
                                type="button"
                                onClick={cancelEdit}
                                className="px-2 py-1 text-[10px] font-semibold text-slate-500 hover:text-slate-700 bg-slate-100 hover:bg-slate-200 rounded flex items-center gap-1"
                              >
                                Cancel
                              </button>
                              <button
                                type="button"
                                onClick={() => saveEdit(field.label)}
                                className="px-2 py-1 text-[10px] font-semibold text-white bg-primary-600 hover:bg-primary-700 rounded flex items-center gap-1"
                              >
                                Save
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-start justify-between gap-4 mt-1">
                            <span className="text-sm font-medium text-slate-700 break-all whitespace-pre-wrap">
                              {field.value || <em className="text-slate-400">Empty</em>}
                            </span>
                            <button
                              type="button"
                              onClick={() => startEditing(field.label, field.value)}
                              className="px-2 py-1 text-[10px] font-semibold text-primary-600 hover:text-primary-700 hover:bg-primary-50 rounded border border-primary-100 flex items-center gap-1 transition-all"
                            >
                              Edit
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {tempFields.length === 0 && (
                    <p className="text-xs text-slate-400 text-center py-4">No fields recorded for this application.</p>
                  )}
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => skipJob(activePopup.popup_id)}
                    className="flex-1 glass-btn-secondary py-2"
                  >
                    Cancel (Skip job)
                  </button>
                  <button
                    type="button"
                    onClick={() => answerPopup(activePopup.popup_id, { fields: tempFields }, false)}
                    className="flex-1 glass-btn-primary py-2"
                    disabled={editingFieldLabel !== null}
                  >
                    <Check className="w-4 h-4" />
                    Confirm & Submit
                  </button>
                </div>
              </div>
            )}

          </form>
        </div>
      </div>
    </div>
  );
};
