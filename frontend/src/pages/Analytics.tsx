import React from 'react';
import { useBot } from '../hooks/useBot';
import { ResponsiveSankey } from '@nivo/sankey';
import { Network } from 'lucide-react';

export const Analytics: React.FC = () => {
  const { stats } = useBot();

  // If we found zero jobs, we can't show a meaningful Sankey diagram.
  if (stats.found === 0) {
    return (
      <div className="space-y-6">
        <div className="p-6 glass-panel border-slate-200">
          <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
            <Network className="w-5 h-5 text-primary-600" />
            Job Flow Analytics
          </h3>
          <div className="flex-shrink-0 flex flex-col items-center justify-center text-center text-slate-400 p-10 h-[400px]">
            <Network className="w-16 h-16 text-slate-300 mb-4" />
            <p className="text-sm font-semibold">Not enough data to display flow.</p>
            <p className="text-xs italic mt-1">Start a session to discover jobs and populate the flow diagram.</p>
          </div>
        </div>
      </div>
    );
  }

  // Calculate pending (discovered but not processed)
  const pending = Math.max(0, stats.found - stats.applied - stats.skipped - stats.failed);

  const nodes = [
    { id: 'Discovered', nodeColor: '#3b82f6' }
  ];
  
  const links = [];

  if (stats.applied > 0) {
    nodes.push({ id: 'Applied', nodeColor: '#10b981' }); // Green for Applied
    links.push({ source: 'Discovered', target: 'Applied', value: stats.applied });
  }
  if (stats.skipped > 0) {
    nodes.push({ id: 'Skipped', nodeColor: '#f59e0b' });
    links.push({ source: 'Discovered', target: 'Skipped', value: stats.skipped });
  }
  if (stats.failed > 0) {
    nodes.push({ id: 'Failed', nodeColor: '#ef4444' });
    links.push({ source: 'Discovered', target: 'Failed', value: stats.failed });
  }
  if (pending > 0) {
    nodes.push({ id: 'Pending', nodeColor: '#8b5cf6' });
    links.push({ source: 'Discovered', target: 'Pending', value: pending });
  }

  const data = { nodes, links };

  return (
    <div className="space-y-6 h-full flex flex-col">
      <div className="p-6 glass-panel border-slate-200 flex-1 flex flex-col min-h-[500px]">
        <h3 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2 flex-shrink-0">
          <Network className="w-5 h-5 text-primary-600" />
          Job Discovery Flow
        </h3>
        
        <div className="flex-1 bg-white rounded-xl shadow-inner border border-slate-100 p-4 relative">
          {links.length > 0 ? (
            <ResponsiveSankey
              data={data}
              margin={{ top: 40, right: 180, bottom: 40, left: 180 }}
              align="justify"
              colors={(node: any) => node.nodeColor || '#000'}
              label={(node: any) => `${node.id}: ${node.value}`}
              nodeOpacity={0.85}
              nodeHoverOthersOpacity={0.1}
              nodeThickness={24}
              nodeSpacing={24}
              nodeBorderWidth={0}
              nodeBorderColor={{ from: 'color', modifiers: [['darker', 0.8]] }}
              nodeBorderRadius={3}
              linkOpacity={0.5}
              linkHoverOthersOpacity={0.1}
              linkContract={3}
              enableLinkGradient={true}
              labelPosition="outside"
              labelOrientation="horizontal"
              labelPadding={16}
              labelTextColor={{ from: 'color', modifiers: [['darker', 1]] }}
              theme={{
                labels: {
                  text: {
                    fontSize: 14,
                    fontWeight: 700,
                    fontFamily: 'Inter, sans-serif'
                  }
                },
                tooltip: {
                  container: {
                    background: '#fff',
                    color: '#333',
                    fontSize: 13,
                    borderRadius: 8,
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)'
                  }
                }
              }}
            />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
              <Network className="w-12 h-12 text-slate-300 mb-2" />
              <p className="text-sm font-semibold">Jobs discovered but no flow data.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
