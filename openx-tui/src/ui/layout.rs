//! Single-column layout with inner margin for content.

use ratatui::layout::{Constraint, Direction, Layout, Rect};

use super::theme::{HEADER_HEIGHT, INPUT_HEIGHT, MARGIN_X, MIN_CHAT_LINES, STATUS_HEIGHT};

#[derive(Clone, Debug)]
pub struct LayoutRegions {
    pub header: Rect,
    pub chat: Rect,
    pub input: Rect,
    pub status: Rect,
}

/// Returns the rect for the palette overlay at the bottom of the chat area.
#[inline]
pub fn palette_overlay_rect(chat: Rect) -> Rect {
    use super::theme::{PALETTE_MARGIN_BOTTOM, PALETTE_MAX_HEIGHT};
    let max_h = chat.height.saturating_sub(PALETTE_MARGIN_BOTTOM).min(PALETTE_MAX_HEIGHT);
    Rect {
        x: chat.x,
        y: chat.y + chat.height.saturating_sub(max_h),
        width: chat.width,
        height: max_h,
    }
}

pub fn compute(area: Rect) -> LayoutRegions {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(HEADER_HEIGHT),
            Constraint::Min(MIN_CHAT_LINES),
            Constraint::Length(INPUT_HEIGHT),
            Constraint::Length(STATUS_HEIGHT),
        ])
        .split(area);
    let chat = Rect {
        x: area.x + MARGIN_X,
        y: chunks[1].y,
        width: area.width.saturating_sub(2 * MARGIN_X),
        height: chunks[1].height,
    };
    LayoutRegions {
        header: chunks[0],
        chat,
        input: chunks[2],
        status: chunks[3],
    }
}
