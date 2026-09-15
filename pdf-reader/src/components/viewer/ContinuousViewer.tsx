import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { TabItem } from '../../types';
import { PDFPageCanvas } from './PDFPageCanvas';
import { useAppStore } from '../../store/useAppStore';

interface ContinuousViewerProps {
  tab: TabItem;
  doc: pdfjsLib.PDFDocumentProxy;
}

export const ContinuousViewer: React.FC<ContinuousViewerProps> = ({ tab, doc }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const setCurrentPage = useAppStore((s) => s.setCurrentPage);
  const [containerSize, setContainerSize] = useState<{ width: number; height: number }>({
    width: 800,
    height: 600,
  });

  // Track which page numbers are within the virtual window
  const [visiblePages, setVisiblePages] = useState<Set<number>>(new Set([1, 2, 3]));
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Listen to container resizing
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

  // Compute effective scale based on zoomMode
  const computedScale = useMemo(() => {
    if (tab.pageDimensions.length === 0) return tab.zoomLevel;

    // Use primary page dimension for fit calculations
    const primaryDim = tab.pageDimensions[0];
    const isTransposed = (tab.rotation / 90) % 2 !== 0;
    const pageWidth = isTransposed ? primaryDim.height : primaryDim.width;
    const pageHeight = isTransposed ? primaryDim.width : primaryDim.height;

    // Content container padding
    const horizontalPadding = 48; // 24px each side
    const verticalPadding = 48;

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
  }, [tab.zoomMode, tab.zoomLevel, tab.pageDimensions, tab.rotation, containerSize]);

  // Virtualization: IntersectionObserver to mount/unmount page canvases
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const pageVisibilityMap = new Map<number, boolean>();

    // Observer with generous margin (600px) so nearby pages are pre-rendered
    const virtualObserver = new IntersectionObserver(
      (entries) => {
        let changed = false;
        entries.forEach((entry) => {
          const pageNum = Number(entry.target.getAttribute('data-page-wrapper'));
          if (!isNaN(pageNum)) {
            const isIntersecting = entry.isIntersecting;
            if (pageVisibilityMap.get(pageNum) !== isIntersecting) {
              pageVisibilityMap.set(pageNum, isIntersecting);
              changed = true;
            }
          }
        });

        if (changed) {
          const visible = new Set<number>();
          pageVisibilityMap.forEach((isVisible, num) => {
            if (isVisible) visible.add(num);
          });
          setVisiblePages(visible);
        }
      },
      {
        root: container,
        rootMargin: '600px 0px 600px 0px',
        threshold: 0.01,
      }
    );

    // Active page observer to update current page in toolbar as user scrolls
    const activePageObserver = new IntersectionObserver(
      (entries) => {
        let bestEntry: IntersectionObserverEntry | null = null;
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            if (!bestEntry || entry.intersectionRatio > bestEntry.intersectionRatio) {
              bestEntry = entry;
            }
          }
        });

        if (bestEntry) {
          const pageNum = Number((bestEntry as IntersectionObserverEntry).target.getAttribute('data-page-wrapper'));
          if (!isNaN(pageNum) && pageNum !== tab.currentPage) {
            setCurrentPage(tab.id, pageNum);
          }
        }
      },
      {
        root: container,
        threshold: [0.1, 0.3, 0.6, 0.9],
      }
    );

    pageRefs.current.forEach((el) => {
      virtualObserver.observe(el);
      activePageObserver.observe(el);
    });

    return () => {
      virtualObserver.disconnect();
      activePageObserver.disconnect();
    };
  }, [tab.totalPages, tab.pageDimensions, computedScale, setCurrentPage, tab.id]);

  // Scroll to current page when changed externally (e.g. via toolbar jump)
  const isInternalScrollRef = useRef(false);
  useEffect(() => {
    if (isInternalScrollRef.current) {
      isInternalScrollRef.current = false;
      return;
    }

    const targetEl = pageRefs.current.get(tab.currentPage);
    if (targetEl && containerRef.current) {
      // Check if already in viewport
      const containerRect = containerRef.current.getBoundingClientRect();
      const pageRect = targetEl.getBoundingClientRect();
      const isPartiallyVisible = pageRect.top < containerRect.bottom && pageRect.bottom > containerRect.top;

      if (!isPartiallyVisible) {
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  }, [tab.currentPage]);

  return (
    <div
      ref={containerRef}
      className="relative flex-1 w-full h-full overflow-y-auto overflow-x-auto bg-zinc-900/90 py-8 px-4 flex flex-col items-center select-none"
    >
      <div className="flex flex-col items-center gap-6">
        {Array.from({ length: tab.totalPages }, (_, i) => i + 1).map((pageNum) => {
          const dim = tab.pageDimensions[pageNum - 1] || tab.pageDimensions[0] || { width: 595, height: 842 };
          const isVisible = visiblePages.has(pageNum);

          return (
            <div
              key={pageNum}
              data-page-wrapper={pageNum}
              ref={(el) => {
                if (el) pageRefs.current.set(pageNum, el);
                else pageRefs.current.delete(pageNum);
              }}
              className="transition-all"
            >
              <PDFPageCanvas
                doc={doc}
                pageNumber={pageNum}
                scale={computedScale}
                rotation={tab.rotation}
                expectedWidth={dim.width}
                expectedHeight={dim.height}
                isVisible={isVisible}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};
