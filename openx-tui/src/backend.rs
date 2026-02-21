//! HTTP client for the OpenX backend (POST /run, GET /tools).

use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct RunResponse {
    pub should_continue: bool,
    pub output: Option<serde_json::Value>,
}

/// Tool entry from GET /tools (name, description for command palette).
#[derive(Debug, Clone, Deserialize)]
pub struct ToolInfo {
    pub name: String,
    pub description: String,
}

pub struct BackendClient {
    base_url: String,
    client: reqwest::blocking::Client,
}

impl BackendClient {
    pub fn new(base_url: String) -> Self {
        let client = reqwest::blocking::Client::builder()
            .timeout(std::time::Duration::from_secs(120))
            .build()
            .expect("reqwest client");
        Self { base_url, client }
    }

    /// Run a command string (same as TUI input). Returns (should_continue, output).
    pub fn run(&self, command: &str) -> Result<RunResponse, String> {
        let url = format!("{}/run", self.base_url.trim_end_matches('/'));
        let body = serde_json::json!({ "command": command });
        let resp = self
            .client
            .post(&url)
            .json(&body)
            .send()
            .map_err(|e| e.to_string())?;
        if !resp.status().is_success() {
            return Err(format!("HTTP {}: {}", resp.status(), resp.text().unwrap_or_default()));
        }
        let run: RunResponse = resp.json().map_err(|e| e.to_string())?;
        Ok(run)
    }

    /// Fetch command palette entries from backend (GET /tools).
    pub fn list_tools(&self) -> Result<Vec<ToolInfo>, String> {
        let url = format!("{}/tools", self.base_url.trim_end_matches('/'));
        let resp = self.client.get(&url).send().map_err(|e| e.to_string())?;
        if !resp.status().is_success() {
            return Err(format!("HTTP {}: {}", resp.status(), resp.text().unwrap_or_default()));
        }
        let tools: Vec<ToolInfo> = resp.json().map_err(|e| e.to_string())?;
        Ok(tools)
    }

    pub fn health_check(&self) -> bool {
        let url = format!("{}/health", self.base_url.trim_end_matches('/'));
        self.client.get(&url).send().map(|r| r.status().is_success()).unwrap_or(false)
    }
}
