import { RecentFile } from '../types';

// Check if running inside Tauri environment
export const isTauri = (): boolean => {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
};

// Database interface for both Tauri SQLite plugin and fallback
interface IDatabaseService {
  init(): Promise<void>;
  addRecentFile(file: Omit<RecentFile, 'id'>): Promise<void>;
  getRecentFiles(limit?: number): Promise<RecentFile[]>;
  updateRecentFilePage(path: string, page: number): Promise<void>;
  removeRecentFile(path: string): Promise<void>;
  getSetting<T>(key: string, defaultValue: T): Promise<T>;
  setSetting(key: string, value: unknown): Promise<void>;
}

class SQLiteDatabaseService implements IDatabaseService {
  private db: any = null;
  private initialized = false;

  async init(): Promise<void> {
    if (this.initialized) return;

    if (isTauri()) {
      try {
        const Database = (await import('@tauri-apps/plugin-sql')).default;
        this.db = await Database.load('sqlite:pdfreader.db');

        // Create tables if they do not exist
        await this.db.execute(`
          CREATE TABLE IF NOT EXISTS recent_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            last_opened INTEGER NOT NULL,
            last_page INTEGER NOT NULL DEFAULT 1,
            total_pages INTEGER NOT NULL DEFAULT 1
          );
        `);

        await this.db.execute(`
          CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT NOT NULL
          );
        `);

        this.initialized = true;
        return;
      } catch (err) {
        console.warn('Tauri SQL plugin failed to load, falling back to memory/local storage:', err);
      }
    }

    // Fallback if not Tauri or Tauri SQL failed
    this.initialized = true;
  }

  async addRecentFile(file: Omit<RecentFile, 'id'>): Promise<void> {
    await this.init();
    if (this.db) {
      try {
        await this.db.execute(
          `INSERT INTO recent_files (path, title, last_opened, last_page, total_pages)
           VALUES ($1, $2, $3, $4, $5)
           ON CONFLICT(path) DO UPDATE SET
             last_opened = excluded.last_opened,
             last_page = excluded.last_page,
             total_pages = excluded.total_pages;`,
          [file.path, file.title, file.lastOpened, file.lastPage, file.totalPages]
        );
        return;
      } catch (err) {
        console.error('Failed to add recent file in SQLite:', err);
      }
    }

    // Fallback store
    const recents = this.getFallbackRecentFiles();
    const filtered = recents.filter((f) => f.path !== file.path);
    filtered.unshift({ ...file, id: Date.now() });
    localStorage.setItem('aeropdf_recent_files', JSON.stringify(filtered.slice(0, 20)));
  }

  async getRecentFiles(limit = 10): Promise<RecentFile[]> {
    await this.init();
    if (this.db) {
      try {
        const rows: any[] = await this.db.select(
          `SELECT id, path, title, last_opened as lastOpened, last_page as lastPage, total_pages as totalPages
           FROM recent_files
           ORDER BY last_opened DESC
           LIMIT $1;`,
          [limit]
        );
        return rows;
      } catch (err) {
        console.error('Failed to get recent files from SQLite:', err);
      }
    }

    return this.getFallbackRecentFiles().slice(0, limit);
  }

  async updateRecentFilePage(path: string, page: number): Promise<void> {
    await this.init();
    if (this.db) {
      try {
        await this.db.execute(
          `UPDATE recent_files SET last_page = $1, last_opened = $2 WHERE path = $3;`,
          [page, Date.now(), path]
        );
        return;
      } catch (err) {
        console.error('Failed to update recent file page in SQLite:', err);
      }
    }

    const recents = this.getFallbackRecentFiles();
    const match = recents.find((f) => f.path === path);
    if (match) {
      match.lastPage = page;
      match.lastOpened = Date.now();
      localStorage.setItem('aeropdf_recent_files', JSON.stringify(recents));
    }
  }

  async removeRecentFile(path: string): Promise<void> {
    await this.init();
    if (this.db) {
      try {
        await this.db.execute(`DELETE FROM recent_files WHERE path = $1;`, [path]);
        return;
      } catch (err) {
        console.error('Failed to remove recent file from SQLite:', err);
      }
    }

    const recents = this.getFallbackRecentFiles().filter((f) => f.path !== path);
    localStorage.setItem('aeropdf_recent_files', JSON.stringify(recents));
  }

  async getSetting<T>(key: string, defaultValue: T): Promise<T> {
    await this.init();
    if (this.db) {
      try {
        const rows: any[] = await this.db.select(
          `SELECT value FROM user_settings WHERE key = $1;`,
          [key]
        );
        if (rows.length > 0) {
          return JSON.parse(rows[0].value) as T;
        }
      } catch (err) {
        console.error(`Failed to get setting ${key} from SQLite:`, err);
      }
    }

    const raw = localStorage.getItem(`aeropdf_setting_${key}`);
    if (raw) {
      try {
        return JSON.parse(raw) as T;
      } catch {
        return defaultValue;
      }
    }
    return defaultValue;
  }

  async setSetting(key: string, value: unknown): Promise<void> {
    await this.init();
    const strVal = JSON.stringify(value);
    if (this.db) {
      try {
        await this.db.execute(
          `INSERT INTO user_settings (key, value) VALUES ($1, $2)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value;`,
          [key, strVal]
        );
        return;
      } catch (err) {
        console.error(`Failed to set setting ${key} in SQLite:`, err);
      }
    }

    localStorage.setItem(`aeropdf_setting_${key}`, strVal);
  }

  private getFallbackRecentFiles(): RecentFile[] {
    try {
      const raw = localStorage.getItem('aeropdf_recent_files');
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }
}

export const dbService = new SQLiteDatabaseService();
