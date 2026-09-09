export type ViewMode = 'continuous' | 'single' | 'two-page';

export type ZoomMode = 'fit-width' | 'fit-page' | 'custom';

export type DocumentType = 'pdf' | 'markdown';

export type MarkdownViewMode = 'rendered' | 'raw' | 'split';

export interface PageDimension {
  pageNumber: number;
  width: number;
  height: number;
}

export interface MarkdownHeading {
  id: string;
  level: number;
  text: string;
}

export interface TabItem {
  id: string;
  filePath?: string;
  fileName: string;
  fileData?: Uint8Array;
  fileType: DocumentType;
  currentPage: number;
  totalPages: number;
  zoomMode: ZoomMode;
  zoomLevel: number; // 1.0 = 100%
  rotation: number; // 0, 90, 180, 270
  viewMode: ViewMode;
  markdownViewMode?: MarkdownViewMode;
  markdownContent?: string;
  pageDimensions: PageDimension[];
  lastModified?: number;
}

export interface RecentFile {
  id?: number;
  path: string;
  title: string;
  lastOpened: number;
  lastPage: number;
  totalPages: number;
  fileType?: DocumentType;
}

export interface UserSettings {
  defaultViewMode: ViewMode;
  defaultZoomMode: ZoomMode;
  defaultZoomLevel: number;
  defaultMarkdownViewMode?: MarkdownViewMode;
  theme: 'dark' | 'light' | 'system';
  isVimMode: boolean;
}

