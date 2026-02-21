//! Theme: True black background with multi-color accents.

use ratatui::style::Color;

pub mod colors {
    use super::*;
    /// Main canvas — true black.
    pub const BG: Color = Color::Rgb(0x00, 0x00, 0x00);
    /// Input bar, status, palette — very dark gray.
    pub const ELEVATED: Color = Color::Rgb(0x0c, 0x0c, 0x0c);
    /// Borders / separators.
    pub const BORDER: Color = Color::Rgb(0x28, 0x28, 0x28);
    /// Primary accent — electric blue.
    pub const ACCENT: Color = Color::Rgb(0x6b, 0xbc, 0xff);
    /// OpenX label — cyan glow.
    #[allow(dead_code)]
    pub const ACCENT_SOFT: Color = Color::Rgb(0x00, 0xe5, 0xcc);
    /// Selection highlight (palette row) — subtle blue glow.
    #[allow(dead_code)]
    pub const ACCENT_GLOW: Color = Color::Rgb(0x0e, 0x1a, 0x2a);
    /// Cursor and active input.
    #[allow(dead_code)]
    pub const CURSOR: Color = Color::Rgb(0x6e, 0xc8, 0xff);
    /// Body text — pure white for max visibility.
    pub const TEXT: Color = Color::Rgb(0xf0, 0xf0, 0xf0);
    /// Secondary text — light gray.
    pub const TEXT_DIM: Color = Color::Rgb(0xa0, 0xa8, 0xb4);
    /// Hints.
    pub const MUTED: Color = Color::Rgb(0x60, 0x68, 0x72);
    /// Code blocks.
    pub const CODE_BG: Color = Color::Rgb(0x0a, 0x0e, 0x14);
    /// User message tint.
    #[allow(dead_code)]
    pub const USER_BG: Color = Color::Rgb(0x06, 0x08, 0x0c);
    /// Error — coral red.
    pub const ERROR: Color = Color::Rgb(0xff, 0x6b, 0x6b);
    /// Green for git branch / connected.
    pub const GREEN: Color = Color::Rgb(0x50, 0xfa, 0x7b);
    /// Yellow/amber.
    #[allow(dead_code)]
    pub const AMBER: Color = Color::Rgb(0xff, 0xd3, 0x66);
    /// Palette backdrop overlay.
    #[allow(dead_code)]
    pub const BACKDROP: Color = Color::Rgb(0x06, 0x06, 0x06);
    /// Heading — lavender/purple.
    pub const HEADING: Color = Color::Rgb(0xbd, 0x93, 0xf9);
    /// User role color — warm gold.
    pub const USER_ROLE: Color = Color::Rgb(0xff, 0xb8, 0x6c);
    /// System message color — soft pink.
    pub const SYSTEM: Color = Color::Rgb(0xff, 0x79, 0xc6);
    /// OpenX role — cyan teal.
    pub const OPENX_ROLE: Color = Color::Rgb(0x00, 0xe5, 0xcc);
    /// Timestamp color.
    pub const TIMESTAMP: Color = Color::Rgb(0x44, 0x47, 0x5a);
}

pub const STATUS_HEIGHT: u16 = 1;
pub const INPUT_HEIGHT: u16 = 3;
/// Blank lines between messages.
pub const MESSAGE_GAP: usize = 1;
/// Inner horizontal margin (chars each side).
pub const MARGIN_X: u16 = 1;
pub const SPINNER: &[char] = &['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
