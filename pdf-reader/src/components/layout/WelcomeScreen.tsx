import React, { useEffect } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { fileService } from '../../services/fileService';
import { FileUp, Clock, FileText, FileCode, Trash2, FolderOpen, ArrowRight } from 'lucide-react';
import { RecentFile } from '../../types';

export const WelcomeScreen: React.FC = () => {
  const { recentFiles, loadRecentFiles, removeRecentFile, openDocument } = useAppStore();

  useEffect(() => {
    loadRecentFiles();
  }, [loadRecentFiles]);

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

  const handleOpenRecent = async (recent: RecentFile) => {
    try {
      const loaded = await fileService.readFileFromPath(recent.path);
      await openDocument({
        ...loaded,
        initialPage: recent.lastPage,
      });
    } catch (err) {
      console.error('Failed to open recent file:', err);
      alert(`Could not open recent file: ${recent.path}`);
    }
  };

  const formatRelativeTime = (timestamp: number) => {
    const diffSec = Math.floor((Date.now() - timestamp) / 1000);
    if (diffSec < 60) return 'Just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    return `${Math.floor(diffSec / 86400)}d ago`;
  };

  return (
    <div className="flex-1 w-full h-full bg-zinc-950 flex flex-col items-center justify-center p-6 overflow-y-auto select-none">
      <div className="max-w-2xl w-full flex flex-col items-center gap-8 my-auto">
        {/* Header Title */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 mb-2 shadow-lg shadow-indigo-500/10">
            <FileText className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            AeroPDF & Markdown Reader
          </h1>
          <p className="text-sm text-zinc-400 max-w-md">
            Fast, keyboard-friendly PDF and Markdown document reader for Linux desktop built with Tauri.
          </p>
        </div>

        {/* Dropzone & Open Button */}
        <div
          onClick={handleOpenFile}
          className="group w-full max-w-lg border-2 border-dashed border-zinc-800 hover:border-indigo-500/70 bg-zinc-900/40 hover:bg-zinc-900/80 rounded-2xl p-8 flex flex-col items-center justify-center gap-4 cursor-pointer transition-all duration-200"
        >
          <div className="w-12 h-12 rounded-full bg-zinc-800 group-hover:bg-indigo-600/20 group-hover:text-indigo-400 text-zinc-400 flex items-center justify-center transition-colors">
            <FileUp className="w-6 h-6" />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-zinc-200 group-hover:text-white">
              Drop a PDF or Markdown file here or <span className="text-indigo-400 underline decoration-indigo-500/40 underline-offset-4">browse files</span>
            </p>
            <p className="text-xs text-zinc-500 mt-1 font-mono">
              Supports PDF (.pdf) and Markdown (.md, .markdown) documents
            </p>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all">
            <FolderOpen className="w-3.5 h-3.5" />
            <span>Open Document</span>
          </button>
        </div>

        {/* Recent Files Section */}
        {recentFiles.length > 0 && (
          <div className="w-full max-w-lg">
            <div className="flex items-center justify-between mb-3 px-1">
              <div className="flex items-center gap-2 text-xs font-medium text-zinc-400">
                <Clock className="w-3.5 h-3.5 text-zinc-500" />
                <span>Recent Documents</span>
              </div>
              <span className="text-[11px] text-zinc-500 font-mono">
                Persisted in SQLite
              </span>
            </div>

            <div className="flex flex-col gap-1.5 max-h-60 overflow-y-auto pr-1">
              {recentFiles.map((file) => {
                const isMd = fileService.isMarkdownFile(file.path || file.title);
                return (
                  <div
                    key={file.path}
                    onClick={() => handleOpenRecent(file)}
                    className="group flex items-center justify-between p-2.5 rounded-lg bg-zinc-900/60 hover:bg-zinc-850 border border-zinc-800/80 hover:border-zinc-700 cursor-pointer transition-all"
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      {isMd ? (
                        <FileCode className="w-4 h-4 text-zinc-500 group-hover:text-emerald-400 transition-colors flex-shrink-0" />
                      ) : (
                        <FileText className="w-4 h-4 text-zinc-500 group-hover:text-indigo-400 transition-colors flex-shrink-0" />
                      )}
                      <div className="flex flex-col min-w-0">
                        <span className="text-xs font-medium text-zinc-200 truncate group-hover:text-white">
                          {file.title}
                        </span>
                        <span className="text-[11px] text-zinc-500 truncate font-mono">
                          {file.path}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                      <span className="text-[10px] text-zinc-500 font-mono bg-zinc-800 px-1.5 py-0.5 rounded">
                        {isMd ? 'MD' : `p. ${file.lastPage}/${file.totalPages}`}
                      </span>
                      <span className="text-[10px] text-zinc-500">
                        {formatRelativeTime(file.lastOpened)}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          removeRecentFile(file.path);
                        }}
                        title="Remove from recents"
                        className="p-1 rounded text-zinc-500 hover:text-red-400 hover:bg-zinc-800 opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                      <ArrowRight className="w-3.5 h-3.5 text-zinc-600 group-hover:text-zinc-300 opacity-0 group-hover:opacity-100 transition-all" />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Quick Hint */}
        <div className="text-[11px] text-zinc-500 flex items-center gap-2">
          <span>Shortcuts:</span>
          <kbd className="px-1.5 py-0.5 rounded bg-zinc-850 border border-zinc-800 text-zinc-300 font-mono">Ctrl+O</kbd>
          <span>to open,</span>
          <kbd className="px-1.5 py-0.5 rounded bg-zinc-850 border border-zinc-800 text-zinc-300 font-mono">Ctrl+W</kbd>
          <span>to close tab,</span>
          <kbd className="px-1.5 py-0.5 rounded bg-zinc-850 border border-zinc-800 text-zinc-300 font-mono">?</kbd>
          <span>for shortcuts</span>
        </div>
      </div>
    </div>
  );
};
