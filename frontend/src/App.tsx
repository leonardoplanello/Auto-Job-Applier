import React from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { BotStatusBar } from './components/BotStatusBar';
import { PopupModal } from './components/PopupModal';
import { Dashboard } from './pages/Dashboard';
import { SearchCriteria } from './pages/SearchCriteria';
import { Jobs } from './pages/Jobs';
import { Applications } from './pages/Applications';
import { QABank } from './pages/QABank';
import { Logs } from './pages/Logs';
import { Settings } from './pages/Settings';
import { Analytics } from './pages/Analytics';
import { 
  LayoutDashboard, Search, Briefcase, CheckCircle2, MessageSquare, 
  Terminal, Settings as SettingsIcon, Power, Network
} from 'lucide-react';
import api from './lib/api';
import { useBot, type PageName } from './hooks/useBot';


export const App: React.FC = () => {
  // Connect and initialize WebSocket listener globally
  const { isConnected } = useWebSocket();
  const { currentPage, setCurrentPage } = useBot();

  const handleEndApplication = async () => {
    if (window.confirm("Are you sure you want to end the application? This will stop the bot, close the browser, and shutdown the python server.")) {
      try {
        await api.post('/api/bot/shutdown');
        alert("The application has been stopped. You can close this browser tab now.");
      } catch (err) {
        // Since the server shuts down immediately, the connection will drop.
        // This is expected and means the backend did indeed stop!
        alert("The application has been stopped. You can close this browser tab now.");
      }
    }
  };

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard': return <Dashboard />;
      case 'search': return <SearchCriteria />;
      case 'jobs': return <Jobs />;
      case 'applications': return <Applications />;
      case 'qa': return <QABank />;
      case 'logs': return <Logs />;
      case 'settings': return <Settings />;
      case 'analytics': return <Analytics />;
      default: return <Dashboard />;
    }
  };

  const navItems = [
    { name: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard className="w-5 h-5" /> },
    { name: 'search', label: 'Search Criteria', icon: <Search className="w-5 h-5" /> },
    { name: 'jobs', label: 'Jobs', icon: <Briefcase className="w-5 h-5" /> },
    { name: 'applications', label: 'Applications', icon: <CheckCircle2 className="w-5 h-5" /> },
    { name: 'qa', label: 'Q&A Bank', icon: <MessageSquare className="w-5 h-5" /> },
    { name: 'logs', label: 'Logs & Sessions', icon: <Terminal className="w-5 h-5" /> },
    { name: 'analytics', label: 'Flow Analytics', icon: <Network className="w-5 h-5" /> },
    { name: 'settings', label: 'Settings', icon: <SettingsIcon className="w-5 h-5" /> },
  ];

  return (
    <div className="flex min-h-screen overflow-hidden bg-slate-50">
      
      {/* Sidebar Navigation - Light Theme */}
      <aside className="w-64 bg-slate-100 border-r border-slate-200 flex flex-col justify-between flex-shrink-0">
        <div>
          {/* Logo Brand Header */}
          <div className="px-6 py-5 border-b border-slate-200 flex items-center gap-3">
            <div className="w-10 h-10 flex-shrink-0">
              <svg className="w-full h-full" viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg">
                {/* Briefcase Top Handle */}
                <path d="M192 160V128C192 110.33 206.33 96 224 96H288C305.67 96 320 110.33 320 128V160" stroke="#0b7ae8" strokeWidth="24" strokeLinecap="round" />
                {/* Briefcase Main Body (solid primary-600 blue) */}
                <rect x="80" y="160" width="352" height="256" rx="48" fill="#0b7ae8" />
                {/* Inner Lightning Bolt (solid white) */}
                <path d="M280 200L190 310H250L220 400L320 280H262L280 200Z" fill="#FFFFFF" />
              </svg>
            </div>
            <div className="flex flex-col justify-center gap-0.5">
              <h1 className="text-sm font-extrabold text-slate-800 tracking-wide uppercase leading-none">Auto J*b Applier</h1>
              <span className="text-[10px] text-primary-600 font-semibold uppercase tracking-wider leading-none">Automation Hub</span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-1">
            {navItems.map((item) => (
              <button
                key={item.name}
                onClick={() => setCurrentPage(item.name as PageName)}
                className={`w-full px-4 py-3 rounded-lg text-xs font-semibold flex items-center gap-3.5 transition-all cursor-pointer ${
                  currentPage === item.name
                    ? 'bg-primary-600 text-white shadow-md shadow-primary-500/10'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
                }`}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </nav>
        </div>

        <div>
          {/* End Application Button */}
          <div className="px-4 pb-3">
            <button
              onClick={handleEndApplication}
              className="w-full px-4 py-2.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 bg-rose-50 text-rose-600 border border-rose-200 hover:bg-rose-600 hover:text-white transition-all cursor-pointer shadow-sm shadow-rose-500/5"
            >
              <Power className="w-4 h-4" />
              End Application
            </button>
          </div>

          {/* WebSocket Connection Status Footer */}
          <div className="p-4 border-t border-slate-200 flex items-center justify-between text-[10px]">
            <span className="text-slate-500">Local Server:</span>
            <span className={`flex items-center gap-1.5 font-bold ${isConnected ? 'text-emerald-600' : 'text-rose-600'}`}>
              <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`}></span>
              {isConnected ? 'CONNECTED' : 'DISCONNECTED'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content Pane */}
      <main className="flex-1 overflow-y-auto p-8 relative flex flex-col justify-start">
        
        {/* Active Bot Status Control Bar */}
        <BotStatusBar />

        {/* Page Render */}
        <div className="flex-1">
          {renderPage()}
        </div>

        {/* High Priority Blocking Popup Modal Overlay */}
        <PopupModal />
      </main>

    </div>
  );
};
