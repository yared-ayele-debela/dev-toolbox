import React, { useEffect, useMemo, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { TabItem } from '../../types';
import { PDFPageCanvas } from './PDFPageCanvas';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';

interface SinglePageViewProps {
  tab: TabItem;
  doc: pdfjsLib.PDFDocumentProxy;
}

export const SinglePageView: React.FC<SinglePageViewProps> = ({ tab, doc }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const setCurrentPage = useAppStore((s) => s.setCurrentPage);
  const [containerSize, setContainerSize] = useState<{ width: number; height: number }>({
    width: 800,
    height: 600,
  });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const dim = tab.pageDimensions[tab.currentPage - 1] || tab.pageDimensions[0] || { width: 595, height: 842 };

  const computedScale = useMemo(() => {
    const isTransposed = (tab.rotation / 90) % 2 !== 0;
    const pageWidth = isTransposed ? dim.height : dim.width;
    const pageHeight = isTransposed ? dim.width : dim.height;

    const horizontalPadding = 64;
    const verticalPadding = 64;

    if (tab.zoomMode === 'fit-width') {
      const availableWidth = Math.max(200, containerSize.width - horizontalPadding);
      return Number((availableWidth / pageWidth).toFixed(2));
    }

    if (tab.zoomMode === 'fit-page') {
      const availableWidth = Math.max(200, containerSize.width - horizontalPadding);
      const availableHeight = Math.max(200, containerSize.height - verticalPadding);
      const scaleX = availableWidth / pageWidth;
      const scaleY = availableHeight / pageHeight;
      return Number(Math.min(scaleX, scaleY).toFixed(2));
    }

    return tab.zoomLevel;
  }, [tab.zoomMode, tab.zoomLevel, dim, tab.rotation, containerSize]);

  // Handle wheel for page flipping
  const handleWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey) return; // Allow pinch/ctrl zoom
    if (Math.abs(e.deltaY) > 30) {
      if (e.deltaY > 0 && tab.currentPage < tab.totalPages) {
        setCurrentPage(tab.id, tab.currentPage + 1);
      } else if (e.deltaY < 0 && tab.currentPage > 1) {
        setCurrentPage(tab.id, tab.currentPage - 1);
      }
    }
  };

  return (
    <div
      ref={containerRef}
      onWheel={handleWheel}
      className="relative flex-1 w-full h-full overflow-auto bg-zinc-900/90 flex items-center justify-center p-8 select-none"
    >
      {/* Floating Prev/Next navigation controls */}
      <button
        onClick={() => setCurrentPage(tab.id, tab.currentPage - 1)}
        disabled={tab.currentPage <= 1}
        title="Previous Page (Left Arrow, Page Up)"
        className={`fixed left-6 top-1/2 -translate-y-1/2 p-3 rounded-full bg-zinc-800/80 text-zinc-200 hover:bg-zinc-700/90 hover:text-white border border-zinc-700/50 shadow-xl backdrop-blur-sm transition-all z-10 ${
          tab.currentPage <= 1 ? 'opacity-20 pointer-events-none' : 'opacity-70 hover:opacity-100 hover:scale-105'
        }`}
      >
        <ChevronLeft className="w-6 h-6" />
      </button>

      <button
        onClick={() => setCurrentPage(tab.id, tab.currentPage + 1)}
        disabled={tab.currentPage >= tab.totalPages}
        title="Next Page (Right Arrow, Page Down)"
        className={`fixed right-6 top-1/2 -translate-y-1/2 p-3 rounded-full bg-zinc-800/80 text-zinc-200 hover:bg-zinc-700/90 hover:text-white border border-zinc-700/50 shadow-xl backdrop-blur-sm transition-all z-10 ${
          tab.currentPage >= tab.totalPages ? 'opacity-20 pointer-events-none' : 'opacity-70 hover:opacity-100 hover:scale-105'
        }`}
      >
        <ChevronRight className="w-6 h-6" />
      </button>

      {/* Page Canvas */}
      <div className="flex items-center justify-center m-auto">
        <PDFPageCanvas
          doc={doc}
          pageNumber={tab.currentPage}
          scale={computedScale}
          rotation={tab.rotation}
          expectedWidth={dim.width}
          expectedHeight={dim.height}
          isVisible={true}
        />
      </div>
    </div>
  );
};
