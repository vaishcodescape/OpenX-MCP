//! Keybindings: Enter submit, Ctrl+C cancel, Ctrl+L clear, Up/Down history, PgUp/PgDn scroll, Esc overlay.

use crate::actions::Action;
use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
use std::time::Duration;

pub const TICK_RATE: Duration = Duration::from_millis(80);

pub fn key_to_action(event: &KeyEvent, palette_visible: bool) -> Option<Action> {
    // Accept Press and Repeat (hold key); ignore Release so we don't double-handle.
    if event.kind == KeyEventKind::Release {
        return None;
    }
    let (code, mods) = (event.code, event.modifiers);

    if code == KeyCode::Char('c') && mods.contains(KeyModifiers::CONTROL) {
        return Some(Action::CancelStreaming);
    }
    if code == KeyCode::Char('l') && mods.contains(KeyModifiers::CONTROL) {
        return Some(Action::ClearInput);
    }
    if code == KeyCode::Char('q') && mods.is_empty() {
        return Some(Action::Quit);
    }
    if code == KeyCode::Esc && mods.is_empty() {
        return Some(Action::PaletteHide);
    }

    if code == KeyCode::Enter && mods.is_empty() {
        return Some(Action::Submit);
    }
    if code == KeyCode::Backspace && mods.is_empty() {
        return Some(Action::Backspace);
    }

    if code == KeyCode::Up && mods.is_empty() {
        return if palette_visible {
            Some(Action::PaletteUp)
        } else {
            Some(Action::HistoryUp)
        };
    }
    if code == KeyCode::Down && mods.is_empty() {
        return if palette_visible {
            Some(Action::PaletteDown)
        } else {
            Some(Action::HistoryDown)
        };
    }

    if code == KeyCode::PageUp && mods.is_empty() {
        return Some(Action::ChatScrollPageUp);
    }
    if code == KeyCode::PageDown && mods.is_empty() {
        return Some(Action::ChatScrollPageDown);
    }
    if code == KeyCode::Char('g') && mods.is_empty() {
        return Some(Action::ChatScrollTop);
    }
    if code == KeyCode::Char('G') && mods.contains(KeyModifiers::SHIFT) {
        return Some(Action::ChatScrollBottom);
    }

    if code == KeyCode::Char('/') && mods.is_empty() {
        return Some(Action::PaletteShow);
    }
    if code == KeyCode::Tab && mods.is_empty() && palette_visible {
        return Some(Action::PaletteSelect);
    }
    if code == KeyCode::Char('j') && mods.is_empty() && !palette_visible {
        return Some(Action::ChatScrollDown);
    }
    if code == KeyCode::Char('k') && mods.is_empty() && !palette_visible {
        return Some(Action::ChatScrollUp);
    }

    // Any other character goes to input (allow Alt for accented chars; only block Ctrl/Cmd).
    if let KeyCode::Char(c) = code {
        if !mods.contains(KeyModifiers::CONTROL) && !mods.contains(KeyModifiers::SUPER) {
            return Some(Action::Char(c));
        }
    }

    None
}
