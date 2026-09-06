import React, { useEffect, useState } from 'react';
import { useAppStore } from './store/useAppStore';
import { fileService } from './services/fileService';
import { TabBar } from './components/layout/TabBar';
import { Toolbar } from './components/layout/Toolbar';
import { WelcomeScreen } from './components/layout/WelcomeScreen';
import { PDFViewer } from './components/viewer/PDFViewer';
import { MarkdownViewer } from './components/viewer/MarkdownViewer';
import { KeyboardShortcutsModal } from './components/common/KeyboardShortcutsModal';
import { DropZoneOverlay } from './components/common/DropZoneOverlay';
import { useKeyboardNavigation } from './hooks/useKeyboardNavigation';
import { isTauri } from './db/database';

export const App: React.FC = () => {
  const {
    tabs,
    activeTabId,
    openDocument,
    loadRecentFiles,
    loadSettings,
    isLoading,
    loadingMessage,
  } = useAppStore();

  const [isDragging, setIsDragging] = useState(false);
  const [shortcutsModalOpen, setShortcutsModalOpen] = useState(false);

  // Bind global keyboard shortcuts
  useKeyboardNavigation({
    onToggleShortcutsModal: () => setShortcutsModalOpen((prev) => !prev),
  });

  // Initialization: settings, recent files, and CLI argument check
  useEffect(() => {
    loadSettings();
    loadRecentFiles();

    // Check if a document file path was passed via CLI (e.g. `pdfreader doc.pdf` or `pdfreader doc.md`)
    const checkCli = async () => {
      const args = await fileService.getCliArguments();
      if (args.length > 0) {
        const filePath = args[0];
        try {
          const loaded = await fileService.readFileFromPath(filePath);
          await openDocument(loaded);
        } catch (err) {
          console.error('Failed to open file from CLI arguments:', filePath, err);
        }
      }
    };

    checkCli();
  }, [loadSettings, loadRecentFiles, openDocument]);

  // Setup Tauri v2 drag-and-drop listener if in Tauri
  useEffect(() => {
    if (!isTauri()) return;

    let unlisten: (() => void) | undefined;
    const setupTauriDrop = async () => {
      try {
        const { getCurrentWebviewWindow } = await import('@tauri-apps/api/webviewWindow');
        const webview = getCurrentWebviewWindow();
        unlisten = await webview.onDragDropEvent(async (event) => {
          if (event.payload.type === 'over') {
            setIsDragging(true);
          } else if (event.payload.type === 'leave') {
            setIsDragging(false);
          } else if (event.payload.type === 'drop') {
            setIsDragging(false);
            const paths = event.payload.paths;
            if (paths && paths.length > 0) {
              const filePath = paths[0];
              if (fileService.isSupportedFile(filePath)) {
                try {
                  const loaded = await fileService.readFileFromPath(filePath);
                  await openDocument(loaded);
                } catch (err) {
                  console.error('Failed to open dropped file:', err);
                }
              }
            }
          }
        });
      } catch (err) {
        console.warn('Tauri onDragDropEvent not available, standard HTML5 drag-and-drop will be used:', err);
      }
    };

    setupTauriDrop();

    return () => {
      if (unlisten) unlisten();
    };
  }, [openDocument]);

  // HTML5 Drag and drop fallback (works in both desktop and web preview)
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    // Only deactivate if leaving the window
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      if (
        file.type === 'application/pdf' ||
        file.type === 'text/markdown' ||
        fileService.isSupportedFile(file.name)
      ) {
        try {
          const loaded = await fileService.readFileFromFileObject(file);
          await openDocument(loaded);
        } catch (err) {
          console.error('Failed to process dropped file:', err);
        }
      } else {
        alert('Please drop a valid PDF or Markdown file.');
      }
    }
  };

  const activeTab = tabs.find((t) => t.id === activeTabId);

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className="flex flex-col h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-100 select-none font-sans"
    >
      {/* Top Tabs Bar */}
      <TabBar />

      {/* Main Toolbar */}
      <Toolbar onOpenShortcutsModal={() => setShortcutsModalOpen(true)} />

      {/* Viewer or Welcome Screen */}
      <div className="flex-1 flex overflow-hidden relative">
        {activeTab ? (
          activeTab.fileType === 'markdown' ? (
            <MarkdownViewer key={activeTab.id} tab={activeTab} />
          ) : (
            <PDFViewer key={activeTab.id} tab={activeTab} />
          )
        ) : (
          <WelcomeScreen />
        )}

        {/* Global Loading Overlay */}
        {isLoading && (
          <div className="absolute inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center z-40">
            <div className="bg-zinc-900 border border-zinc-800 px-5 py-3 rounded-xl shadow-2xl flex items-center gap-3">
              <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs font-medium text-zinc-200">{loadingMessage || 'Loading...'}</span>
            </div>
          </div>
        )}
      </div>

      {/* Modals & Visual Overlays */}
      <KeyboardShortcutsModal
        isOpen={shortcutsModalOpen}
        onClose={() => setShortcutsModalOpen(false)}
      />
      <DropZoneOverlay isDragging={isDragging} />
    </div>
  );
};

export default App;
