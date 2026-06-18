import React, { useEffect, useState } from 'react';
import api from '../lib/api';
import { Settings as SettingsIcon, Check, ShieldAlert } from 'lucide-react';

export const Settings: React.FC = () => {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);

  const fetchSettings = async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/api/settings');
      setSettings(res.data);
    } catch (err) {
      console.error('Failed to load settings:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleUpdate = async (key: string, value: string) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    try {
      await api.put(`/api/settings/${key}`, { value });
    } catch (err) {
      console.error(`Failed to update setting ${key}:`, err);
    }
  };

  const handleSaveAll = () => {
    alert('Settings saved and applied in real-time.');
  };

  if (isLoading && Object.keys(settings).length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-slate-500 text-xs italic">
        Loading settings...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto pb-12">
      <div>
        <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-primary-600" />
          Bot Parameters Settings
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Adjust typing speeds, safety boundaries, and anti-detection parameters.
        </p>
      </div>

      <div className="glass-panel border-slate-200 p-6 space-y-6 bg-white">
        
        {/* Anti-detect Warning */}
        <div className="p-4 bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-xl flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 flex-shrink-0 text-amber-600" />
          <div>
            <span className="font-bold block mb-0.5">Human Behavior Enforcement</span>
            To prevent account restriction flags from LinkedIn, keep typing action delays above 800ms and respect recommended session limits (max 15).
          </div>
        </div>

        <div className="space-y-6 divide-y divide-slate-100">
          
          {/* Headless Mode */}
          <div className="flex items-center justify-between py-4">
            <div>
              <h4 className="text-sm font-bold text-slate-800">Invisible Mode (Headless)</h4>
              <p className="text-xs text-slate-500 mt-0.5">Runs Chrome hidden in the background without opening a visible UI.</p>
            </div>
            <select
              value={settings.headless_mode || 'false'}
              onChange={(e) => handleUpdate('headless_mode', e.target.value)}
              className="glass-input text-xs bg-white w-36 text-slate-800"
            >
              <option value="true">Enabled (Hidden)</option>
              <option value="false">Disabled (Visible)</option>
            </select>
          </div>

          {/* Submission Mode */}
          <div className="flex items-center justify-between py-4">
            <div>
              <h4 className="text-sm font-bold text-slate-800">Application Review</h4>
              <p className="text-xs text-slate-500 mt-0.5">Shows a pre-filled submission preview before sending the form.</p>
            </div>
            <select
              value={settings.bot_mode || 'review'}
              onChange={(e) => handleUpdate('bot_mode', e.target.value)}
              className="glass-input text-xs bg-white w-36 text-slate-800"
            >
              <option value="review">Review (Prompt)</option>
              <option value="auto">Submit directly</option>
            </select>
          </div>

          {/* Popup Mode */}
          <div className="flex items-center justify-between py-4">
            <div>
              <h4 className="text-sm font-bold text-slate-800">Popup Display Mode</h4>
              <p className="text-xs text-slate-500 mt-0.5">Choose if popups show in the Web Dashboard or in local Python Tkinter screens.</p>
            </div>
            <select
              value={settings.popup_mode || 'web'}
              onChange={(e) => handleUpdate('popup_mode', e.target.value)}
              className="glass-input text-xs bg-white w-36 text-slate-800"
            >
              <option value="web">Web Only</option>
              <option value="desktop">Desktop (Python)</option>
            </select>
          </div>

          {/* Limit per session */}
          <div className="flex items-center justify-between py-4">
            <div>
              <h4 className="text-sm font-bold text-slate-800">Session Limit</h4>
              <p className="text-xs text-slate-500 mt-0.5">Maximum number of completed applications per execution run.</p>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="number"
                min="1"
                max="50"
                value={settings.session_limit || '10'}
                onChange={(e) => handleUpdate('session_limit', e.target.value)}
                className="glass-input text-xs w-20 text-center"
              />
              <span className="text-xs text-slate-500 font-semibold">jobs</span>
            </div>
          </div>

          {/* Action Delays */}
          <div className="flex items-center justify-between py-4">
            <div>
              <h4 className="text-sm font-bold text-slate-800">Minimum Keypress Delay</h4>
              <p className="text-xs text-slate-500 mt-0.5">Minimum delay between keystrokes and clicks in forms.</p>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="number"
                step="100"
                min="200"
                max="5000"
                value={settings.min_action_delay_ms || '800'}
                onChange={(e) => handleUpdate('min_action_delay_ms', e.target.value)}
                className="glass-input text-xs w-20 text-center"
              />
              <span className="text-xs text-slate-500 font-semibold">ms</span>
            </div>
          </div>

          <div className="flex items-center justify-between py-4">
            <div>
              <h4 className="text-sm font-bold text-slate-800">Maximum Keypress Delay</h4>
              <p className="text-xs text-slate-500 mt-0.5">Maximum delay to simulate natural variation in human timing.</p>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="number"
                step="100"
                min="500"
                max="10000"
                value={settings.max_action_delay_ms || '3000'}
                onChange={(e) => handleUpdate('max_action_delay_ms', e.target.value)}
                className="glass-input text-xs w-20 text-center"
              />
              <span className="text-xs text-slate-500 font-semibold">ms</span>
            </div>
          </div>

          {/* Auto submit delay */}
          <div className="flex items-center justify-between py-4">
            <div>
              <h4 className="text-sm font-bold text-slate-800">Pre-Submit Pause</h4>
              <p className="text-xs text-slate-500 mt-0.5">How long the bot pauses on the final preview page before clicking submit.</p>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="number"
                step="500"
                min="500"
                max="10000"
                value={settings.auto_submit_delay_ms || '2000'}
                onChange={(e) => handleUpdate('auto_submit_delay_ms', e.target.value)}
                className="glass-input text-xs w-20 text-center"
              />
              <span className="text-xs text-slate-500 font-semibold">ms</span>
            </div>
          </div>

          {/* Fuzzy Threshold */}
          <div className="flex items-center justify-between py-4">
            <div>
              <h4 className="text-sm font-bold text-slate-800">Fuzzy Match Sensitivity</h4>
              <p className="text-xs text-slate-500 mt-0.5">Similarity threshold score for auto-resolving saved questions (0.0 to 1.0).</p>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="number"
                step="0.05"
                min="0.5"
                max="1.0"
                value={settings.fuzzy_match_threshold || '1.0'}
                onChange={(e) => handleUpdate('fuzzy_match_threshold', e.target.value)}
                className="glass-input text-xs w-20 text-center"
              />
              <span className="text-xs text-slate-500 font-semibold">score</span>
            </div>
          </div>

          {/* Log Level */}
          <div className="flex items-center justify-between py-4">
            <div>
              <h4 className="text-sm font-bold text-slate-800">Logger Level</h4>
              <p className="text-xs text-slate-500 mt-0.5">Verbosity level of execution logs stored in SQLite database.</p>
            </div>
            <select
              value={settings.log_level || 'info'}
              onChange={(e) => handleUpdate('log_level', e.target.value)}
              className="glass-input text-xs bg-white w-36 text-slate-800"
            >
              <option value="info">Info (Default)</option>
              <option value="debug">Debug (Verbose)</option>
            </select>
          </div>

        </div>

        <button
          onClick={handleSaveAll}
          className="w-full glass-btn-primary py-2.5 font-semibold mt-6"
        >
          <Check className="w-4 h-4" />
          Save Settings
        </button>

      </div>
    </div>
  );
};
