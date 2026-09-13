import React, { useState, useEffect } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { fileService } from '../../services/fileService';
import {
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  ZoomIn,
  ZoomOut,
  RotateCw,
  RotateCcw,
  BookOpen,
  FileText,
  AlignJustify,
  Keyboard,
  Eye,
  Columns,
  Code2,
} from 'lucide-react';
import { ZoomMode } from '../../types';

interface ToolbarProps {
  onOpenShortcutsModal: () => void;
}

export const Toolbar: React.FC<ToolbarProps> = ({ onOpenShortcutsModal }) => {
  const {
    tabs,
    activeTabId,
    setCurrentPage,
    setZoomMode,
    zoomIn,
    zoomOut,
    rotateClockwise,
    rotateCounterClockwise,
    setViewMode,
    setMarkdownViewMode,
    openDocument,
  } = useAppStore();

  const activeTab = tabs.find((t) => t.id === activeTabId);
  const [pageInput, setPageInput] = useState<string>('1');

  useEffect(() => {
    if (activeTab) {
      setPageInput(String(activeTab.currentPage));
    }
  }, [activeTab?.currentPage]);

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

  const handlePageSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTab) return;
    const p = parseInt(pageInput, 10);
    if (!isNaN(p)) {
      setCurrentPage(activeTab.id, p);
    }
  };

  const isMarkdown = activeTab?.fileType === 'markdown';

  return (
    <div className="flex items-center justify-between h-11 bg-zinc-900 border-b border-zinc-800 px-3 select-none text-zinc-300">
      {/* Left Section: File Actions & Page Navigation */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleOpenFile}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-zinc-800 hover:bg-zinc-700/80 text-xs font-medium text-zinc-200 transition-colors border border-zinc-700/60 shadow-sm"
          title="Open file (Ctrl+O)"
        >
          <FolderOpen className="w-3.5 h-3.5 text-indigo-400" />
          <span>Open</span>
        </button>

        {activeTab && !isMarkdown && (
          <div className="flex items-center gap-1 ml-2 border-l border-zinc-800 pl-3">
            <button
              onClick={() => setCurrentPage(activeTab.id, activeTab.currentPage - 1)}
              disabled={activeTab.currentPage <= 1}
              className="p-1 rounded hover:bg-zinc-800 disabled:opacity-30 text-zinc-400 hover:text-zinc-100 transition-colors"
              title="Previous Page (Left Arrow, Page Up)"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <form onSubmit={handlePageSubmit} className="flex items-center gap-1">
              <input
                type="text"
                value={pageInput}
                onChange={(e) => setPageInput(e.target.value)}
                onBlur={handlePageSubmit}
                className="w-11 h-6 text-center text-xs font-mono font-medium bg-zinc-950 border border-zinc-750 rounded text-zinc-100 focus:outline-none focus:border-indigo-500 transition-colors"
              />
              <span className="text-xs text-zinc-400 font-mono">/ {activeTab.totalPages}</span>
            </form>

            <button
              onClick={() => setCurrentPage(activeTab.id, activeTab.currentPage + 1)}
              disabled={activeTab.currentPage >= activeTab.totalPages}
              className="p-1 rounded hover:bg-zinc-800 disabled:opacity-30 text-zinc-400 hover:text-zinc-100 transition-colors"
              title="Next Page (Right Arrow, Page Down)"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Center Section: View Mode Selector */}
      {activeTab && (
        isMarkdown ? (
          <div className="flex items-center gap-0.5 bg-zinc-950 p-0.5 rounded-md border border-zinc-800">
            <button
              onClick={() => setMarkdownViewMode(activeTab.id, 'rendered')}
              title="Rendered Markdown Preview (1)"
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors ${
                (activeTab.markdownViewMode || 'rendered') === 'rendered'
                  ? 'bg-zinc-800 text-zinc-100 shadow-sm font-medium'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Eye className="w-3.5 h-3.5" />
              <span>Preview</span>
            </button>

            <button
              onClick={() => setMarkdownViewMode(activeTab.id, 'split')}
              title="Side-by-side Split View (2)"
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors ${
                activeTab.markdownViewMode === 'split'
                  ? 'bg-zinc-800 text-zinc-100 shadow-sm font-medium'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Columns className="w-3.5 h-3.5" />
              <span>Split</span>
            </button>

            <button
              onClick={() => setMarkdownViewMode(activeTab.id, 'raw')}
              title="Raw Markdown Source (3)"
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors ${
                activeTab.markdownViewMode === 'raw'
                  ? 'bg-zinc-800 text-zinc-100 shadow-sm font-medium'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Code2 className="w-3.5 h-3.5" />
              <span>Source</span>
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-0.5 bg-zinc-950 p-0.5 rounded-md border border-zinc-800">
            <button
              onClick={() => setViewMode(activeTab.id, 'continuous')}
              title="Continuous Vertical Scroll (1)"
              className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs transition-colors ${
                activeTab.viewMode === 'continuous'
                  ? 'bg-zinc-800 text-zinc-100 shadow-sm font-medium'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <AlignJustify className="w-3.5 h-3.5" />
              <span>Continuous</span>
            </button>

            <button
              onClick={() => setViewMode(activeTab.id, 'single')}
              title="Single Page View (2)"
              className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs transition-colors ${
                activeTab.viewMode === 'single'
                  ? 'bg-zinc-800 text-zinc-100 shadow-sm font-medium'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Single</span>
            </button>

            <button
              onClick={() => setViewMode(activeTab.id, 'two-page')}
              title="Two-Page Book Spread (3)"
              className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs transition-colors ${
                activeTab.viewMode === 'two-page'
                  ? 'bg-zinc-800 text-zinc-100 shadow-sm font-medium'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>Two-Page</span>
            </button>
          </div>
        )
      )}

      {/* Right Section: Zoom & Rotation Controls */}
      {activeTab ? (
        <div className="flex items-center gap-1.5">
          {/* Zoom controls */}
          <div className="flex items-center gap-1 bg-zinc-950 px-1 py-0.5 rounded-md border border-zinc-800">
            <button
              onClick={() => zoomOut(activeTab.id)}
              title="Zoom Out (Ctrl+-)"
              className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 transition-colors"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>

            <select
              value={activeTab.zoomMode === 'custom' ? `${Math.round(activeTab.zoomLevel * 100)}%` : activeTab.zoomMode}
              onChange={(e) => {
                const val = e.target.value;
                if (val === 'fit-width' || val === 'fit-page') {
                  setZoomMode(activeTab.id, val as ZoomMode);
                } else {
                  const level = parseFloat(val) / 100;
                  setZoomMode(activeTab.id, 'custom', level);
                }
              }}
              className="bg-transparent text-xs font-mono font-medium text-zinc-200 border-none outline-none cursor-pointer px-1 text-center"
            >
              {!isMarkdown && (
                <>
                  <option value="fit-width" className="bg-zinc-900 text-zinc-100">Fit Width</option>
                  <option value="fit-page" className="bg-zinc-900 text-zinc-100">Fit Page</option>
                </>
              )}
              <option value="50%" className="bg-zinc-900 text-zinc-100">50%</option>
              <option value="75%" className="bg-zinc-900 text-zinc-100">75%</option>
              <option value="90%" className="bg-zinc-900 text-zinc-100">90%</option>
              <option value="100%" className="bg-zinc-900 text-zinc-100">100%</option>
              <option value="110%" className="bg-zinc-900 text-zinc-100">110%</option>
              <option value="125%" className="bg-zinc-900 text-zinc-100">125%</option>
              <option value="150%" className="bg-zinc-900 text-zinc-100">150%</option>
              <option value="200%" className="bg-zinc-900 text-zinc-100">200%</option>
              <option value="300%" className="bg-zinc-900 text-zinc-100">300%</option>
            </select>

            <button
              onClick={() => zoomIn(activeTab.id)}
              title="Zoom In (Ctrl++)"
              className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 transition-colors"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Rotation controls (PDF only) */}
          {!isMarkdown && (
            <div className="flex items-center gap-0.5 border-l border-zinc-800 pl-1.5">
              <button
                onClick={() => rotateCounterClockwise(activeTab.id)}
                title="Rotate Counter-Clockwise"
                className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>

              <button
                onClick={() => rotateClockwise(activeTab.id)}
                title="Rotate Clockwise"
                className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 transition-colors"
              >
                <RotateCw className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Shortcuts Help */}
          <button
            onClick={onOpenShortcutsModal}
            title="Keyboard Shortcuts (?)"
            className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 transition-colors ml-1"
          >
            <Keyboard className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-1">
          <button
            onClick={onOpenShortcutsModal}
            title="Keyboard Shortcuts (?)"
            className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 transition-colors"
          >
            <Keyboard className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};
