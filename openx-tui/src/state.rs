//! App state: chat, input, command palette, streaming.

use serde::{Deserialize, Serialize};
use std::time::SystemTime;

/// Chat message role.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum MessageRole {
    User,
    OpenX,
    System,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Message {
    pub role: MessageRole,
    pub content: String,
    pub timestamp: SystemTime,
}

impl Message {
    pub fn user(content: String) -> Self {
        Self { role: MessageRole::User, content, timestamp: SystemTime::now() }
    }
    pub fn openx(content: String) -> Self {
        Self { role: MessageRole::OpenX, content, timestamp: SystemTime::now() }
    }
    pub fn system(content: String) -> Self {
        Self { role: MessageRole::System, content, timestamp: SystemTime::now() }
    }
}

/// Chat: messages + scroll + streaming buffer.
#[derive(Clone, Debug, Default)]
pub struct ChatState {
    pub messages: Vec<Message>,
    pub scroll: usize,
    pub streaming_content: String,
}

/// One command in the registry (from backend).
#[derive(Clone, Debug)]
pub struct CommandEntry {
    pub name: String,
    pub description: String,
}

/// Command palette: visible, query after "/", filtered list, selection index.
#[derive(Clone, Debug, Default)]
pub struct PaletteState {
    pub visible: bool,
    pub query: String,
    /// All commands from backend.
    pub commands: Vec<CommandEntry>,
    /// Indices into commands that match current query (fuzzy).
    pub filtered: Vec<usize>,
    pub selected_index: usize,
}

impl PaletteState {
    pub fn selected_command(&self) -> Option<&CommandEntry> {
        self.filtered.get(self.selected_index).and_then(|&i| self.commands.get(i))
    }
}

/// Global app state (single-panel assistant).
#[derive(Clone, Debug, Default)]
pub struct AppState {
    pub chat: ChatState,
    pub input_buffer: String,
    pub input_cursor: usize,
    pub history: Vec<String>,
    pub history_index: usize,
    pub palette: PaletteState,
    pub loading: bool,
    /// When true (or input_buffer is non-empty), bare-key shortcuts are
    /// suppressed and characters go straight to the input buffer.
    pub input_focused: bool,
}

impl AppState {
    pub fn input_buffer(&self) -> &str {
        self.input_buffer.as_str()
    }
    pub fn input_cursor(&self) -> usize {
        self.input_cursor
    }
}
