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
    /// OpenX brand — orange.
    pub const OPENX_ORANGE: Color = Color::Rgb(0xff, 0x95, 0x00);
    /// User role color — warm gold.
    pub const USER_ROLE: Color = Color::Rgb(0xff, 0xb8, 0x6c);
    /// System message color — soft pink.
    pub const SYSTEM: Color = Color::Rgb(0xff, 0x79, 0xc6);
    /// OpenX role — cyan teal.
    pub const OPENX_ROLE: Color = Color::Rgb(0x00, 0xe5, 0xcc);
    /// Timestamp color.
    pub const TIMESTAMP: Color = Color::Rgb(0x44, 0x47, 0x5a);
}

/// Reusable styles to avoid repeated `Style::default().fg(...)` in render paths.
pub mod styles {
    use super::colors;
    use ratatui::style::{Modifier, Style};

    #[inline(always)]
    pub fn border() -> Style {
        Style::default().fg(colors::BORDER)
    }

    #[inline(always)]
    pub fn muted() -> Style {
        Style::default().fg(colors::MUTED)
    }

    #[inline(always)]
    pub fn text() -> Style {
        Style::default().fg(colors::TEXT)
    }

    #[inline(always)]
    pub fn text_dim() -> Style {
        Style::default().fg(colors::TEXT_DIM)
    }

    #[inline(always)]
    pub fn elevated_bg() -> Style {
        Style::default().bg(colors::ELEVATED)
    }

    #[inline(always)]
    pub fn accent_bold() -> Style {
        Style::default().fg(colors::ACCENT).add_modifier(Modifier::BOLD)
    }

    #[inline(always)]
    pub fn openx_orange_bold() -> Style {
        Style::default().fg(colors::OPENX_ORANGE).add_modifier(Modifier::BOLD)
    }

    #[inline(always)]
    pub fn openx_role() -> Style {
        Style::default().fg(colors::OPENX_ROLE)
    }

    #[inline(always)]
    pub fn green() -> Style {
        Style::default().fg(colors::GREEN)
    }

    #[inline(always)]
    pub fn green_bold() -> Style {
        Style::default().fg(colors::GREEN).add_modifier(Modifier::BOLD)
    }

    #[inline(always)]
    pub fn error() -> Style {
        Style::default().fg(colors::ERROR)
    }

    #[inline(always)]
    pub fn accent() -> Style {
        Style::default().fg(colors::ACCENT)
    }

    /// Status bar pill (key) — muted bg, dark fg.
    #[inline(always)]
    pub fn pill_key() -> Style {
        Style::default().fg(colors::BG).bg(colors::MUTED)
    }
}

pub const HEADER_HEIGHT: u16 = 5;
pub const STATUS_HEIGHT: u16 = 1;
pub const INPUT_HEIGHT: u16 = 3;
/// Minimum number of lines for the chat area (layout constraint).
pub const MIN_CHAT_LINES: u16 = 4;
/// Blank lines between messages.
pub const MESSAGE_GAP: usize = 1;
/// Inner horizontal margin (chars each side).
pub const MARGIN_X: u16 = 1;
/// Max height of command palette overlay (lines).
pub const PALETTE_MAX_HEIGHT: u16 = 16;
/// Vertical margin when placing palette overlay inside chat (lines from bottom).
pub const PALETTE_MARGIN_BOTTOM: u16 = 2;
pub const SPINNER: &[char] = &['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

/// Codex-style loading animation (blinking block cursor).
pub const OPENX_LOADING_FRAMES: &[&str] = &["█", "█", "█", " ", " ", " "];
