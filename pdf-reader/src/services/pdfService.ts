import * as pdfjsLib from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { PageDimension } from '../types';

// Configure pdfjs worker
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export interface RenderPageOptions {
  doc: pdfjsLib.PDFDocumentProxy;
  pageNumber: number;
  scale: number;
  rotation: number;
  canvas: HTMLCanvasElement;
}

export interface RenderTaskHandle {
  promise: Promise<void>;
  cancel: () => void;
}

class PDFService {
  private documentCache = new Map<string, pdfjsLib.PDFDocumentProxy>();

  /**
   * Loads a PDF Document from raw bytes.
   */
  async loadDocument(id: string, data: Uint8Array): Promise<pdfjsLib.PDFDocumentProxy> {
    if (this.documentCache.has(id)) {
      return this.documentCache.get(id)!;
    }

    // Pass data as a slice to prevent detached buffer issues
    const loadingTask = pdfjsLib.getDocument({
      data: data.slice(0),
      cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@6.3.289/cmaps/',
      cMapPacked: true,
    });

    const doc = await loadingTask.promise;
    this.documentCache.set(id, doc);
    return doc;
  }

  getDocument(id: string): pdfjsLib.PDFDocumentProxy | undefined {
    return this.documentCache.get(id);
  }

  unloadDocument(id: string): void {
    const doc = this.documentCache.get(id);
    if (doc) {
      if (typeof (doc as any).destroy === 'function') {
        (doc as any).destroy();
      } else if (typeof (doc as any).cleanup === 'function') {
        (doc as any).cleanup();
      }
      this.documentCache.delete(id);
    }
  }

  /**
   * Quickly extracts the default dimensions of all pages in the document.
   * This allows the virtualizer to immediately calculate the full scrollable height.
   */
  async extractPageDimensions(doc: pdfjsLib.PDFDocumentProxy): Promise<PageDimension[]> {
    const totalPages = doc.numPages;
    const dimensions: PageDimension[] = [];

    for (let i = 1; i <= totalPages; i++) {
      const page = await doc.getPage(i);
      const viewport = page.getViewport({ scale: 1.0 });
      dimensions.push({
        pageNumber: i,
        width: viewport.width,
        height: viewport.height,
      });
    }

    return dimensions;
  }

  /**
   * Renders a single PDF page onto an HTML Canvas with high-DPI scaling and cancellation.
   */
  renderPage({ doc, pageNumber, scale, rotation, canvas }: RenderPageOptions): RenderTaskHandle {
    let activeRenderTask: pdfjsLib.RenderTask | null = null;
    let isCancelled = false;

    const promise = (async () => {
      try {
        const page = await doc.getPage(pageNumber);
        if (isCancelled) return;

        // Apply total rotation: page native rotation + user rotation
        const totalRotation = (page.rotate + rotation) % 360;
        const viewport = page.getViewport({ scale, rotation: totalRotation });

        const dpr = window.devicePixelRatio || 1;
        const ctx = canvas.getContext('2d', { alpha: false });
        if (!ctx) return;

        // Set display dimensions in CSS pixels
        canvas.style.width = `${Math.floor(viewport.width)}px`;
        canvas.style.height = `${Math.floor(viewport.height)}px`;

        // Set actual canvas drawing buffer dimensions for high DPI
        canvas.width = Math.floor(viewport.width * dpr);
        canvas.height = Math.floor(viewport.height * dpr);

        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(dpr, dpr);

        // Fill background white
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, viewport.width, viewport.height);

        const renderContext = {
          canvasContext: ctx,
          canvas: canvas,
          viewport: viewport,
        };

        activeRenderTask = page.render(renderContext as any);
        await activeRenderTask.promise;
      } catch (err: any) {
        if (err?.name !== 'RenderingCancelledException') {
          console.error(`Error rendering page ${pageNumber}:`, err);
        }
      }
    })();

    return {
      promise,
      cancel: () => {
        isCancelled = true;
        if (activeRenderTask) {
          try {
            activeRenderTask.cancel();
          } catch {
            // Ignore cancel errors
          }
        }
      },
    };
  }
}

export const pdfService = new PDFService();
