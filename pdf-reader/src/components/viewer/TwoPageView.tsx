import React, { useEffect, useMemo, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { TabItem } from '../../types';
import { PDFPageCanvas } from './PDFPageCanvas';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';

interface TwoPageViewProps {
  tab: TabItem;
  doc: pdfjsLib.PDFDocumentProxy;
}

export const TwoPageView: React.FC<TwoPageViewProps> = ({ tab, doc }) => {
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

  // Determine left and right page numbers
  // Standard two-page spread: Page 1 on left, Page 2 on right; or Page 1 alone if cover.
  // Here we pair: odd page on left, even page on right: [1, 2], [3, 4], [5, 6]...
  const leftPage = tab.currentPage % 2 === 0 ? tab.currentPage - 1 : tab.currentPage;
  const rightPage = leftPage + 1 <= tab.totalPages ? leftPage + 1 : null;

  const leftDim = tab.pageDimensions[leftPage - 1] || tab.pageDimensions[0] || { width: 595, height: 842 };
  const rightDim = rightPage
    ? tab.pageDimensions[rightPage - 1] || leftDim
    : leftDim;

  const computedScale = useMemo(() => {
    const isTransposed = (tab.rotation / 90) % 2 !== 0;
    const p1Width = isTransposed ? leftDim.height : leftDim.width;
    const p1Height = isTransposed ? leftDim.width : leftDim.height;
    const p2Width = rightPage ? (isTransposed ? rightDim.height : rightDim.width) : 0;
    const p2Height = rightPage ? (isTransposed ? rightDim.width : rightDim.height) : 0;

    const totalSpreadWidth = p1Width + p2Width + (rightPage ? 24 : 0); // 24px book spine gap
    const maxSpreadHeight = Math.max(p1Height, p2Height);

    const horizontalPadding = 80;
    const verticalPadding = 64;

    if (tab.zoomMode === 'fit-width') {
      const availableWidth = Math.max(200, containerSize.width - horizontalPadding);
      return Number((availableWidth / totalSpreadWidth).toFixed(2));
    }

    if (tab.zoomMode === 'fit-page') {
      const availableWidth = Math.max(200, containerSize.width - horizontalPadding);
      const availableHeight = Math.max(200, containerSize.height - verticalPadding);
      const scaleX = availableWidth / totalSpreadWidth;
      const scaleY = availableHeight / maxSpreadHeight;
      return Number(Math.min(scaleX, scaleY).toFixed(2));
    }

    return tab.zoomLevel;
  }, [tab.zoomMode, tab.zoomLevel, leftDim, rightDim, rightPage, tab.rotation, containerSize]);

  const handlePrevSpread = () => {
    const prev = Math.max(1, leftPage - 2);
    setCurrentPage(tab.id, prev);
  };

  const handleNextSpread = () => {
    if (rightPage && rightPage < tab.totalPages) {
      setCurrentPage(tab.id, rightPage + 1);
    } else if (leftPage + 1 < tab.totalPages) {
      setCurrentPage(tab.id, leftPage + 2);
    }
  };

  const handleWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey) return;
    if (Math.abs(e.deltaY) > 30) {
      if (e.deltaY > 0) handleNextSpread();
      else handlePrevSpread();
    }
  };

  return (
    <div
      ref={containerRef}
      onWheel={handleWheel}
      className="relative flex-1 w-full h-full overflow-auto bg-zinc-900/90 flex items-center justify-center p-8 select-none"
    >
      {/* Navigation arrows */}
      <button
        onClick={handlePrevSpread}
        disabled={leftPage <= 1}
        title="Previous Spread (Page Up, Left Arrow)"
        className={`fixed left-6 top-1/2 -translate-y-1/2 p-3 rounded-full bg-zinc-800/80 text-zinc-200 hover:bg-zinc-700/90 hover:text-white border border-zinc-700/50 shadow-xl backdrop-blur-sm transition-all z-10 ${
          leftPage <= 1 ? 'opacity-20 pointer-events-none' : 'opacity-70 hover:opacity-100 hover:scale-105'
        }`}
      >
        <ChevronLeft className="w-6 h-6" />
      </button>

      <button
        onClick={handleNextSpread}
        disabled={!rightPage || rightPage >= tab.totalPages}
        title="Next Spread (Page Down, Right Arrow)"
        className={`fixed right-6 top-1/2 -translate-y-1/2 p-3 rounded-full bg-zinc-800/80 text-zinc-200 hover:bg-zinc-700/90 hover:text-white border border-zinc-700/50 shadow-xl backdrop-blur-sm transition-all z-10 ${
          !rightPage || rightPage >= tab.totalPages ? 'opacity-20 pointer-events-none' : 'opacity-70 hover:opacity-100 hover:scale-105'
        }`}
      >
        <ChevronRight className="w-6 h-6" />
      </button>

      {/* Two Pages side by side (Book Spread) */}
      <div className="flex items-center justify-center gap-6 m-auto">
        <div className="relative shadow-2xl rounded">
          <PDFPageCanvas
            doc={doc}
            pageNumber={leftPage}
            scale={computedScale}
            rotation={tab.rotation}
            expectedWidth={leftDim.width}
            expectedHeight={leftDim.height}
            isVisible={true}
          />
        </div>

        {rightPage && (
          <div className="relative shadow-2xl rounded">
            <PDFPageCanvas
              doc={doc}
              pageNumber={rightPage}
              scale={computedScale}
              rotation={tab.rotation}
              expectedWidth={rightDim.width}
              expectedHeight={rightDim.height}
              isVisible={true}
            />
          </div>
        )}
      </div>
    </div>
  );
};
