//! HTTP client for the OpenX backend (blocking, used from the TUI thread pool).
//!
//! All requests are sent with a 120-second timeout so the TUI never hangs
//! waiting for a long-running agent response.

use serde::Deserialize;

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

/// Response from `POST /run` (legacy endpoint, kept for compatibility).
#[derive(Debug, Deserialize)]
pub struct RunResponse {
    pub should_continue: bool,
    pub output: Option<serde_json::Value>,
    /// Set when the server handled a command but reported an error.
    pub error: Option<String>,
}

/// Response from `POST /chat`.
#[derive(Debug, Deserialize)]
pub struct ChatResponse {
    pub response: Option<String>,
    pub conversation_id: Option<String>,
    pub error: Option<String>,
}

/// One entry in the command palette (from `GET /tools`).
#[derive(Debug, Clone, Deserialize)]
pub struct ToolInfo {
    pub name: String,
    pub description: String,
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

pub struct BackendClient {
    base_url: String,
    client: reqwest::blocking::Client,
}

impl BackendClient {
    pub fn new(base_url: String) -> Self {
        let client = reqwest::blocking::Client::builder()
            .timeout(std::time::Duration::from_secs(120))
            .build()
            .expect("failed to build reqwest client");
        Self { base_url, client }
    }

    fn url(&self, path: &str) -> String {
        format!("{}/{}", self.base_url.trim_end_matches('/'), path.trim_start_matches('/'))
    }

    fn check(resp: reqwest::blocking::Response) -> Result<reqwest::blocking::Response, String> {
        if resp.status().is_success() {
            Ok(resp)
        } else {
            Err(format!("HTTP {}: {}", resp.status(), resp.text().unwrap_or_default()))
        }
    }

    /// Liveness probe (`GET /health`).
    pub fn health_check(&self) -> bool {
        self.client
            .get(&self.url("health"))
            .send()
            .map(|r| r.status().is_success())
            .unwrap_or(false)
    }

    /// Fetch the command palette entries (`GET /tools`).
    pub fn list_tools(&self) -> Result<Vec<ToolInfo>, String> {
        let resp = self.client.get(&self.url("tools")).send().map_err(|e| e.to_string())?;
        Self::check(resp)?.json::<Vec<ToolInfo>>().map_err(|e| e.to_string())
    }

    /// Send a message to the LangChain agent (`POST /chat`).
    pub fn chat(&self, message: &str, conversation_id: &str) -> Result<ChatResponse, String> {
        let body = serde_json::json!({ "message": message, "conversation_id": conversation_id });
        let resp = self
            .client
            .post(&self.url("chat"))
            .json(&body)
            .send()
            .map_err(|e| e.to_string())?;
        Self::check(resp)?.json::<ChatResponse>().map_err(|e| e.to_string())
    }

    /// Run a raw command string (`POST /run`). Kept for non-TUI callers.
    #[allow(dead_code)]
    pub fn run(&self, command: &str) -> Result<RunResponse, String> {
        let body = serde_json::json!({ "command": command });
        let resp = self
            .client
            .post(&self.url("run"))
            .json(&body)
            .send()
            .map_err(|e| e.to_string())?;
        Self::check(resp)?.json::<RunResponse>().map_err(|e| e.to_string())
    }
}
