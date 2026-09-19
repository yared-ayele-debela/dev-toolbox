import React from 'react';
import { X, Keyboard } from 'lucide-react';

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const KeyboardShortcutsModal: React.FC<KeyboardShortcutsModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  const shortcuts = [
    {
      category: 'Tabs & Files',
      items: [
        { keys: ['Ctrl', 'O'], desc: 'Open PDF / Markdown file' },
        { keys: ['Ctrl', 'W'], desc: 'Close current tab' },
        { keys: ['Ctrl', 'Tab'], desc: 'Switch to next tab' },
        { keys: ['Ctrl', 'Shift', 'Tab'], desc: 'Switch to previous tab' },
      ],
    },
    {
      category: 'Page & Scroll Navigation',
      items: [
        { keys: ['↓', 'PageDown', 'j'], desc: 'Next page / scroll down' },
        { keys: ['↑', 'PageUp', 'k'], desc: 'Previous page / scroll up' },
        { keys: ['Home'], desc: 'Go to first page / top' },
        { keys: ['End'], desc: 'Go to last page / bottom' },
      ],
    },
    {
      category: 'Zoom & Typography',
      items: [
        { keys: ['Ctrl', '+'], desc: 'Zoom in / increase font' },
        { keys: ['Ctrl', '-'], desc: 'Zoom out / decrease font' },
        { keys: ['Ctrl', '0'], desc: 'Reset zoom (100%)' },
        { keys: ['w'], desc: 'Fit to width' },
        { keys: ['p'], desc: 'Fit to page' },
        { keys: ['r'], desc: 'Rotate clockwise (PDF)' },
      ],
    },
    {
      category: 'View Modes (1, 2, 3)',
      items: [
        { keys: ['1'], desc: 'PDF: Continuous / MD: Preview' },
        { keys: ['2'], desc: 'PDF: Single / MD: Split' },
        { keys: ['3'], desc: 'PDF: Two-Page / MD: Source' },
        { keys: ['?'], desc: 'Toggle shortcuts cheatsheet' },
      ],
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 select-none animate-in fade-in duration-150">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl max-w-xl w-full p-6 text-zinc-100 flex flex-col gap-5">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center gap-2">
            <Keyboard className="w-5 h-5 text-indigo-400" />
            <h2 className="text-base font-semibold">Keyboard Shortcuts</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[70vh] overflow-y-auto pr-1">
          {shortcuts.map((group) => (
            <div key={group.category} className="space-y-2">
              <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                {group.category}
              </h3>
              <div className="space-y-1.5">
                {group.items.map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between text-xs py-1">
                    <span className="text-zinc-300">{item.desc}</span>
                    <div className="flex items-center gap-1">
                      {item.keys.map((k, kidx) => (
                        <kbd
                          key={kidx}
                          className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-200 font-mono text-[11px] shadow-sm"
                        >
                          {k}
                        </kbd>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end pt-2 border-t border-zinc-800">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
