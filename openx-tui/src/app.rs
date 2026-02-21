//! Global state container and action dispatch (minimal assistant).

use crate::actions::Action;
use crate::backend::{BackendClient, ToolInfo};
use crate::commands::update_palette_filter;
use crate::services::{format_output, normalize_slash_command};
use crate::state::{CommandEntry, Message};

pub struct App {
    pub state: crate::state::AppState,
    client: BackendClient,
    pub should_quit: bool,
    /// For spinner animation (incremented each tick).
    pub tick: usize,
}

impl App {
    pub fn new(client: BackendClient) -> Self {
        Self {
            state: crate::state::AppState::default(),
            client,
            should_quit: false,
            tick: 0,
        }
    }

    pub fn bootstrap(&mut self) {
        let _connected = self.client.health_check();
        self.state.chat.messages.push(Message::system(
            "OpenX. Type a command and press Enter. Use / for command palette.".to_string(),
        ));
        if let Ok(tools) = self.client.list_tools() {
            self.state.palette.commands = tools
                .into_iter()
                .map(|t: ToolInfo| CommandEntry {
                    name: t.name,
                    description: t.description,
                })
                .collect();
            update_palette_filter(&mut self.state.palette);
        }
    }

    pub fn dispatch(&mut self, action: Action) {
        match action {
            Action::Quit => self.should_quit = true,

            Action::Char(c) => {
                let pos = self.state.input_cursor.min(self.state.input_buffer.len());
                self.state.input_buffer.insert(pos, c);
                self.state.input_cursor = pos + c.len_utf8();
                if self.state.palette.visible {
                    self.state.palette.query = self.state.input_buffer.get(1..).unwrap_or("").to_string();
                    update_palette_filter(&mut self.state.palette);
                }
            }
            Action::Backspace => {
                if self.state.palette.visible {
                    if self.state.input_cursor > 1 {
                        self.state.input_buffer.remove(self.state.input_cursor - 1);
                        self.state.input_cursor -= 1;
                        self.state.palette.query = self.state.input_buffer.get(1..).unwrap_or("").to_string();
                        update_palette_filter(&mut self.state.palette);
                    }
                } else if self.state.input_cursor > 0 && self.state.input_cursor <= self.state.input_buffer.len() {
                    self.state.input_buffer.remove(self.state.input_cursor - 1);
                    self.state.input_cursor -= 1;
                }
            }
            Action::ClearInput => {
                self.state.input_buffer.clear();
                self.state.input_cursor = 0;
                self.state.palette.visible = false;
            }
            Action::Submit => self.submit_input(),

            Action::CancelStreaming => {
                self.state.loading = false;
                self.state.chat.streaming_content.clear();
            }

            Action::ChatScrollUp => self.state.chat.scroll = self.state.chat.scroll.saturating_sub(1),
            Action::ChatScrollDown => self.state.chat.scroll = self.state.chat.scroll.saturating_add(1),
            Action::ChatScrollPageUp => {
                self.state.chat.scroll = self.state.chat.scroll.saturating_sub(10);
            }
            Action::ChatScrollPageDown => {
                self.state.chat.scroll = self.state.chat.scroll.saturating_add(10);
            }
            Action::ChatScrollTop => self.state.chat.scroll = 0,
            Action::ChatScrollBottom => {
                let total = self
                    .state
                    .chat
                    .messages
                    .iter()
                    .map(|m| m.content.lines().count().max(1))
                    .sum::<usize>();
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

        self.state.palette.visible = false;
        self.state.input_buffer.clear();
        self.state.input_cursor = 0;

        let command = normalize_slash_command(&raw);
        if self.state.history.last().as_deref() != Some(&raw) {
            self.state.history.push(raw);
        }
        self.state.history_index = self.state.history.len();

        self.state.chat.messages.push(Message::user(command.clone()));
        self.state.loading = true;
        self.state.chat.streaming_content.clear();

        let result = self.client.run(&command);
        self.state.loading = false;

        match result {
            Ok(r) => {
                if !r.should_continue {
                    self.should_quit = true;
                    return;
                }
                let text = format_output(r.output);
                self.state.chat.messages.push(Message::openx(text));
            }
            Err(e) => {
                self.state.chat.messages.push(Message::openx(format!("Error: {}", e)));
            }
        }
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
