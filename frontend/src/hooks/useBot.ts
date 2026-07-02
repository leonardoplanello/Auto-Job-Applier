import { create } from 'zustand';

export interface Job {
  id: number;
  linkedin_id: string;
  title: string;
  company: string;
  location?: string;
  remote?: boolean;
  description?: string;
  url: string;
  easy_apply: boolean;
  status: string;
  discovered_at: string;
  search_id?: number;
  skip_reason?: string;
  priority?: number;
  connected_profiles?: string[];
}

export interface LogEntry {
  id: number;
  session_id: string;
  timestamp: string;
  level: 'success' | 'info' | 'warning' | 'error' | 'action' | 'debug';
  category: 'auth' | 'search' | 'apply' | 'qa' | 'bot' | 'system';
  message: string;
  company?: string;
  job_title?: string;
  job_url?: string;
  job_id?: number;
  extra: Record<string, any>;
}

export interface PopupPayload {
  popup_id: string;
  type: 'manual_action' | 'question_text' | 'question_select' | 'question_number' | 'confirm' | 'review_submit' | 'question_file' | 'question_checkbox' | 'confirm_message' | 'confirm_email';
  title: string;
  message?: string;
  action_label?: string;
  question?: string;
  options?: string[];
  field_hint?: string;
  file_hint?: string;
  company?: string;
  job_title?: string;
  job_url?: string;
  min?: number;
  max?: number;
  confirm_label?: string;
  cancel_label?: string;
  fields?: any[];
  current_value?: string | number;
  error_message?: string;
  recruiter_name?: string;
  recruiter_url?: string;
  connection_status?: string;
  email?: string;
  subject?: string;
}

interface BotStats {
  found: number;
  applied: number;
  skipped: number;
  failed: number;
  popups: number;
}

export type PageName = 'dashboard' | 'tasks' | 'search' | 'jobs' | 'applications' | 'qa' | 'logs' | 'settings' | 'analytics' | 'connections';

interface BotStore {
  status: string;
  sessionId: string | null;
  mode: 'review' | 'auto';
  stats: BotStats;
  currentJob: Job | null;
  activePopup: PopupPayload | null;
  logs: LogEntry[];
  currentPage: PageName;
  jobSearchQuery: string;
  appSearchQuery: string;
  jobStatusFilter: string;
  jobsRefreshCounter: number;
  selectedJobIdForApp: number | null;
  
  setBotStatus: (status: string) => void;
  setSessionId: (id: string | null) => void;
  setBotMode: (mode: 'review' | 'auto') => void;
  setStats: (stats: BotStats) => void;
  setCurrentJob: (job: Job | null) => void;
  setActivePopup: (popup: PopupPayload | null) => void;
  addLog: (log: LogEntry) => void;
  setLogs: (logs: LogEntry[]) => void;
  clearLogs: () => void;
  updateStats: (diff: Partial<BotStats>) => void;
  setCurrentPage: (page: PageName) => void;
  setJobSearchQuery: (query: string) => void;
  setAppSearchQuery: (query: string) => void;
  setSelectedJobIdForApp: (id: number | null) => void;
  setJobStatusFilter: (status: string) => void;
  triggerJobsRefresh: () => void;
}

export const useBot = create<BotStore>((set) => ({
  status: 'idle',
  sessionId: null,
  mode: 'auto',
  stats: { found: 0, applied: 0, skipped: 0, failed: 0, popups: 0 },
  currentJob: null,
  activePopup: null,
  logs: [],
  currentPage: 'dashboard',
  jobSearchQuery: '',
  appSearchQuery: '',
  jobStatusFilter: 'discovered',
  jobsRefreshCounter: 0,
  selectedJobIdForApp: null,

  setBotStatus: (status) => set({ status }),
  setSessionId: (sessionId) => set({ sessionId }),
  setBotMode: (mode) => set({ mode }),
  setStats: (stats) => set({ stats }),
  setCurrentJob: (currentJob) => set({ currentJob }),
  setActivePopup: (activePopup) => set({ activePopup }),
  addLog: (log) => set((state) => {
    // Avoid duplicates in logs
    if (state.logs.some((l) => l.id === log.id)) return state;
    return { logs: [log, ...state.logs].slice(0, 300) }; // cap at 300 logs in memory
  }),
  setLogs: (logs) => set({ logs }),
  clearLogs: () => set({ logs: [] }),
  updateStats: (diff) => set((state) => ({ stats: { ...state.stats, ...diff } })),
  setCurrentPage: (currentPage) => set({ currentPage }),
  setJobSearchQuery: (jobSearchQuery) => set({ jobSearchQuery }),
  setAppSearchQuery: (appSearchQuery) => set({ appSearchQuery }),
  setSelectedJobIdForApp: (selectedJobIdForApp) => set({ selectedJobIdForApp }),
  setJobStatusFilter: (jobStatusFilter) => set({ jobStatusFilter }),
  triggerJobsRefresh: () => set((state) => ({ jobsRefreshCounter: state.jobsRefreshCounter + 1 })),
}));
