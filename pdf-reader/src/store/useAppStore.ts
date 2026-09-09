import { create } from 'zustand';
import { MarkdownViewMode, RecentFile, TabItem, UserSettings, ViewMode, ZoomMode } from '../types';
import { pdfService } from '../services/pdfService';
import { fileService } from '../services/fileService';
import { dbService } from '../db/database';

interface AppStoreState {
  tabs: TabItem[];
  activeTabId: string | null;
  recentFiles: RecentFile[];
  settings: UserSettings;
  isLoading: boolean;
  loadingMessage: string;

  // Actions
  openDocument: (file: { name: string; path?: string; data: Uint8Array; initialPage?: number }) => Promise<void>;
  closeTab: (tabId: string) => void;
  setActiveTab: (tabId: string) => void;
  setCurrentPage: (tabId: string, page: number) => void;
  setZoomMode: (tabId: string, mode: ZoomMode, customLevel?: number) => void;
  zoomIn: (tabId: string) => void;
  zoomOut: (tabId: string) => void;
  resetZoom: (tabId: string) => void;
  rotateClockwise: (tabId: string) => void;
  rotateCounterClockwise: (tabId: string) => void;
  setViewMode: (tabId: string, mode: ViewMode) => void;
  setMarkdownViewMode: (tabId: string, mode: MarkdownViewMode) => void;
  updateMarkdownContent: (tabId: string, content: string) => void;
  loadRecentFiles: () => Promise<void>;
  removeRecentFile: (path: string) => Promise<void>;
  loadSettings: () => Promise<void>;
  updateSettings: (newSettings: Partial<UserSettings>) => Promise<void>;
}

const DEFAULT_SETTINGS: UserSettings = {
  defaultViewMode: 'continuous',
  defaultZoomMode: 'fit-width',
  defaultZoomLevel: 1.0,
  defaultMarkdownViewMode: 'rendered',
  theme: 'dark',
  isVimMode: false,
};

export const useAppStore = create<AppStoreState>((set, get) => ({
  tabs: [],
  activeTabId: null,
  recentFiles: [],
  settings: DEFAULT_SETTINGS,
  isLoading: false,
  loadingMessage: '',

  openDocument: async ({ name, path, data, initialPage = 1 }) => {
    // If a tab with this path is already open, just activate it
    const { tabs, settings } = get();
    if (path) {
      const existingTab = tabs.find((t) => t.filePath === path);
      if (existingTab) {
        set({ activeTabId: existingTab.id });
        return;
      }
    }

    set({ isLoading: true, loadingMessage: `Loading ${name}...` });

    try {
      const tabId = `tab_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
      const isMarkdown = fileService.isMarkdownFile(name) || (path ? fileService.isMarkdownFile(path) : false);

      let newTab: TabItem;

      if (isMarkdown) {
        const text = new TextDecoder('utf-8').decode(data);
        newTab = {
          id: tabId,
          fileName: name,
          filePath: path,
          fileData: data,
          fileType: 'markdown',
          currentPage: 1,
          totalPages: 1,
          zoomMode: 'fit-width',
          zoomLevel: 1.0,
          rotation: 0,
          viewMode: 'continuous',
          markdownViewMode: settings.defaultMarkdownViewMode || 'rendered',
          markdownContent: text,
          pageDimensions: [],
          lastModified: Date.now(),
        };
      } else {
        const doc = await pdfService.loadDocument(tabId, data);
        const totalPages = doc.numPages;
        const pageDimensions = await pdfService.extractPageDimensions(doc);

        newTab = {
          id: tabId,
          fileName: name,
          filePath: path,
          fileData: data,
          fileType: 'pdf',
          currentPage: Math.min(Math.max(1, initialPage), totalPages),
          totalPages,
          zoomMode: settings.defaultZoomMode,
          zoomLevel: settings.defaultZoomLevel,
          rotation: 0,
          viewMode: settings.defaultViewMode,
          pageDimensions,
          lastModified: Date.now(),
        };
      }

      set((state) => ({
        tabs: [...state.tabs, newTab],
        activeTabId: tabId,
        isLoading: false,
        loadingMessage: '',
      }));

      // If document has a file path, save to SQLite recent files
      if (path) {
        await dbService.addRecentFile({
          path,
          title: name,
          lastOpened: Date.now(),
          lastPage: newTab.currentPage,
          totalPages: newTab.totalPages,
        });
        get().loadRecentFiles();
      }
    } catch (err: any) {
      console.error('Failed to open document:', err);
      set({ isLoading: false, loadingMessage: '' });
      alert(`Could not open document: ${err?.message || 'Unknown error'}`);
    }
  },

  closeTab: (tabId: string) => {
    const tabToClose = get().tabs.find((t) => t.id === tabId);
    if (tabToClose?.fileType === 'pdf') {
      pdfService.unloadDocument(tabId);
    }

    set((state) => {
      const newTabs = state.tabs.filter((t) => t.id !== tabId);
      let newActiveId = state.activeTabId;

      if (state.activeTabId === tabId) {
        if (newTabs.length > 0) {
          const closedIndex = state.tabs.findIndex((t) => t.id === tabId);
          const nextIndex = Math.min(closedIndex, newTabs.length - 1);
          newActiveId = newTabs[nextIndex].id;
        } else {
          newActiveId = null;
        }
      }

      return {
        tabs: newTabs,
        activeTabId: newActiveId,
      };
    });
  },

  setActiveTab: (tabId: string) => {
    set({ activeTabId: tabId });
  },

  setCurrentPage: (tabId: string, page: number) => {
    set((state) => {
      const tabs = state.tabs.map((tab) => {
        if (tab.id !== tabId) return tab;
        const clampedPage = Math.min(Math.max(1, page), tab.totalPages);
        if (tab.filePath) {
          dbService.updateRecentFilePage(tab.filePath, clampedPage);
        }
        return { ...tab, currentPage: clampedPage };
      });
      return { tabs };
    });
  },

  setZoomMode: (tabId: string, mode: ZoomMode, customLevel?: number) => {
    set((state) => ({
      tabs: state.tabs.map((tab) => {
        if (tab.id !== tabId) return tab;
        return {
          ...tab,
          zoomMode: mode,
          zoomLevel: customLevel !== undefined ? customLevel : tab.zoomLevel,
        };
      }),
    }));
  },

  zoomIn: (tabId: string) => {
    set((state) => ({
      tabs: state.tabs.map((tab) => {
        if (tab.id !== tabId) return tab;
        const newZoom = Math.min(5.0, Number((tab.zoomLevel + 0.25).toFixed(2)));
        return {
          ...tab,
          zoomMode: 'custom',
          zoomLevel: newZoom,
        };
      }),
    }));
  },

  zoomOut: (tabId: string) => {
    set((state) => ({
      tabs: state.tabs.map((tab) => {
        if (tab.id !== tabId) return tab;
        const newZoom = Math.max(0.25, Number((tab.zoomLevel - 0.25).toFixed(2)));
        return {
          ...tab,
          zoomMode: 'custom',
          zoomLevel: newZoom,
        };
      }),
    }));
  },

  resetZoom: (tabId: string) => {
    set((state) => ({
      tabs: state.tabs.map((tab) => {
        if (tab.id !== tabId) return tab;
        return {
          ...tab,
          zoomMode: 'custom',
          zoomLevel: 1.0,
        };
      }),
    }));
  },

  rotateClockwise: (tabId: string) => {
    set((state) => ({
      tabs: state.tabs.map((tab) => {
        if (tab.id !== tabId) return tab;
        return {
          ...tab,
          rotation: (tab.rotation + 90) % 360,
        };
      }),
    }));
  },

  rotateCounterClockwise: (tabId: string) => {
    set((state) => ({
      tabs: state.tabs.map((tab) => {
        if (tab.id !== tabId) return tab;
        return {
          ...tab,
          rotation: (tab.rotation + 270) % 360,
        };
      }),
    }));
  },

  setViewMode: (tabId: string, mode: ViewMode) => {
    set((state) => ({
      tabs: state.tabs.map((tab) => {
        if (tab.id !== tabId) return tab;
        return { ...tab, viewMode: mode };
      }),
    }));
  },

  setMarkdownViewMode: (tabId: string, mode: MarkdownViewMode) => {
    set((state) => ({
      tabs: state.tabs.map((tab) => {
        if (tab.id !== tabId) return tab;
        return { ...tab, markdownViewMode: mode };
      }),
    }));
  },

  updateMarkdownContent: (tabId: string, content: string) => {
    const encoder = new TextEncoder();
    const data = encoder.encode(content);
    set((state) => ({
      tabs: state.tabs.map((tab) => {
        if (tab.id !== tabId) return tab;
        return {
          ...tab,
          markdownContent: content,
          fileData: data,
          lastModified: Date.now(),
        };
      }),
    }));
  },

  loadRecentFiles: async () => {
    const recents = await dbService.getRecentFiles(15);
    set({ recentFiles: recents });
  },

  removeRecentFile: async (path: string) => {
    await dbService.removeRecentFile(path);
    get().loadRecentFiles();
  },

  loadSettings: async () => {
    const settings = await dbService.getSetting<UserSettings>('app_settings', DEFAULT_SETTINGS);
    set({ settings });
  },

  updateSettings: async (newSettings: Partial<UserSettings>) => {
    const updated = { ...get().settings, ...newSettings };
    set({ settings: updated });
    await dbService.setSetting('app_settings', updated);
  },
}));
