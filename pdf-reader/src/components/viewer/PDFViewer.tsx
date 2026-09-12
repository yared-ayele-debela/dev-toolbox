import React, { useEffect, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import { TabItem } from '../../types';
import { pdfService } from '../../services/pdfService';
import { ContinuousViewer } from './ContinuousViewer';
import { SinglePageView } from './SinglePageView';
import { TwoPageView } from './TwoPageView';
import { Loader2 } from 'lucide-react';

interface PDFViewerProps {
  tab: TabItem;
}

export const PDFViewer: React.FC<PDFViewerProps> = ({ tab }) => {
  const [doc, setDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    const load = async () => {
      try {
        let loadedDoc = pdfService.getDocument(tab.id);
        if (!loadedDoc && tab.fileData) {
          loadedDoc = await pdfService.loadDocument(tab.id, tab.fileData);
        }
        if (isMounted) {
          setDoc(loadedDoc || null);
          setLoading(false);
        }
      } catch (err) {
        console.error('Failed to load document for tab:', tab.id, err);
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      isMounted = false;
    };
  }, [tab.id, tab.fileData]);

  if (loading || !doc) {
    return (
      <div className="flex-1 w-full h-full flex flex-col items-center justify-center bg-zinc-950 text-zinc-400 gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
        <span className="text-sm font-medium">Preparing document...</span>
      </div>
    );
  }

  switch (tab.viewMode) {
    case 'single':
      return <SinglePageView tab={tab} doc={doc} />;
    case 'two-page':
      return <TwoPageView tab={tab} doc={doc} />;
    case 'continuous':
    default:
      return <ContinuousViewer tab={tab} doc={doc} />;
  }
};
