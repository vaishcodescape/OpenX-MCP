//! Keybinding map: `KeyEvent` → `Action`.
//!
//! Three context flags narrow which action is returned:
//! - `palette_visible` — the command palette overlay is open.
//! - `input_has_focus` — the input buffer is non-empty or explicitly focused; bare-letter
//!   shortcuts are disabled so characters go to the buffer instead.
//! - `input_empty` — when `true`, ↑/↓ scroll the chat; when `false`, they cycle history.

use crate::actions::Action;
use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
use std::time::Duration;

/// Tick rate for the main event loop.
pub const TICK_RATE: Duration = Duration::from_millis(80);

/// Map a key event to an [`Action`], or return `None` to ignore it.
pub fn key_to_action(
    event: &KeyEvent,
    palette_visible: bool,
    input_has_focus: bool,
    input_empty: bool,
) -> Option<Action> {
    // Ignore Release events — only process Press and Repeat.
    if event.kind == KeyEventKind::Release {
        return None;
    }
    let (code, mods) = (event.code, event.modifiers);
    let ctrl = mods.contains(KeyModifiers::CONTROL);
    let bare = mods.is_empty();

    // ── Always-active shortcuts ────────────────────────────────────────────
    if ctrl {
        return match code {
            KeyCode::Char('c') => Some(Action::CancelStreaming),
            KeyCode::Char('l') => Some(Action::ClearInput),
            _ => None,
        };
    }

    if code == KeyCode::Esc && bare {
        return Some(if palette_visible {
            Action::PaletteHide
        } else if input_has_focus {
            Action::UnfocusInput
        } else {
            Action::Quit
        });
    }

    if code == KeyCode::Enter    && bare { return Some(Action::Submit);    }
    if code == KeyCode::Backspace && bare { return Some(Action::Backspace); }

    // ── Arrow / page keys ─────────────────────────────────────────────────
    if code == KeyCode::Up && bare {
        return Some(if palette_visible    { Action::PaletteUp }
                    else if input_empty   { Action::ChatScrollPageUp }
                    else                  { Action::HistoryUp });
    }
    if code == KeyCode::Down && bare {
        return Some(if palette_visible    { Action::PaletteDown }
                    else if input_empty   { Action::ChatScrollPageDown }
                    else                  { Action::HistoryDown });
    }
    if code == KeyCode::PageUp   && bare { return Some(Action::ChatScrollPageUp);   }
    if code == KeyCode::PageDown && bare { return Some(Action::ChatScrollPageDown);  }
    if code == KeyCode::Tab      && bare && palette_visible { return Some(Action::PaletteSelect); }

    // ── Normal-mode (unfocused) shortcuts ─────────────────────────────────
    // Only consume q, g, G as shortcuts when unfocused; let all other keys fall through
    // to the input buffer so typing works when the input line is empty.
    if !input_has_focus && !palette_visible && bare {
        if let KeyCode::Char(c) = code {
            match c {
                'q' => return Some(Action::Quit),
                'g' => return Some(Action::ChatScrollTop),
                'G' => return Some(Action::ChatScrollBottom),
                _ => {} // fall through so Action::Char(c) is returned below
            }
        }
    }

    // ── Palette trigger ───────────────────────────────────────────────────
    if code == KeyCode::Char('/') && bare && !palette_visible && !input_has_focus {
        return Some(Action::PaletteShow);
    }

    // ── Any other character → input buffer ───────────────────────────────
    if let KeyCode::Char(c) = code {
        if !mods.contains(KeyModifiers::CONTROL) && !mods.contains(KeyModifiers::SUPER) {
            return Some(Action::Char(c));
        }
    }

    None
}
