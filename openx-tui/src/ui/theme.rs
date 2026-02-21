//! Theme: Codex/Claude-style dark, refined hierarchy.

use ratatui::style::Color;

pub mod colors {
    use super::*;
    /// Main canvas (chat area) — dark gray so white text pops.
    pub const BG: Color = Color::Rgb(0x18, 0x1c, 0x22);
    /// Input bar, status, palette.
    pub const ELEVATED: Color = Color::Rgb(0x16, 0x1a, 0x1f);
    /// Borders / separators — visible.
    pub const BORDER: Color = Color::Rgb(0x2d, 0x34, 0x3e);
    /// Primary accent (prompt, You label).
    pub const ACCENT: Color = Color::Rgb(0x6b, 0xbc, 0xff);
    /// OpenX label, links.
    pub const ACCENT_SOFT: Color = Color::Rgb(0x99, 0xd4, 0xff);
    /// Selection highlight (palette row).
    #[allow(dead_code)]
    pub const ACCENT_GLOW: Color = Color::Rgb(0x1e, 0x2d, 0x3d);
    /// Cursor and active input.
    #[allow(dead_code)]
    pub const CURSOR: Color = Color::Rgb(0x6e, 0xc8, 0xff);
    /// Body text — near white, maximum visibility.
    pub const TEXT: Color = Color::Rgb(0xf2, 0xf4, 0xf8);
    /// Secondary text — clearly visible.
    pub const TEXT_DIM: Color = Color::Rgb(0xbc, 0xc5, 0xd0);
    /// Hints — visible.
    pub const MUTED: Color = Color::Rgb(0x94, 0x9e, 0xad);
    /// Code blocks — lighter so text stands out.
    pub const CODE_BG: Color = Color::Rgb(0x1e, 0x24, 0x2e);
    /// User message tint (very subtle).
    #[allow(dead_code)]
    pub const USER_BG: Color = Color::Rgb(0x11, 0x18, 0x1f);
    /// Error.
    #[allow(dead_code)]
    pub const ERROR: Color = Color::Rgb(0xf0, 0x6c, 0x6c);
}

pub const STATUS_HEIGHT: u16 = 1;
pub const INPUT_HEIGHT: u16 = 1;
/// Blank line between messages.
pub const MESSAGE_GAP: usize = 1;
/// Inner horizontal margin (chars each side).
pub const MARGIN_X: u16 = 1;
pub const SPINNER: &[char] = &['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
