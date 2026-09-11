import { Marked } from 'marked';
import DOMPurify from 'dompurify';
import Prism from 'prismjs';

// Import common Prism syntax highlight grammars
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-jsx';
import 'prismjs/components/prism-tsx';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-markdown';
import 'prismjs/components/prism-rust';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-yaml';
import 'prismjs/components/prism-sql';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-c';
import 'prismjs/components/prism-cpp';
import 'prismjs/components/prism-go';
import 'prismjs/components/prism-toml';
import 'prismjs/components/prism-docker';

import { MarkdownHeading } from '../types';

export interface MarkdownStats {
  wordCount: number;
  charCount: number;
  lineCount: number;
  readingTimeMinutes: number;
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

class MarkdownService {
  /**
   * Calculates statistics for a markdown document.
   */
  calculateStats(markdownText: string): MarkdownStats {
    const trimmed = markdownText.trim();
    if (!trimmed) {
      return { wordCount: 0, charCount: 0, lineCount: 0, readingTimeMinutes: 0 };
    }
    const words = trimmed.split(/\s+/).filter(Boolean);
    const wordCount = words.length;
    const charCount = markdownText.length;
    const lineCount = markdownText.split('\n').length;
    const readingTimeMinutes = Math.max(1, Math.ceil(wordCount / 200));

    return {
      wordCount,
      charCount,
      lineCount,
      readingTimeMinutes,
    };
  }

  /**
   * Extracts outline / table of contents headings from markdown text.
   */
  extractHeadings(markdownText: string): MarkdownHeading[] {
    const slugCounts = new Map<string, number>();
    const headings: MarkdownHeading[] = [];
    const lines = markdownText.split('\n');

    let inCodeBlock = false;

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('```') || trimmed.startsWith('~~~')) {
        inCodeBlock = !inCodeBlock;
        continue;
      }
      if (inCodeBlock) continue;

      const match = line.match(/^(#{1,6})\s+(.+)$/);
      if (match) {
        const level = match[1].length;
        const rawTitle = match[2].trim().replace(/[#*`_~]/g, '');
        let slug = rawTitle
          .toLowerCase()
          .replace(/[^\w\s-]/g, '')
          .trim()
          .replace(/\s+/g, '-');
        if (!slug) slug = 'section';

        const count = slugCounts.get(slug) || 0;
        slugCounts.set(slug, count + 1);
        const id = count === 0 ? `heading-${slug}` : `heading-${slug}-${count}`;

        headings.push({
          id,
          level,
          text: rawTitle,
        });
      }
    }

    return headings;
  }

  /**
   * Renders Markdown text to sanitized HTML with syntax highlighting,
   * heading IDs for TOC navigation, and interactive code copy buttons.
   */
  renderToHtml(markdownText: string): string {
    const slugCounts = new Map<string, number>();

    const markedInstance = new Marked({
      gfm: true,
      breaks: true,
      renderer: {
        code({ text, lang }: { text: string; lang?: string }) {
          const rawLang = (lang || '').trim().toLowerCase();
          const language = rawLang.split(/\s+/)[0] || 'text';

          let highlighted = '';
          if (language && Prism.languages[language]) {
            try {
              highlighted = Prism.highlight(text, Prism.languages[language], language);
            } catch {
              highlighted = escapeHtml(text);
            }
          } else {
            highlighted = escapeHtml(text);
          }

          const encoded = encodeURIComponent(text);

          return `
            <div class="code-block-wrapper group relative my-4 rounded-xl bg-zinc-900/90 border border-zinc-800 shadow-xl overflow-hidden font-mono">
              <div class="flex items-center justify-between px-3.5 py-1.5 bg-zinc-950/80 border-b border-zinc-800/80 text-[11px] text-zinc-400 select-none">
                <span class="font-semibold text-zinc-300 tracking-wider uppercase">${language}</span>
                <button
                  type="button"
                  class="markdown-copy-code-btn inline-flex items-center gap-1 px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-zinc-100 transition-colors cursor-pointer text-[11px]"
                  data-code="${encoded}"
                  title="Copy code"
                >
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                  </svg>
                  <span>Copy</span>
                </button>
              </div>
              <pre class="p-4 overflow-x-auto text-[13px] leading-relaxed text-zinc-200"><code>${highlighted}</code></pre>
            </div>
          `;
        },

        heading({ tokens, depth }: { tokens: any[]; depth: number }) {
          const rawText = tokens.map((t: any) => t.text || t.raw || '').join('');
          const cleanText = rawText.replace(/[#*`_~]/g, '').trim();
          let slug = cleanText
            .toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .trim()
            .replace(/\s+/g, '-');
          if (!slug) slug = 'section';

          const count = slugCounts.get(slug) || 0;
          slugCounts.set(slug, count + 1);
          const id = count === 0 ? `heading-${slug}` : `heading-${slug}-${count}`;

          const innerHtml = this.parser.parseInline(tokens);

          return `<h${depth} id="${id}" class="group scroll-mt-6">${innerHtml}<a href="#${id}" class="heading-anchor opacity-0 group-hover:opacity-100 ml-2 text-indigo-400/60 hover:text-indigo-400 transition-opacity font-normal text-sm" aria-label="Direct link to heading">#</a></h${depth}>`;
        },

        blockquote({ tokens }: { tokens: any[] }) {
          const body = this.parser.parse(tokens);
          return `<blockquote class="border-l-4 border-indigo-500 bg-indigo-950/20 px-4 py-2 my-4 rounded-r-lg text-zinc-300 italic">${body}</blockquote>`;
        },

        link({ href, title, tokens }: { href: string; title?: string | null; tokens: any[] }) {
          const text = this.parser.parseInline(tokens);
          const titleAttr = title ? ` title="${escapeHtml(title)}"` : '';
          return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer"${titleAttr} class="text-indigo-400 underline decoration-indigo-500/40 underline-offset-2 hover:text-indigo-300 hover:decoration-indigo-400 transition-colors">${text}</a>`;
        },
      },
    });

    const rawHtml = markedInstance.parse(markdownText) as string;

    // Sanitize with DOMPurify while keeping attributes needed for code copy and anchors
    return DOMPurify.sanitize(rawHtml, {
      ADD_TAGS: ['button', 'svg', 'path'],
      ADD_ATTR: ['target', 'rel', 'data-code', 'viewBox', 'fill', 'stroke', 'stroke-linecap', 'stroke-linejoin', 'stroke-width', 'd'],
    });
  }
}

export const markdownService = new MarkdownService();
