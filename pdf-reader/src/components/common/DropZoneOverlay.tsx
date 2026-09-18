import React from 'react';
import { FileUp } from 'lucide-react';

interface DropZoneOverlayProps {
  isDragging: boolean;
}

export const DropZoneOverlay: React.FC<DropZoneOverlayProps> = ({ isDragging }) => {
  if (!isDragging) return null;

  return (
    <div className="fixed inset-0 z-50 pointer-events-none flex items-center justify-center bg-indigo-950/60 backdrop-blur-sm border-4 border-dashed border-indigo-500/80 m-3 rounded-2xl animate-in fade-in duration-150">
      <div className="flex flex-col items-center gap-3 p-8 bg-zinc-900/90 rounded-2xl shadow-2xl border border-indigo-500/30 text-center">
        <div className="w-16 h-16 rounded-full bg-indigo-600/20 text-indigo-400 flex items-center justify-center">
          <FileUp className="w-8 h-8 animate-bounce" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-white">Drop Document</h3>
          <p className="text-xs text-zinc-400 mt-0.5">Release to open PDF or Markdown file in a new tab</p>
        </div>
      </div>
    </div>
  );
};
