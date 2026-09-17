import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { TabItem, MarkdownHeading } from '../../types';
import { markdownService, MarkdownStats } from '../../services/markdownService';
import { useAppStore } from '../../store/useAppStore';
import {
  Code2,
  Columns,
  Copy,
  Check,
  Search,
  X,
  ListTree,
  FileCode,
  Clock,
  Type,
  ChevronRight,
  WrapText,
  Eye,
} from 'lucide-react';

interface MarkdownViewerProps {
  tab: TabItem;
}

export const MarkdownViewer: React.FC<MarkdownViewerProps> = ({ tab }) => {
  const { setMarkdownViewMode } = useAppStore();
  const content = tab.markdownContent || '';

  const [outlineOpen, setOutlineOpen] = useState(true);
  const [outlineFilter, setOutlineFilter] = useState('');
  const [activeHeadingId, setActiveHeadingId] = useState<string>('');
  const [copiedDocument, setCopiedDocument] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [wrapLines, setWrapLines] = useState(true);

  const containerRef = useRef<HTMLDivElement>(null);
  const renderedContentRef = useRef<HTMLDivElement>(null);
  const rawContentRef = useRef<HTMLDivElement>(null);

  // Compute stats and outline
  const stats: MarkdownStats = useMemo(() => {
    return markdownService.calculateStats(content);
  }, [content]);

  const headings: MarkdownHeading[] = useMemo(() => {
    return markdownService.extractHeadings(content);
  }, [content]);

  // Filtered headings for outline search
  const filteredHeadings = useMemo(() => {
    if (!outlineFilter.trim()) return headings;
    const q = outlineFilter.toLowerCase();
    return headings.filter((h) => h.text.toLowerCase().includes(q));
  }, [headings, outlineFilter]);

  // Render HTML from markdown
  const renderedHtml = useMemo(() => {
    return markdownService.renderToHtml(content);
  }, [content]);

  // Copy full markdown document
  const handleCopyDocument = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedDocument(true);
      setTimeout(() => setCopiedDocument(false), 2000);
    } catch (err) {
      console.error('Failed to copy document:', err);
    }
  };

  // Scroll to heading from outline
  const scrollToHeading = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveHeadingId(id);
    }
  };

  // Setup click handlers for interactive code block copy buttons inside rendered HTML
  useEffect(() => {
    const container = renderedContentRef.current;
    if (!container) return;

    const handleCopyClick = async (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const copyBtn = target.closest('.markdown-copy-code-btn') as HTMLElement | null;
      if (!copyBtn) return;

      e.preventDefault();
      e.stopPropagation();

      const encodedCode = copyBtn.dataset.code;
      if (encodedCode) {
        try {
          const code = decodeURIComponent(encodedCode);
          await navigator.clipboard.writeText(code);

          const span = copyBtn.querySelector('span');
          const originalText = span ? span.innerText : 'Copy';
          if (span) span.innerText = 'Copied!';
          copyBtn.classList.add('bg-emerald-700/80', 'text-white');

          setTimeout(() => {
            if (span) span.innerText = originalText;
            copyBtn.classList.remove('bg-emerald-700/80', 'text-white');
          }, 2000);
        } catch (err) {
          console.error('Failed to copy code snippet:', err);
        }
      }
    };

    const handleAnchorClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const anchor = target.closest('a') as HTMLAnchorElement | null;
      if (!anchor) return;

      const href = anchor.getAttribute('href');
      if (href && href.startsWith('#')) {
        e.preventDefault();
        const targetId = href.substring(1);
        const el = document.getElementById(targetId);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    };

    container.addEventListener('click', handleCopyClick);
    container.addEventListener('click', handleAnchorClick);

    return () => {
      container.removeEventListener('click', handleCopyClick);
      container.removeEventListener('click', handleAnchorClick);
    };
  }, [renderedHtml]);

  // Track active heading on scroll
  const handleScroll = useCallback(() => {
    if (!headings.length) return;

    const headingElements = headings
      .map((h) => ({ id: h.id, el: document.getElementById(h.id) }))
      .filter((item): item is { id: string; el: HTMLElement } => item.el !== null);

    const scrollPos = (containerRef.current?.scrollTop || 0) + 120;

    for (let i = headingElements.length - 1; i >= 0; i--) {
      const { id, el } = headingElements[i];
      if (el.offsetTop <= scrollPos) {
        setActiveHeadingId(id);
        return;
      }
    }

    if (headingElements.length > 0) {
      setActiveHeadingId(headingElements[0].id);
    }
  }, [headings]);

  const viewMode = tab.markdownViewMode || 'rendered';
  const fontSizePx = Math.max(12, Math.min(32, Math.round(15 * tab.zoomLevel)));

  // Raw lines for raw view
  const rawLines = useMemo(() => content.split('\n'), [content]);

  return (
    <div className="flex-1 flex flex-col h-full w-full bg-zinc-950 text-zinc-100 select-text overflow-hidden font-sans">
      {/* Markdown Sub-Header / Meta Bar */}
      <div className="h-10 bg-zinc-900/90 border-b border-zinc-800/80 px-4 flex items-center justify-between text-xs select-none backdrop-blur-sm z-10 flex-shrink-0">
        {/* Left Side: Outline Toggle & Stats */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setOutlineOpen((prev) => !prev)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors ${
              outlineOpen
                ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
            }`}
            title="Toggle Outline / Table of Contents"
          >
            <ListTree className="w-3.5 h-3.5" />
            <span className="font-medium">Outline</span>
            {headings.length > 0 && (
              <span className="px-1.5 py-0.2 bg-zinc-800 rounded-full text-[10px] text-zinc-400 font-mono">
                {headings.length}
              </span>
            )}
          </button>

          <div className="h-4 w-[1px] bg-zinc-800" />

          {/* Document Stats Badges */}
          <div className="hidden sm:flex items-center gap-3 text-zinc-400">
            <div className="flex items-center gap-1" title="Word count">
              <Type className="w-3.5 h-3.5 text-zinc-500" />
              <span>{stats.wordCount.toLocaleString()} words</span>
            </div>
            <div className="flex items-center gap-1" title="Estimated reading time">
              <Clock className="w-3.5 h-3.5 text-zinc-500" />
              <span>~{stats.readingTimeMinutes} min read</span>
            </div>
            <div className="flex items-center gap-1" title="Total lines">
              <FileCode className="w-3.5 h-3.5 text-zinc-500" />
              <span>{stats.lineCount} lines</span>
            </div>
          </div>
        </div>

        {/* Right Side: View Mode Switcher, Search, Copy */}
        <div className="flex items-center gap-2">
          {/* Search Toggle */}
          <div className="relative flex items-center">
            {searchOpen ? (
              <div className="flex items-center bg-zinc-950 border border-zinc-750 rounded-md px-2 py-0.5 text-xs">
                <Search className="w-3 h-3 text-zinc-400 mr-1.5" />
                <input
                  type="text"
                  placeholder="Find in text..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  autoFocus
                  className="bg-transparent text-zinc-100 outline-none w-28 sm:w-40 font-mono text-[11px]"
                />
                <button
                  onClick={() => {
                    setSearchQuery('');
                    setSearchOpen(false);
                  }}
                  className="p-0.5 hover:text-white text-zinc-500"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setSearchOpen(true)}
                className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
                title="Search in document"
              >
                <Search className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* View Mode Switcher */}
          <div className="flex items-center bg-zinc-950 p-0.5 rounded-md border border-zinc-800">
            <button
              onClick={() => setMarkdownViewMode(tab.id, 'rendered')}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                viewMode === 'rendered'
                  ? 'bg-zinc-800 text-zinc-100 shadow-sm font-medium'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
              title="Rendered Markdown (Preview)"
            >
              <Eye className="w-3 h-3" />
              <span className="hidden md:inline">Preview</span>
            </button>

            <button
              onClick={() => setMarkdownViewMode(tab.id, 'split')}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                viewMode === 'split'
                  ? 'bg-zinc-800 text-zinc-100 shadow-sm font-medium'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
              title="Split View (Source & Preview)"
            >
              <Columns className="w-3 h-3" />
              <span className="hidden md:inline">Split</span>
            </button>

            <button
              onClick={() => setMarkdownViewMode(tab.id, 'raw')}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                viewMode === 'raw'
                  ? 'bg-zinc-800 text-zinc-100 shadow-sm font-medium'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
              title="Raw Source View"
            >
              <Code2 className="w-3 h-3" />
              <span className="hidden md:inline">Source</span>
            </button>
          </div>

          {/* Copy Markdown Document */}
          <button
            onClick={handleCopyDocument}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors border ${
              copiedDocument
                ? 'bg-emerald-600/20 text-emerald-400 border-emerald-500/40'
                : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border-zinc-700/60'
            }`}
            title="Copy Raw Markdown"
          >
            {copiedDocument ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span>Copied!</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy MD</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Collapsible Outline / Table of Contents Drawer */}
        {outlineOpen && (
          <aside className="w-64 border-r border-zinc-800/80 bg-zinc-925 flex flex-col flex-shrink-0 z-10 transition-all select-none">
            <div className="p-2.5 border-b border-zinc-800/80">
              <div className="relative">
                <Search className="w-3 h-3 absolute left-2 top-2.5 text-zinc-500" />
                <input
                  type="text"
                  placeholder="Filter headings..."
                  value={outlineFilter}
                  onChange={(e) => setOutlineFilter(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-md pl-7 pr-2 py-1 text-xs text-zinc-200 placeholder-zinc-500 outline-none focus:border-indigo-500/80 font-sans"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
              {filteredHeadings.length === 0 ? (
                <div className="text-center py-8 text-zinc-500 text-xs">
                  {headings.length === 0 ? 'No headings found in document.' : 'No matching headings.'}
                </div>
              ) : (
                filteredHeadings.map((h) => {
                  const isActive = activeHeadingId === h.id;
                  return (
                    <button
                      key={h.id}
                      onClick={() => scrollToHeading(h.id)}
                      className={`w-full text-left flex items-center gap-1.5 px-2 py-1.5 rounded-md text-xs transition-colors group ${
                        isActive
                          ? 'bg-indigo-600/15 text-indigo-300 font-medium'
                          : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
                      }`}
                      style={{
                        paddingLeft: `${Math.max(8, (h.level - 1) * 14 + 8)}px`,
                      }}
                      title={h.text}
                    >
                      <ChevronRight
                        className={`w-2.5 h-2.5 flex-shrink-0 transition-transform ${
                          isActive ? 'text-indigo-400' : 'text-zinc-600 group-hover:text-zinc-400'
                        }`}
                      />
                      <span className="truncate flex-1">{h.text}</span>
                      <span className="text-[9px] font-mono text-zinc-600 uppercase">H{h.level}</span>
                    </button>
                  );
                })
              )}
            </div>
          </aside>
        )}

        {/* Viewer Viewport Based on ViewMode */}
        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto overflow-x-hidden flex flex-col items-center bg-zinc-950 scroll-smooth"
        >
          {/* 1. Rendered Mode */}
          {viewMode === 'rendered' && (
            <div
              ref={renderedContentRef}
              className="w-full max-w-4xl px-8 sm:px-12 py-10 transition-all"
              style={{ fontSize: `${fontSizePx}px` }}
            >
              <article
                className="markdown-body"
                dangerouslySetInnerHTML={{ __html: renderedHtml }}
              />
            </div>
          )}

          {/* 2. Raw Mode */}
          {viewMode === 'raw' && (
            <div className="w-full h-full flex flex-col bg-zinc-950">
              <div className="flex items-center justify-between px-4 py-1.5 bg-zinc-900 border-b border-zinc-800/80 text-xs text-zinc-400 select-none">
                <span className="font-mono text-[11px] text-zinc-500">RAW MARKDOWN SOURCE</span>
                <button
                  onClick={() => setWrapLines((prev) => !prev)}
                  className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] transition-colors ${
                    wrapLines ? 'bg-indigo-600/20 text-indigo-300' : 'text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  <WrapText className="w-3 h-3" />
                  <span>Word Wrap</span>
                </button>
              </div>
              <div
                ref={rawContentRef}
                className="flex-1 overflow-auto p-4 font-mono text-xs text-zinc-300 leading-relaxed"
                style={{ fontSize: `${fontSizePx - 2}px` }}
              >
                <div className="flex gap-4">
                  {/* Line numbers column */}
                  <div className="select-none text-right text-zinc-600 pr-2 border-r border-zinc-850 font-mono text-[11px]">
                    {rawLines.map((_, idx) => (
                      <div key={idx}>{idx + 1}</div>
                    ))}
                  </div>
                  {/* Source content */}
                  <pre
                    className={`flex-1 m-0 p-0 text-zinc-200 font-mono ${
                      wrapLines ? 'whitespace-pre-wrap break-words' : 'whitespace-pre'
                    }`}
                  >
                    <code>{content}</code>
                  </pre>
                </div>
              </div>
            </div>
          )}

          {/* 3. Split Mode */}
          {viewMode === 'split' && (
            <div className="w-full h-full flex divide-x divide-zinc-800">
              {/* Left: Raw Code */}
              <div className="w-1/2 h-full flex flex-col bg-zinc-950 overflow-hidden">
                <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-900 border-b border-zinc-800 text-[11px] font-mono text-zinc-500 select-none">
                  <span>MARKDOWN SOURCE</span>
                  <button
                    onClick={() => setWrapLines((prev) => !prev)}
                    className={`flex items-center gap-1 px-1.5 py-0.5 rounded transition-colors ${
                      wrapLines ? 'bg-indigo-600/20 text-indigo-300' : 'text-zinc-500 hover:text-zinc-300'
                    }`}
                  >
                    <WrapText className="w-3 h-3" />
                    <span>Wrap</span>
                  </button>
                </div>
                <div
                  className="flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed text-zinc-300"
                  style={{ fontSize: `${fontSizePx - 2}px` }}
                >
                  <pre
                    className={`m-0 p-0 text-zinc-200 font-mono ${
                      wrapLines ? 'whitespace-pre-wrap break-words' : 'whitespace-pre'
                    }`}
                  >
                    <code>{content}</code>
                  </pre>
                </div>
              </div>

              {/* Right: Rendered Preview */}
              <div className="w-1/2 h-full overflow-y-auto p-6 sm:p-8 bg-zinc-950">
                <div
                  ref={renderedContentRef}
                  style={{ fontSize: `${fontSizePx}px` }}
                >
                  <article
                    className="markdown-body"
                    dangerouslySetInnerHTML={{ __html: renderedHtml }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
