use std::fs;
use std::path::Path;

#[tauri::command]
fn read_pdf_file(path: String) -> Result<Vec<u8>, String> {
    let p = Path::new(&path);
    if !p.exists() {
        return Err(format!("File does not exist: {}", path));
    }
    fs::read(p).map_err(|e| format!("Failed to read file '{}': {}", path, e))
}

#[tauri::command]
fn get_cli_args() -> Vec<String> {
    // Return all arguments after the binary name that point to existing files or end with .pdf, .md, .markdown
    std::env::args()
        .skip(1)
        .filter(|arg| {
            let lower = arg.to_lowercase();
            !arg.starts_with("--")
                && (lower.ends_with(".pdf")
                    || lower.ends_with(".md")
                    || lower.ends_with(".markdown")
                    || Path::new(arg).exists())
        })
        .collect()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_sql::Builder::default().build())
        .invoke_handler(tauri::generate_handler![read_pdf_file, get_cli_args])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
