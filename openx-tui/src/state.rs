//! Application state types.
//!
//! All fields are `pub` so UI and `App` can read them directly.
//! Mutation goes through [`crate::app::App::dispatch`].

use serde::{Deserialize, Serialize};
use std::time::SystemTime;

// ---------------------------------------------------------------------------
// Message
// ---------------------------------------------------------------------------

/// Sender of a chat message.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum MessageRole {
    User,
    OpenX,
    System,
}

/// One message in the chat history.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Message {
    pub role: MessageRole,
    pub content: String,
    pub timestamp: SystemTime,
}

impl Message {
    pub fn user(content: String)   -> Self { Self { role: MessageRole::User,   content, timestamp: SystemTime::now() } }
    pub fn openx(content: String)  -> Self { Self { role: MessageRole::OpenX,  content, timestamp: SystemTime::now() } }
    pub fn system(content: String) -> Self { Self { role: MessageRole::System, content, timestamp: SystemTime::now() } }
}

// ---------------------------------------------------------------------------
// Command palette
// ---------------------------------------------------------------------------

/// One command registered in the palette (sourced from the backend or built-in).
#[derive(Clone, Debug)]
pub struct CommandEntry {
    pub name: String,
    pub description: String,
}

/// State for the `/`-triggered command palette overlay.
#[derive(Clone, Debug, Default)]
pub struct PaletteState {
    pub visible: bool,
    /// Text after the leading `/` — drives fuzzy filtering.
    pub query: String,
    /// Full command list (built-ins + backend tools merged at startup).
    pub commands: Vec<CommandEntry>,
    /// Indices into `commands` that match the current query (sorted by score).
    pub filtered: Vec<usize>,
    pub selected_index: usize,
}

impl PaletteState {
    /// Return the currently highlighted command, if any.
    pub fn selected_command(&self) -> Option<&CommandEntry> {
        self.filtered.get(self.selected_index).and_then(|&i| self.commands.get(i))
    }
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

/// Scrollable chat view and streaming buffer.
#[derive(Clone, Debug, Default)]
pub struct ChatState {
    pub messages: Vec<Message>,
    /// Vertical scroll offset (in content lines).
    pub scroll: usize,
    /// In-progress streaming text (cleared when the response completes).
    pub streaming_content: String,
}

// ---------------------------------------------------------------------------
// Global app state
// ---------------------------------------------------------------------------

/// Complete mutable state of the TUI application.
#[derive(Clone, Debug, Default)]
pub struct AppState {
    pub chat: ChatState,
    pub input_buffer: String,
    pub input_cursor: usize,
    /// Previous submitted inputs (oldest first).
    pub history: Vec<String>,
    /// Index into `history` while browsing up/down; `history.len()` = current draft.
    pub history_index: usize,
    pub palette: PaletteState,
    /// `true` while waiting for an agent response.
    pub loading: bool,
    /// `true` when the user has explicitly focused the input (suppresses vi-style shortcuts).
    pub input_focused: bool,
}

impl AppState {
    /// Borrow the input buffer as a `&str` (used by the UI renderer).
    pub fn input_buffer(&self) -> &str {
        &self.input_buffer
    }

    /// Return the current cursor byte-offset (used by the UI renderer).
    pub fn input_cursor(&self) -> usize {
        self.input_cursor
    }
}
