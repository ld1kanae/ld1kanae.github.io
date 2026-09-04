use serde::Serialize;
use std::{
    fs::File,
    io::copy,
    path::PathBuf,
    process::Command,
};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

const RELEASE_API: &str = "https://api.github.com/repos/ld1kanae/ld1kanae.github.io/releases/tags/windows-latest";
const TRUSTED_DOWNLOAD_PREFIX: &str = "https://github.com/ld1kanae/ld1kanae.github.io/releases/download/windows-latest/";

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct UpdateInfo {
    current_build: u64,
    latest_build: u64,
    update_available: bool,
    download_url: Option<String>,
    asset_name: Option<String>,
}

fn current_build() -> u64 {
    option_env!("GITHUB_RUN_NUMBER")
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(0)
}

fn parse_main_build_number(name: &str) -> Option<u64> {
    if !name.starts_with("DruMaster-Windows-") || !name.ends_with("-Setup.exe") {
        return None;
    }
    let parts: Vec<&str> = name.split('-').collect();
    if parts.len() != 5 {
        return None;
    }
    let build = parts.get(2)?.parse::<u64>().ok()?;
    let short_sha = *parts.get(3)?;
    if short_sha.len() != 7 || !short_sha.chars().all(|c| c.is_ascii_hexdigit()) {
        return None;
    }
    Some(build)
}

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

#[tauri::command]
fn toggle_window_maximize(window: tauri::Window) -> Result<(), String> {
    if window.is_fullscreen().map_err(|error| error.to_string())? {
        window.set_fullscreen(false).map_err(|error| error.to_string())?;
    }
    if window.is_maximized().map_err(|error| error.to_string())? {
        window.unmaximize().map_err(|error| error.to_string())
    } else {
        window.maximize().map_err(|error| error.to_string())
    }
}

#[tauri::command]
async fn check_for_update() -> Result<UpdateInfo, String> {
    tauri::async_runtime::spawn_blocking(|| {
        let client = reqwest::blocking::Client::builder()
            .user_agent("DruMaster-Updater")
            .build()
            .map_err(|error| error.to_string())?;
        let response = client
            .get(RELEASE_API)
            .send()
            .and_then(|response| response.error_for_status())
            .map_err(|error| format!("update check failed: {error}"))?;
        let release: serde_json::Value = response
            .json()
            .map_err(|error| format!("invalid release response: {error}"))?;

        let mut latest_build = 0_u64;
        let mut latest_url = None;
        let mut latest_name = None;

        if let Some(assets) = release.get("assets").and_then(|value| value.as_array()) {
            for asset in assets {
                let Some(name) = asset.get("name").and_then(|value| value.as_str()) else { continue };
                let Some(build) = parse_main_build_number(name) else { continue };
                let Some(url) = asset.get("browser_download_url").and_then(|value| value.as_str()) else { continue };
                if !url.starts_with(TRUSTED_DOWNLOAD_PREFIX) {
                    continue;
                }
                if build > latest_build {
                    latest_build = build;
                    latest_url = Some(url.to_string());
                    latest_name = Some(name.to_string());
                }
            }
        }

        let current = current_build();
        Ok(UpdateInfo {
            current_build: current,
            latest_build,
            update_available: latest_build > current && latest_url.is_some(),
            download_url: latest_url,
            asset_name: latest_name,
        })
    })
    .await
    .map_err(|error| error.to_string())?
}

#[tauri::command]
async fn install_update(app: tauri::AppHandle, url: String, asset_name: String) -> Result<(), String> {
    if !url.starts_with(TRUSTED_DOWNLOAD_PREFIX) {
        return Err("untrusted update URL".into());
    }
    if parse_main_build_number(&asset_name).is_none() {
        return Err("invalid update asset".into());
    }

    let current_exe = std::env::current_exe().map_err(|error| error.to_string())?;
    let installer_path = std::env::temp_dir().join(&asset_name);
    let helper_path = std::env::temp_dir().join(format!("drumaster-update-{}.cmd", std::process::id()));
    let download_url = url.clone();
    let download_target = installer_path.clone();

    tauri::async_runtime::spawn_blocking(move || -> Result<(), String> {
        let client = reqwest::blocking::Client::builder()
            .user_agent("DruMaster-Updater")
            .build()
            .map_err(|error| error.to_string())?;
        let mut response = client
            .get(&download_url)
            .send()
            .and_then(|response| response.error_for_status())
            .map_err(|error| format!("update download failed: {error}"))?;
        let mut output = File::create(&download_target).map_err(|error| error.to_string())?;
        copy(&mut response, &mut output).map_err(|error| error.to_string())?;
        Ok(())
    })
    .await
    .map_err(|error| error.to_string())??;

    write_update_helper(&helper_path, &installer_path, &current_exe)?;
    launch_update_helper(&helper_path)?;
    app.exit(0);
    Ok(())
}

fn write_update_helper(helper: &PathBuf, installer: &PathBuf, current_exe: &PathBuf) -> Result<(), String> {
    let script = format!(
        "@echo off\r\ntimeout /t 2 /nobreak >nul\r\nstart /wait \"\" \"{}\" /S\r\nif exist \"{}\" start \"\" \"{}\"\r\ndel \"%~f0\"\r\n",
        installer.display(),
        current_exe.display(),
        current_exe.display()
    );
    std::fs::write(helper, script).map_err(|error| error.to_string())
}

fn launch_update_helper(helper: &PathBuf) -> Result<(), String> {
    let mut command = Command::new("cmd.exe");
    command.arg("/C").arg(helper);
    #[cfg(target_os = "windows")]
    command.creation_flags(0x00000008 | 0x00000200);
    command.spawn().map_err(|error| error.to_string())?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            close_app,
            start_window_drag,
            toggle_window_maximize,
            check_for_update,
            install_update
        ])
        .run(tauri::generate_context!())
        .expect("error while running DruMaster");
}
