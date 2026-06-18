import React, { type ReactNode } from 'react';

interface StatCardProps {
  title: string;
  value: number | string;
  icon: ReactNode;
  colorClass?: string;
  onClick?: () => void;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon,
  colorClass = 'text-primary-400 bg-primary-500/10 border-primary-500/20',
  onClick
}) => {
  return (
    <div 
      className={`flex items-center justify-between p-5 glass-panel border-slate-800/60 transition-all duration-200 ${onClick ? 'cursor-pointer hover:shadow-md hover:border-primary-400/50' : 'hover:border-slate-700/60'}`}
      onClick={onClick}
    >
      <div>
        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-800 mb-1.5">{title}</p>
        <h4 className="text-3xl font-black text-slate-800 tracking-tight">{value}</h4>
      </div>
      <div className={`p-3 rounded-xl border ${colorClass}`}>{icon}</div>
    </div>
  );
};
