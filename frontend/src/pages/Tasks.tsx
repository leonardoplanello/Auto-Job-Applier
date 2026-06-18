import React, { useEffect, useState } from 'react';
import api from '../lib/api';
import { 
  ListOrdered, GripVertical, Plus, Trash2, Search, LayoutList, Layers
} from 'lucide-react';
import { useBot } from '../hooks/useBot';

interface SearchCriteria {
  id: number;
  name: string;
}

export interface BotTask {
  id?: string; // Unique UI id for dragging
  type: 'process_queue' | 'search';
  target?: 'all' | 'prioritized';
  search_id?: number;
}

export const Tasks: React.FC = () => {
  const { status } = useBot();
  const [tasks, setTasks] = useState<BotTask[]>([]);
  const [criterias, setCriterias] = useState<SearchCriteria[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showAddMenu, setShowAddMenu] = useState(false);

  // Drag state
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const critRes = await api.get('/api/search');
        setCriterias(critRes.data);

        const setRes = await api.get('/api/settings');
        if (setRes.data && setRes.data.bot_tasks_sequence) {
          const loaded = JSON.parse(setRes.data.bot_tasks_sequence);
          // ensure UI ids
          const withIds = loaded.map((t: any) => ({ ...t, id: t.id || Math.random().toString(36).substr(2, 9) }));
          setTasks(withIds);
        } else {
          // Default setup
          setTasks([
            { id: Math.random().toString(36).substr(2, 9), type: 'process_queue', target: 'all' }
          ]);
        }
      } catch (err) {
        console.error('Failed to load tasks data:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleSave = async (tasksToSave = tasks) => {
    try {
      const payload = tasksToSave.map(({ id, ...rest }) => rest);
      await api.put('/api/settings/bot_tasks_sequence', { value: JSON.stringify(payload) });
    } catch (err) {
      console.error('Failed to save tasks sequence:', err);
      alert('Failed to save sequence.');
    }
  };

  const addTask = (task: Omit<BotTask, 'id'>) => {
    const newTask = { ...task, id: Math.random().toString(36).substr(2, 9) };
    const updated = [...tasks, newTask];
    setTasks(updated);
    setShowAddMenu(false);
    handleSave(updated);
  };

  const removeTask = (index: number) => {
    const updated = tasks.filter((_, i) => i !== index);
    setTasks(updated);
    handleSave(updated);
  };

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggingIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent, targetIndex: number) => {
    e.preventDefault();
    if (draggingIndex === null || draggingIndex === targetIndex) {
      setDraggingIndex(null);
      return;
    }
    const newList = [...tasks];
    const [draggedItem] = newList.splice(draggingIndex, 1);
    newList.splice(targetIndex, 0, draggedItem);
    
    setTasks(newList);
    setDraggingIndex(null);
    handleSave(newList);
  };

  const getTaskLabel = (task: BotTask) => {
    if (task.type === 'process_queue') {
      return task.target === 'prioritized' ? 'Process Queue (Prioritized Only)' : 'Process Queue (All Jobs)';
    }
    if (task.type === 'search') {
      const crit = criterias.find(c => c.id === task.search_id);
      return crit ? `Search: ${crit.name}` : `Search (ID: ${task.search_id})`;
    }
    return 'Unknown Task';
  };

  const getTaskIcon = (task: BotTask) => {
    if (task.type === 'process_queue') return <LayoutList className="w-5 h-5 text-indigo-500" />;
    if (task.type === 'search') return <Search className="w-5 h-5 text-emerald-500" />;
    return <Layers className="w-5 h-5 text-slate-500" />;
  };

  const isBotActive = !['idle', 'stopped', 'finished'].includes(status);

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-3">
            <ListOrdered className="w-7 h-7 text-primary-600" />
            Tasks Sequence
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Build the exact sequence of actions the bot will perform when started. Changes are saved automatically.
          </p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        {isLoading ? (
          <div className="text-center py-10 text-slate-400 text-sm font-semibold animate-pulse">Loading tasks...</div>
        ) : (
          <div className="space-y-4">
            
            <div className="flex flex-col space-y-2">
              {tasks.length === 0 ? (
                <div className="text-center py-12 bg-slate-50 rounded-lg border-2 border-dashed border-slate-200">
                  <Layers className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                  <p className="text-sm text-slate-500 font-medium">No tasks in sequence.</p>
                  <p className="text-xs text-slate-400 mt-1">Add a task below to get started.</p>
                </div>
              ) : (
                tasks.map((task, index) => (
                  <div
                    key={task.id}
                    draggable={!isBotActive}
                    onDragStart={(e) => handleDragStart(e, index)}
                    onDragOver={handleDragOver}
                    onDrop={(e) => handleDrop(e, index)}
                    className={`flex items-center p-3 sm:p-4 rounded-lg border ${
                      draggingIndex === index 
                        ? 'opacity-50 border-primary-400 bg-primary-50' 
                        : 'border-slate-200 bg-white hover:border-slate-300 shadow-sm'
                    } transition-all`}
                  >
                    <div className="flex items-center flex-1 gap-4">
                      <div className={`cursor-grab active:cursor-grabbing p-1 -ml-1 text-slate-300 hover:text-slate-500 rounded transition-colors ${isBotActive ? 'opacity-50 cursor-not-allowed pointer-events-none' : ''}`}>
                        <GripVertical className="w-5 h-5" />
                      </div>
                      
                      <div className="flex items-center justify-center w-10 h-10 rounded-full bg-slate-50 border border-slate-100 flex-shrink-0">
                        <span className="text-xs font-bold text-slate-400">{index + 1}</span>
                      </div>
                      
                      <div className="flex items-center gap-3">
                        {getTaskIcon(task)}
                        <span className="font-semibold text-slate-700">{getTaskLabel(task)}</span>
                      </div>
                    </div>
                    
                    <button
                      onClick={() => removeTask(index)}
                      disabled={isBotActive}
                      className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors disabled:opacity-50"
                      title="Remove task"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))
              )}
            </div>

            <div className="pt-4 relative">
              {showAddMenu ? (
                <div className="absolute z-10 top-full left-0 mt-2 w-72 bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden">
                  <div className="p-3 border-b border-slate-100 bg-slate-50">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Queue Operations</span>
                  </div>
                  <button onClick={() => addTask({ type: 'process_queue', target: 'all' })} className="w-full text-left px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 flex items-center gap-3 transition-colors border-b border-slate-50">
                    <LayoutList className="w-4 h-4" /> Process Queue (All)
                  </button>
                  <button onClick={() => addTask({ type: 'process_queue', target: 'prioritized' })} className="w-full text-left px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 flex items-center gap-3 transition-colors border-b border-slate-50">
                    <LayoutList className="w-4 h-4" /> Process Queue (Prioritized Only)
                  </button>
                  
                  <div className="p-3 border-b border-slate-100 bg-slate-50">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Run Search</span>
                  </div>
                  <div className="max-h-48 overflow-y-auto">
                    {criterias.length === 0 ? (
                      <div className="px-4 py-3 text-xs text-slate-400 italic">No search criteria found. Create one first.</div>
                    ) : (
                      criterias.map(c => (
                        <button key={c.id} onClick={() => addTask({ type: 'search', search_id: c.id })} className="w-full text-left px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-emerald-50 hover:text-emerald-700 flex items-center gap-3 transition-colors">
                          <Search className="w-4 h-4" /> {c.name}
                        </button>
                      ))
                    )}
                  </div>
                  
                  <div className="p-2 border-t border-slate-100 bg-slate-50 flex justify-end">
                    <button onClick={() => setShowAddMenu(false)} className="text-xs font-bold text-slate-500 hover:text-slate-800 px-3 py-1.5 rounded transition-colors">Cancel</button>
                  </div>
                </div>
              ) : null}
              
              <button
                onClick={() => setShowAddMenu(!showAddMenu)}
                disabled={isBotActive}
                className="w-full py-4 border-2 border-dashed border-slate-200 rounded-xl text-slate-500 font-semibold hover:border-primary-400 hover:text-primary-600 hover:bg-primary-50 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                <Plus className="w-5 h-5" />
                Add Task
              </button>
            </div>

          </div>
        )}
      </div>

    </div>
  );
};
