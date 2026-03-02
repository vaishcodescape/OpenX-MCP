//! Global app state container and action dispatcher.

use std::sync::{mpsc, Arc};
use std::thread;

use crate::actions::Action;
use crate::backend::{BackendClient, ToolInfo};
use crate::commands::update_palette_filter;
use crate::git;
use crate::services::normalize_slash_command;
use crate::state::{CommandEntry, Message};

/// Result of a completed background HTTP call.
pub enum BackendResult {
    Chat { text: String },
}

pub struct App {
    pub state: crate::state::AppState,
    pub should_quit: bool,
    /// Spinner animation counter (incremented each tick).
    pub tick: usize,
    /// Current git branch (read once at startup).
    pub git_branch: String,
    /// Whether the backend answered the health probe.
    pub connected: bool,
    client: Arc<BackendClient>,
    result_rx: mpsc::Receiver<BackendResult>,
    result_tx: mpsc::Sender<BackendResult>,
}

impl App {
    pub fn new(client: BackendClient) -> Self {
        let (result_tx, result_rx) = mpsc::channel();
        Self {
            state: Default::default(),
            should_quit: false,
            tick: 0,
            git_branch: git::git_branch(),
            connected: false,
            client: Arc::new(client),
            result_rx,
            result_tx,
        }
    }

    /// `true` when the input field has focus (buffer is non-empty or explicitly focused).
    pub fn input_has_focus(&self) -> bool {
        self.state.input_focused || !self.state.input_buffer.is_empty()
    }

    /// Estimate total display-line count across all chat messages.
    fn chat_total_lines(messages: &[Message], gap: bool) -> usize {
        messages
            .iter()
            .map(|m| m.content.lines().count().max(1) + usize::from(gap))
            .sum()
    }

    /// Initialise the command palette and check backend connectivity.
    pub fn bootstrap(&mut self) {
        self.connected = self.client.health_check();
        self.state.chat.messages.push(Message::system(
            "Welcome to OpenX. Type what you need or use / for shortcuts.".into(),
        ));

        // Built-in commands (always present, even if the backend is down).
        let builtins: Vec<CommandEntry> = [
            ("/help",           "Show help and available commands"),
            ("/tools",          "List all available MCP tools"),
            ("/schema",         "Show tool schema / parameters"),
            ("/call",           "Call a tool directly"),
            ("/analyze",        "Analyze a repository"),
            ("/repos",          "List repositories"),
            ("/prs",            "List pull requests"),
            ("/pr",             "Get pull request details"),
            ("/issues",         "List issues in a repo"),
            ("/issue",          "Get issue details"),
            ("/newissue",       "Create a new issue"),
            ("/commentissue",   "Comment on an issue"),
            ("/closeissue",     "Close an issue"),
            ("/comment",        "Comment on a pull request"),
            ("/merge",          "Merge a pull request"),
            ("/readme",         "Get or update README"),
            ("/workflows",      "List CI/CD workflows"),
            ("/trigger",        "Trigger a workflow run"),
            ("/runs",           "List workflow runs"),
            ("/run",            "Get workflow run details"),
            ("/failing",        "Get PRs with failing CI"),
            ("/heal",           "Auto-heal failing PR (analyze, fix, apply, rerun CI)"),
            ("/logs",           "Get CI logs for a run"),
            ("/analyze-failure","Analyze a CI failure"),
            ("/context",        "Locate relevant code context"),
            ("/patch",          "Generate a fix patch"),
            ("/apply",          "Apply a fix to a pull request"),
            ("/rerun",          "Re-run CI for a workflow"),
            ("/chat",           "Chat with the AI agent (agentic reasoning)"),
            ("/index",          "Index a repo into the RAG knowledge base"),
            ("/reset",          "Clear agent conversation memory"),
        ]
        .iter()
        .map(|&(name, desc)| CommandEntry { name: name.into(), description: desc.into() })
        .collect();

        self.state.palette.commands = builtins;

        // Merge backend tools on top if available.
        if let Ok(tools) = self.client.list_tools() {
            let existing: std::collections::HashSet<&str> =
                self.state.palette.commands.iter().map(|c| c.name.as_str()).collect();
            let extra: Vec<CommandEntry> = tools
                .into_iter()
                .filter(|t: &ToolInfo| !existing.contains(t.name.as_str()))
                .map(|t| CommandEntry { name: t.name, description: t.description })
                .collect();
            self.state.palette.commands.extend(extra);
        }

        update_palette_filter(&mut self.state.palette);
    }

    /// Poll for completed background HTTP results. Call once per tick.
    pub fn poll_results(&mut self) {
        while let Ok(result) = self.result_rx.try_recv() {
            self.state.loading = false;
            let BackendResult::Chat { text } = result;
            self.state.chat.messages.push(Message::openx(text));
            // Auto-scroll to the bottom on every new message.
            let total = Self::chat_total_lines(&self.state.chat.messages, true);
            self.state.chat.scroll = total.saturating_sub(10);
        }
    }

    pub fn dispatch(&mut self, action: Action) {
        match action {
            Action::Quit => self.should_quit = true,

            Action::UnfocusInput => self.state.input_focused = false,

            Action::Char(c) => {
                self.state.input_focused = true;
                let pos = self.state.input_cursor.min(self.state.input_buffer.len());
                self.state.input_buffer.insert(pos, c);
                self.state.input_cursor = pos + c.len_utf8();
                if self.state.palette.visible {
                    self.sync_palette_query();
                }
            }

            Action::Backspace => {
                let cursor = self.state.input_cursor;
                let min_cursor = if self.state.palette.visible { 1 } else { 0 };
                if cursor > min_cursor {
                    let prev = self.state.input_buffer[..cursor]
                        .char_indices()
                        .next_back()
                        .map(|(idx, _)| idx)
                        .unwrap_or(0);
                    if prev >= min_cursor {
                        self.state.input_buffer.remove(prev);
                        self.state.input_cursor = prev;
                    }
                    if self.state.palette.visible {
                        self.sync_palette_query();
                    }
                }
            }

            Action::ClearInput => {
                self.state.input_buffer.clear();
                self.state.input_cursor = 0;
                self.state.input_focused = false;
                self.state.palette.visible = false;
            }

            Action::Submit => self.submit_input(),

            Action::CancelStreaming => {
                self.state.loading = false;
                self.state.chat.streaming_content.clear();
            }

            Action::ChatScrollPageUp   => { self.state.chat.scroll = self.state.chat.scroll.saturating_sub(10); }
            Action::ChatScrollPageDown => { self.state.chat.scroll = self.state.chat.scroll.saturating_add(10); }
            Action::ChatScrollTop      => self.state.chat.scroll = 0,
            Action::ChatScrollBottom   => {
                let total = Self::chat_total_lines(&self.state.chat.messages, false);
                self.state.chat.scroll = total.saturating_sub(20);
            }

            Action::HistoryUp   => self.history_up(),
            Action::HistoryDown => self.history_down(),

            Action::PaletteShow => {
                self.state.palette.visible = true;
                self.state.palette.query.clear();
                self.state.input_buffer = "/".into();
                self.state.input_cursor = 1;
                update_palette_filter(&mut self.state.palette);
            }
            Action::PaletteHide => self.state.palette.visible = false,
            Action::PaletteUp   => self.palette_move(-1),
            Action::PaletteDown => self.palette_move(1),
            Action::PaletteSelect => {
                if let Some(cmd) = self.state.palette.selected_command() {
                    self.state.input_buffer = cmd.name.clone();
                    self.state.input_cursor = self.state.input_buffer.len();
                    self.state.palette.visible = false;
                }
            }
        }
    }

    // ── Private helpers ───────────────────────────────────────────────────

    fn sync_palette_query(&mut self) {
        self.state.palette.query = self.state.input_buffer.get(1..).unwrap_or("").to_string();
        update_palette_filter(&mut self.state.palette);
    }

    fn palette_move(&mut self, delta: isize) {
        let len = self.state.palette.filtered.len();
        if len == 0 {
            return;
        }
        let cur = self.state.palette.selected_index as isize;
        self.state.palette.selected_index = ((cur + delta).rem_euclid(len as isize)) as usize;
    }

    fn submit_input(&mut self) {
        let raw = self.state.input_buffer.trim().to_string();
        if raw.is_empty() {
            return;
        }

        // While the palette is open, Enter selects the highlighted command.
        if self.state.palette.visible && !self.state.palette.filtered.is_empty() {
            if let Some(cmd) = self.state.palette.selected_command() {
                self.state.input_buffer = cmd.name.clone();
                self.state.input_cursor = self.state.input_buffer.len();
                self.state.palette.visible = false;
            }
            return;
        }

        // Don't queue a second request while one is in-flight.
        if self.state.loading {
            return;
        }

        // Clear the input and close the palette.
        self.state.palette.visible = false;
        self.state.input_buffer.clear();
        self.state.input_cursor = 0;
        self.state.input_focused = false;

        // Deduplicate history.
        let command = normalize_slash_command(&raw);
        if self.state.history.last().map(|s| s.as_str()) != Some(&raw) {
            self.state.history.push(raw);
        }
        self.state.history_index = self.state.history.len();

        self.state.chat.messages.push(Message::user(command.clone()));

        // Handle quit locally for an instant response.
        if matches!(command.as_str(), "quit" | "exit") {
            self.state.chat.messages.push(Message::openx("Goodbye.".into()));
            self.should_quit = true;
            return;
        }

        self.state.loading = true;
        self.state.chat.streaming_content.clear();

        // Strip a leading "chat " prefix so /chat <msg> and <msg> both work.
        let message = command.strip_prefix("chat ").unwrap_or(&command).trim().to_string();

        let tx     = self.result_tx.clone();
        let client = Arc::clone(&self.client);
        thread::spawn(move || {
            let text = match client.chat(&message, "tui-default") {
                Ok(r)  => r.error.or(r.response).unwrap_or_else(|| "(no response)".into()),
                Err(e) => format!("Error: {e}"),
            };
            let _ = tx.send(BackendResult::Chat { text });
        });
    }

    fn history_up(&mut self) {
        if self.state.palette.visible || self.state.history.is_empty() || self.state.history_index == 0 {
            return;
        }
        self.state.history_index -= 1;
        self.state.input_buffer  = self.state.history[self.state.history_index].clone();
        self.state.input_cursor  = self.state.input_buffer.len();
    }

    fn history_down(&mut self) {
        if self.state.palette.visible {
            return;
        }
        let len = self.state.history.len();
        if self.state.history_index >= len {
            return;
        }
        self.state.history_index += 1;
        self.state.input_buffer = if self.state.history_index >= len {
            String::new()
        } else {
            self.state.history[self.state.history_index].clone()
        };
        self.state.input_cursor = self.state.input_buffer.len();
    }
}
