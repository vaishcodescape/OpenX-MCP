//! Global state container and action dispatch (minimal assistant).

use std::sync::{mpsc, Arc};
use std::thread;

use crate::actions::Action;
use crate::backend::{BackendClient, ToolInfo};
use crate::commands::update_palette_filter;
use crate::git;
use crate::services::normalize_slash_command;
use crate::state::{CommandEntry, Message};

/// Result of a background HTTP call (agent response).
pub enum BackendResult {
    Chat { text: String },
}

pub struct App {
    pub state: crate::state::AppState,
    client: Arc<BackendClient>,
    pub should_quit: bool,
    /// For spinner animation (incremented each tick).
    pub tick: usize,
    /// Current git branch (cached at startup).
    pub git_branch: String,
    /// Whether backend is reachable.
    pub connected: bool,
    /// Channel for receiving background HTTP results.
    result_rx: mpsc::Receiver<BackendResult>,
    result_tx: mpsc::Sender<BackendResult>,
}

impl App {
    pub fn new(client: BackendClient) -> Self {
        let (tx, rx) = mpsc::channel();
        Self {
            state: crate::state::AppState::default(),
            client: Arc::new(client),
            should_quit: false,
            tick: 0,
            git_branch: git::git_branch(),
            connected: false,
            result_rx: rx,
            result_tx: tx,
        }
    }

    /// Input has focus when the buffer is non-empty or explicitly focused.
    pub fn input_has_focus(&self) -> bool {
        self.state.input_focused || !self.state.input_buffer.is_empty()
    }

    /// Sync palette query from input buffer (everything after leading '/').
    fn sync_palette_query(&mut self) {
        self.state.palette.query = self.state.input_buffer.get(1..).unwrap_or("").to_string();
        update_palette_filter(&mut self.state.palette);
    }

    /// Estimated total line count for chat (for scroll-to-bottom). Uses content line count as proxy for display lines.
    fn estimated_chat_total_lines(include_gap_per_message: bool) -> impl Fn(&[Message]) -> usize {
        move |messages: &[Message]| {
            messages
                .iter()
                .map(|m| m.content.lines().count().max(1) + if include_gap_per_message { 1 } else { 0 })
                .sum()
        }
    }

    pub fn bootstrap(&mut self) {
        self.connected = self.client.health_check();
        self.state.chat.messages.push(Message::system(
            "Welcome to OpenX. Type what you need or use / for shortcuts.".to_string(),
        ));

        // Built-in commands (always available, even without backend).
        let builtins: Vec<CommandEntry> = vec![
            CommandEntry { name: "/help".into(), description: "Show help and available commands".into() },
            CommandEntry { name: "/tools".into(), description: "List all available MCP tools".into() },
            CommandEntry { name: "/schema".into(), description: "Show tool schema / parameters".into() },
            CommandEntry { name: "/call".into(), description: "Call a tool directly".into() },
            CommandEntry { name: "/analyze".into(), description: "Analyze a repository".into() },
            CommandEntry { name: "/repos".into(), description: "List repositories".into() },
            CommandEntry { name: "/prs".into(), description: "List pull requests".into() },
            CommandEntry { name: "/pr".into(), description: "Get pull request details".into() },
            CommandEntry { name: "/issues".into(), description: "List issues in a repo".into() },
            CommandEntry { name: "/issue".into(), description: "Get issue details".into() },
            CommandEntry { name: "/newissue".into(), description: "Create a new issue".into() },
            CommandEntry { name: "/commentissue".into(), description: "Comment on an issue".into() },
            CommandEntry { name: "/closeissue".into(), description: "Close an issue".into() },
            CommandEntry { name: "/comment".into(), description: "Comment on a pull request".into() },
            CommandEntry { name: "/merge".into(), description: "Merge a pull request".into() },
            CommandEntry { name: "/readme".into(), description: "Get or update README (use agent for update)".into() },
            CommandEntry { name: "/workflows".into(), description: "List CI/CD workflows".into() },
            CommandEntry { name: "/trigger".into(), description: "Trigger a workflow run".into() },
            CommandEntry { name: "/runs".into(), description: "List workflow runs".into() },
            CommandEntry { name: "/run".into(), description: "Get workflow run details".into() },
            CommandEntry { name: "/failing".into(), description: "Get PRs with failing CI".into() },
            CommandEntry { name: "/heal".into(), description: "Auto-heal failing PR (analyze, fix code, apply, rerun CI)".into() },
            CommandEntry { name: "/logs".into(), description: "Get CI logs for a run".into() },
            CommandEntry { name: "/analyze-failure".into(), description: "Analyze a CI failure".into() },
            CommandEntry { name: "/context".into(), description: "Locate relevant code context".into() },
            CommandEntry { name: "/patch".into(), description: "Generate a fix patch".into() },
            CommandEntry { name: "/apply".into(), description: "Apply a fix to a pull request".into() },
            CommandEntry { name: "/rerun".into(), description: "Re-run CI for a workflow".into() },
            CommandEntry { name: "/chat".into(), description: "Chat with the AI agent (agentic reasoning)".into() },
            CommandEntry { name: "/index".into(), description: "Index a repo into the RAG knowledge base".into() },
            CommandEntry { name: "/reset".into(), description: "Clear agent conversation memory".into() },
        ];
        self.state.palette.commands = builtins;

        // Merge backend tools on top if available.
        if let Ok(tools) = self.client.list_tools() {
            let extra: Vec<CommandEntry> = tools
                .into_iter()
                .filter(|t| {
                    !self.state.palette.commands.iter().any(|c| c.name == t.name)
                })
                .map(|t: ToolInfo| CommandEntry {
                    name: t.name,
                    description: t.description,
                })
                .collect();
            self.state.palette.commands.extend(extra);
        }
        update_palette_filter(&mut self.state.palette);
    }

    /// Poll for completed background HTTP results. Call each tick.
    pub fn poll_results(&mut self) {
        while let Ok(result) = self.result_rx.try_recv() {
            self.state.loading = false;
            match result {
                BackendResult::Chat { text } => {
                    self.state.chat.messages.push(Message::openx(text));
                }
            }
            // Auto-scroll to bottom on new message.
            let total_lines = Self::estimated_chat_total_lines(true)(&self.state.chat.messages);
            self.state.chat.scroll = total_lines.saturating_sub(10);
        }
    }

    pub fn dispatch(&mut self, action: Action) {
        match action {
            Action::Quit => self.should_quit = true,
            Action::UnfocusInput => {
                self.state.input_focused = false;
            }

            Action::Char(c) => {
                // Auto-focus when the user begins typing.
                self.state.input_focused = true;
                let pos = self.state.input_cursor.min(self.state.input_buffer.len());
                self.state.input_buffer.insert(pos, c);
                self.state.input_cursor = pos + c.len_utf8();
                if self.state.palette.visible {
                    self.sync_palette_query();
                }
            }
            Action::Backspace => {
                if self.state.palette.visible {
                    if self.state.input_cursor > 1 {
                        self.state.input_buffer.remove(self.state.input_cursor - 1);
                        self.state.input_cursor -= 1;
                        self.sync_palette_query();
                    }
                } else if self.state.input_cursor > 0 && self.state.input_cursor <= self.state.input_buffer.len() {
                    self.state.input_buffer.remove(self.state.input_cursor - 1);
                    self.state.input_cursor -= 1;
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

            Action::ChatScrollPageUp => {
                self.state.chat.scroll = self.state.chat.scroll.saturating_sub(10);
            }
            Action::ChatScrollPageDown => {
                self.state.chat.scroll = self.state.chat.scroll.saturating_add(10);
            }
            Action::ChatScrollTop => self.state.chat.scroll = 0,
            Action::ChatScrollBottom => {
                let total = Self::estimated_chat_total_lines(false)(&self.state.chat.messages);
                self.state.chat.scroll = total.saturating_sub(20);
            }

            Action::HistoryUp => self.history_up(),
            Action::HistoryDown => self.history_down(),

            Action::PaletteShow => {
                self.state.palette.visible = true;
                self.state.palette.query.clear();
                self.state.input_buffer = "/".to_string();
                self.state.input_cursor = 1;
                update_palette_filter(&mut self.state.palette);
            }
            Action::PaletteHide => {
                self.state.palette.visible = false;
            }
            Action::PaletteUp => {
                if !self.state.palette.filtered.is_empty() {
                    let len = self.state.palette.filtered.len();
                    self.state.palette.selected_index = (self.state.palette.selected_index + len - 1) % len;
                }
            }
            Action::PaletteDown => {
                if !self.state.palette.filtered.is_empty() {
                    let len = self.state.palette.filtered.len();
                    self.state.palette.selected_index = (self.state.palette.selected_index + 1) % len;
                }
            }
            Action::PaletteSelect => {
                if let Some(cmd) = self.state.palette.selected_command() {
                    self.state.input_buffer = cmd.name.clone();
                    self.state.input_cursor = self.state.input_buffer.len();
                    self.state.palette.visible = false;
                }
            }
        }
    }

    fn submit_input(&mut self) {
        let raw = self.state.input_buffer.trim().to_string();
        if raw.is_empty() {
            return;
        }

        if self.state.palette.visible && !self.state.palette.filtered.is_empty() {
            if let Some(cmd) = self.state.palette.selected_command() {
                self.state.input_buffer = cmd.name.clone();
                self.state.input_cursor = self.state.input_buffer.len();
                self.state.palette.visible = false;
            }
            return;
        }

        // Don't allow submitting while another request is in-flight.
        if self.state.loading {
            return;
        }

        self.state.palette.visible = false;
        self.state.input_buffer.clear();
        self.state.input_cursor = 0;
        self.state.input_focused = false;

        let command = normalize_slash_command(&raw);
        if self.state.history.last().as_deref() != Some(&raw) {
            self.state.history.push(raw);
        }
        self.state.history_index = self.state.history.len();

        self.state.chat.messages.push(Message::user(command.clone()));
        self.state.loading = true;
        self.state.chat.streaming_content.clear();

        // Quit/exit: handle locally for instant, Codex-like response.
        if command == "quit" || command == "exit" {
            self.state.loading = false;
            self.state.chat.messages.push(Message::openx("Goodbye.".to_string()));
            self.should_quit = true;
            return;
        }

        // All other input (free-form and slash commands) goes to the LLM agent.
        // The agent interprets intent and uses tools — e.g. /prs → list_prs, natural language → tools.
        let tx = self.result_tx.clone();
        let client = Arc::clone(&self.client);
        let message = command
            .strip_prefix("chat ")
            .unwrap_or(&command)
            .trim()
            .to_string();

        thread::spawn(move || {
            let result = client.chat(&message, "tui-default");
            let text = match result {
                Ok(r) => r.error.unwrap_or_else(|| {
                    r.response.unwrap_or_else(|| "(no response)".to_string())
                }),
                Err(e) => format!("Error: {}", e),
            };
            let _ = tx.send(BackendResult::Chat { text });
        });
    }

    fn history_up(&mut self) {
        if self.state.palette.visible {
            return;
        }
        if !self.state.history.is_empty() && self.state.history_index > 0 {
            self.state.history_index -= 1;
            self.state.input_buffer = self.state.history[self.state.history_index].clone();
            self.state.input_cursor = self.state.input_buffer.len();
        }
    }

    fn history_down(&mut self) {
        if self.state.palette.visible {
            return;
        }
        if self.state.history_index < self.state.history.len() {
            self.state.history_index += 1;
            self.state.input_buffer = if self.state.history_index >= self.state.history.len() {
                String::new()
            } else {
                self.state.history[self.state.history_index].clone()
            };
            self.state.input_cursor = self.state.input_buffer.len();
        }
    }
}
