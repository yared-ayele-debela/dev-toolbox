import React, { useEffect, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { pdfService, RenderTaskHandle } from '../../services/pdfService';

interface PDFPageCanvasProps {
  doc: pdfjsLib.PDFDocumentProxy;
  pageNumber: number;
  scale: number;
  rotation: number;
  expectedWidth: number;
  expectedHeight: number;
  isVisible?: boolean; // From virtualization observer
  onVisibleChange?: (isVisible: boolean) => void;
  className?: string;
}

export const PDFPageCanvas: React.FC<PDFPageCanvasProps> = ({
  doc,
  pageNumber,
  scale,
  rotation,
  expectedWidth,
  expectedHeight,
  isVisible = true,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const activeTaskRef = useRef<RenderTaskHandle | null>(null);
  const [isRendered, setIsRendered] = useState(false);
  const [isRendering, setIsRendering] = useState(false);

  useEffect(() => {
    // If virtualization indicates page is not visible, don't mount/render canvas
    if (!isVisible) {
      if (activeTaskRef.current) {
        activeTaskRef.current.cancel();
        activeTaskRef.current = null;
      }
      setIsRendered(false);
      setIsRendering(false);
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;

    // Cancel any ongoing rendering on this canvas
    if (activeTaskRef.current) {
      activeTaskRef.current.cancel();
      activeTaskRef.current = null;
    }

    setIsRendering(true);

    const task = pdfService.renderPage({
      doc,
      pageNumber,
      scale,
      rotation,
      canvas,
    });
    activeTaskRef.current = task;

    task.promise
      .then(() => {
        setIsRendered(true);
        setIsRendering(false);
      })
      .catch(() => {
        setIsRendering(false);
      });

    return () => {
      if (activeTaskRef.current) {
        activeTaskRef.current.cancel();
        activeTaskRef.current = null;
      }
    };
  }, [doc, pageNumber, scale, rotation, isVisible]);

  // If rotation is 90 or 270, width and height swap
  const isTransposed = (rotation / 90) % 2 !== 0;
  const displayWidth = isTransposed ? expectedHeight * scale : expectedWidth * scale;
  const displayHeight = isTransposed ? expectedWidth * scale : expectedHeight * scale;

  return (
    <div
      ref={containerRef}
      data-page-number={pageNumber}
      className={`relative bg-white rounded shadow-md overflow-hidden transition-shadow select-none ${className}`}
      style={{
        width: `${Math.floor(displayWidth)}px`,
        height: `${Math.floor(displayHeight)}px`,
        minWidth: `${Math.floor(displayWidth)}px`,
        minHeight: `${Math.floor(displayHeight)}px`,
      }}
    >
      {isVisible ? (
        <canvas
          ref={canvasRef}
          className="absolute inset-0 block w-full h-full"
        />
      ) : (
        /* Virtualized placeholder while out of viewport */
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-100 text-zinc-400">
          <span className="text-xs font-medium font-mono uppercase tracking-wider">Page {pageNumber}</span>
        </div>
      )}

      {/* Subtle page indicator floating at bottom-right of page */}
      <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-zinc-900/60 text-white text-[10px] font-mono pointer-events-none opacity-0 hover:opacity-100 transition-opacity">
        {pageNumber}
      </div>

      {isRendering && !isRendered && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/40 pointer-events-none">
          <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}
    </div>
  );
};
