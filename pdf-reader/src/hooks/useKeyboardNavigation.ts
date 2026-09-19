import { useEffect } from 'react';
import { useAppStore } from '../store/useAppStore';
import { fileService } from '../services/fileService';

interface KeyboardNavigationOptions {
  onToggleShortcutsModal: () => void;
}

export const useKeyboardNavigation = ({ onToggleShortcutsModal }: KeyboardNavigationOptions) => {
  const {
    tabs,
    activeTabId,
    setActiveTab,
    closeTab,
    setCurrentPage,
    zoomIn,
    zoomOut,
    resetZoom,
    setZoomMode,
    rotateClockwise,
    rotateCounterClockwise,
    setViewMode,
    setMarkdownViewMode,
    openDocument,
  } = useAppStore();

  useEffect(() => {
    const handleKeyDown = async (e: KeyboardEvent) => {
      // Don't intercept if user is typing inside an input or textarea
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
        if (e.key === 'Escape') {
          target.blur();
        }
        return;
      }

      const activeTab = tabs.find((t) => t.id === activeTabId);
      const isCtrlOrMeta = e.ctrlKey || e.metaKey;

      // Ctrl+O: Open file
      if (isCtrlOrMeta && e.key.toLowerCase() === 'o') {
        e.preventDefault();
        try {
          const file = await fileService.openFileDialog();
          if (file) await openDocument(file);
        } catch (err) {
          console.error(err);
        }
        return;
      }

      // Ctrl+W: Close tab
      if (isCtrlOrMeta && e.key.toLowerCase() === 'w') {
        e.preventDefault();
        if (activeTabId) {
          closeTab(activeTabId);
        }
        return;
      }

      // Ctrl+Tab & Ctrl+Shift+Tab: Switch tabs
      if (isCtrlOrMeta && e.key === 'Tab') {
        e.preventDefault();
        if (tabs.length > 1 && activeTabId) {
          const currentIndex = tabs.findIndex((t) => t.id === activeTabId);
          if (e.shiftKey) {
            // Previous tab
            const prevIndex = (currentIndex - 1 + tabs.length) % tabs.length;
            setActiveTab(tabs[prevIndex].id);
          } else {
            // Next tab
            const nextIndex = (currentIndex + 1) % tabs.length;
            setActiveTab(tabs[nextIndex].id);
          }
        }
        return;
      }

      // Zoom Controls (Ctrl + +, Ctrl + -, Ctrl + 0)
      if (isCtrlOrMeta && (e.key === '+' || e.key === '=')) {
        e.preventDefault();
        if (activeTab) zoomIn(activeTab.id);
        return;
      }
      if (isCtrlOrMeta && (e.key === '-' || e.key === '_')) {
        e.preventDefault();
        if (activeTab) zoomOut(activeTab.id);
        return;
      }
      if (isCtrlOrMeta && e.key === '0') {
        e.preventDefault();
        if (activeTab) resetZoom(activeTab.id);
        return;
      }

      // Shortcuts modal toggle (?)
      if (e.key === '?') {
        e.preventDefault();
        onToggleShortcutsModal();
        return;
      }

      if (!activeTab) return;

      // If active tab is a Markdown document
      if (activeTab.fileType === 'markdown') {
        const scrollContainer = document.querySelector('.scroll-smooth') as HTMLElement | null;
        switch (e.key) {
          case 'ArrowDown':
          case 'j':
            e.preventDefault();
            if (scrollContainer) scrollContainer.scrollBy({ top: 80, behavior: 'smooth' });
            break;
          case 'ArrowUp':
          case 'k':
            e.preventDefault();
            if (scrollContainer) scrollContainer.scrollBy({ top: -80, behavior: 'smooth' });
            break;
          case 'PageDown':
            e.preventDefault();
            if (scrollContainer) scrollContainer.scrollBy({ top: 400, behavior: 'smooth' });
            break;
          case 'PageUp':
            e.preventDefault();
            if (scrollContainer) scrollContainer.scrollBy({ top: -400, behavior: 'smooth' });
            break;
          case 'Home':
            e.preventDefault();
            if (scrollContainer) scrollContainer.scrollTo({ top: 0, behavior: 'smooth' });
            break;
          case 'End':
            e.preventDefault();
            if (scrollContainer) scrollContainer.scrollTo({ top: scrollContainer.scrollHeight, behavior: 'smooth' });
            break;
          case '1':
            e.preventDefault();
            setMarkdownViewMode(activeTab.id, 'rendered');
            break;
          case '2':
            e.preventDefault();
            setMarkdownViewMode(activeTab.id, 'split');
            break;
          case '3':
            e.preventDefault();
            setMarkdownViewMode(activeTab.id, 'raw');
            break;
          default:
            break;
        }
        return;
      }

      // PDF Navigation shortcuts
      switch (e.key) {
        case 'ArrowRight':
        case 'PageDown':
        case 'j':
          e.preventDefault();
          if (activeTab.viewMode === 'two-page') {
            setCurrentPage(activeTab.id, Math.min(activeTab.totalPages, activeTab.currentPage + 2));
          } else {
            setCurrentPage(activeTab.id, Math.min(activeTab.totalPages, activeTab.currentPage + 1));
          }
          break;

        case 'ArrowLeft':
        case 'PageUp':
        case 'k':
          e.preventDefault();
          if (activeTab.viewMode === 'two-page') {
            setCurrentPage(activeTab.id, Math.max(1, activeTab.currentPage - 2));
          } else {
            setCurrentPage(activeTab.id, Math.max(1, activeTab.currentPage - 1));
          }
          break;

        case 'Home':
          e.preventDefault();
          setCurrentPage(activeTab.id, 1);
          break;

        case 'End':
          e.preventDefault();
          setCurrentPage(activeTab.id, activeTab.totalPages);
          break;

        case 'w':
          e.preventDefault();
          setZoomMode(activeTab.id, 'fit-width');
          break;

        case 'p':
          e.preventDefault();
          setZoomMode(activeTab.id, 'fit-page');
          break;

        case '1':
          e.preventDefault();
          setViewMode(activeTab.id, 'continuous');
          break;

        case '2':
          e.preventDefault();
          setViewMode(activeTab.id, 'single');
          break;

        case '3':
          e.preventDefault();
          setViewMode(activeTab.id, 'two-page');
          break;

        case 'r':
          e.preventDefault();
          rotateClockwise(activeTab.id);
          break;

        case 'R':
          e.preventDefault();
          rotateCounterClockwise(activeTab.id);
          break;

        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    tabs,
    activeTabId,
    setActiveTab,
    closeTab,
    setCurrentPage,
    zoomIn,
    zoomOut,
    resetZoom,
    setZoomMode,
    rotateClockwise,
    rotateCounterClockwise,
    setViewMode,
    setMarkdownViewMode,
    openDocument,
    onToggleShortcutsModal,
  ]);
};
