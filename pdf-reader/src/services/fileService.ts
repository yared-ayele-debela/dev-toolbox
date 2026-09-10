import { isTauri } from '../db/database';

export interface LoadedFilePayload {
  name: string;
  path?: string;
  data: Uint8Array;
}

export class FileService {
  /**
   * Prompts the user to pick a document (PDF or Markdown).
   * In Tauri, uses native dialog. In browser, uses file input element.
   */
  async openFileDialog(): Promise<LoadedFilePayload | null> {
    if (isTauri()) {
      try {
        const { open } = await import('@tauri-apps/plugin-dialog');
        const selected = await open({
          multiple: false,
          directory: false,
          filters: [
            {
              name: 'Supported Documents (*.pdf, *.md, *.markdown)',
              extensions: ['pdf', 'md', 'markdown'],
            },
            {
              name: 'PDF Documents (*.pdf)',
              extensions: ['pdf'],
            },
            {
              name: 'Markdown Documents (*.md, *.markdown)',
              extensions: ['md', 'markdown'],
            },
            {
              name: 'All Files (*.*)',
              extensions: ['*'],
            },
          ],
        });

        if (!selected) return null;
        const filePath = typeof selected === 'string' ? selected : selected;
        return await this.readFileFromPath(filePath);
      } catch (err) {
        console.warn('Tauri open dialog failed, falling back to HTML file input:', err);
      }
    }

    return this.openBrowserFileInput();
  }

  /**
   * Reads a PDF file by path via Tauri command or local filesystem.
   */
  async readFileFromPath(path: string): Promise<LoadedFilePayload> {
    if (isTauri()) {
      const { invoke } = await import('@tauri-apps/api/core');
      const bytes = await invoke<number[]>('read_pdf_file', { path });
      const data = new Uint8Array(bytes);
      const name = path.split('/').pop() || path.split('\\').pop() || 'document.pdf';
      return { name, path, data };
    }

    throw new Error('Reading directly by path is only supported in Tauri desktop mode.');
  }

  /**
   * Reads an HTML5 File object (e.g. from Drag & Drop or input).
   */
  async readFileFromFileObject(file: File): Promise<LoadedFilePayload> {
    const buffer = await file.arrayBuffer();
    return {
      name: file.name,
      path: (file as any).path || undefined,
      data: new Uint8Array(buffer),
    };
  }

  /**
   * Gets initial CLI arguments passed when launching the app (e.g. `pdfreader sample.pdf`).
   */
  async getCliArguments(): Promise<string[]> {
    if (isTauri()) {
      try {
        const { invoke } = await import('@tauri-apps/api/core');
        return await invoke<string[]>('get_cli_args');
      } catch (err) {
        console.error('Failed to get CLI args:', err);
      }
    }
    return [];
  }

  /**
   * Fallback for browser testing when Tauri native dialog is not active.
   */
  private openBrowserFileInput(): Promise<LoadedFilePayload | null> {
    return new Promise((resolve) => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.pdf,application/pdf,.md,.markdown,text/markdown,text/plain';
      input.style.display = 'none';

      input.onchange = async () => {
        const file = input.files?.[0];
        if (!file) {
          resolve(null);
          return;
        }
        try {
          const loaded = await this.readFileFromFileObject(file);
          resolve(loaded);
        } catch (err) {
          console.error('Failed to read file from input:', err);
          resolve(null);
        } finally {
          document.body.removeChild(input);
        }
      };

      input.oncancel = () => {
        resolve(null);
        document.body.removeChild(input);
      };

      document.body.appendChild(input);
      input.click();
    });
  }

  isMarkdownFile(fileNameOrPath: string): boolean {
    const lower = fileNameOrPath.toLowerCase();
    return lower.endsWith('.md') || lower.endsWith('.markdown');
  }

  isPdfFile(fileNameOrPath: string): boolean {
    return fileNameOrPath.toLowerCase().endsWith('.pdf');
  }

  isSupportedFile(fileNameOrPath: string): boolean {
    return this.isPdfFile(fileNameOrPath) || this.isMarkdownFile(fileNameOrPath);
  }
}

export const fileService = new FileService();
