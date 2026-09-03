#[tauri::command]
fn close_app(app: tauri::AppHandle) {
    app.exit(0);
}

#[tauri::command]
fn start_window_drag(window: tauri::Window) -> Result<(), String> {
    if window.is_fullscreen().map_err(|error| error.to_string())? {
        window.set_fullscreen(false).map_err(|error| error.to_string())?;
    }
    window.start_dragging().map_err(|error| error.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![close_app, start_window_drag])
        .run(tauri::generate_context!())
        .expect("error while running DruMaster");
}
