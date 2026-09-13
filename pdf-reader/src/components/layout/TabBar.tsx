import React from 'react';
import { useAppStore } from '../../store/useAppStore';
import { fileService } from '../../services/fileService';
import { FileText, FileCode, Plus, X } from 'lucide-react';

export const TabBar: React.FC = () => {
  const { tabs, activeTabId, setActiveTab, closeTab, openDocument } = useAppStore();

  const handleOpenFile = async () => {
    try {
      const file = await fileService.openFileDialog();
      if (file) {
        await openDocument(file);
      }
    } catch (err) {
      console.error('Failed to open file:', err);
    }
  };

  const handleTabMouseDown = (e: React.MouseEvent, tabId: string) => {
    // Middle click closes the tab
    if (e.button === 1) {
      e.preventDefault();
      closeTab(tabId);
    }
  };

  return (
    <div className="flex items-center h-10 bg-zinc-950 px-2 select-none border-b border-zinc-800/80 overflow-x-auto overflow-y-hidden">
      <div className="flex items-center gap-1.5 flex-1 min-w-0">
        {tabs.map((tab) => {
          const isActive = tab.id === activeTabId;
          const isMarkdown = tab.fileType === 'markdown';
          return (
            <div
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              onMouseDown={(e) => handleTabMouseDown(e, tab.id)}
              title={tab.filePath || tab.fileName}
              className={`group flex items-center gap-2 h-8 px-3 rounded-t-md text-xs font-medium cursor-pointer transition-all border-t border-x ${
                isActive
                  ? 'bg-zinc-850 text-zinc-100 border-zinc-700 shadow-sm'
                  : 'bg-zinc-900/50 text-zinc-400 border-transparent hover:bg-zinc-900 hover:text-zinc-200'
              }`}
              style={{ maxWidth: '240px' }}
            >
              {isMarkdown ? (
                <FileCode
                  className={`w-3.5 h-3.5 flex-shrink-0 ${
                    isActive ? 'text-emerald-400' : 'text-zinc-500'
                  }`}
                />
              ) : (
                <FileText
                  className={`w-3.5 h-3.5 flex-shrink-0 ${
                    isActive ? 'text-indigo-400' : 'text-zinc-500'
                  }`}
                />
              )}
              <span className="truncate flex-1">{tab.fileName}</span>
              <span className="text-[10px] text-zinc-500 group-hover:text-zinc-400 font-mono">
                {isMarkdown ? 'MD' : `${tab.currentPage}/${tab.totalPages}`}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  closeTab(tab.id);
                }}
                title="Close Tab (Ctrl+W)"
                className="w-4 h-4 rounded flex items-center justify-center text-zinc-500 hover:text-zinc-100 hover:bg-zinc-700/60 transition-colors"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          );
        })}

        {/* New Tab Button */}
        <button
          onClick={handleOpenFile}
          title="Open Document (Ctrl+O)"
          className="flex items-center justify-center w-7 h-7 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors ml-1"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
