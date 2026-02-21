//! Single-column layout with inner margin for content.

use ratatui::layout::{Constraint, Direction, Layout, Rect};

use super::theme::{INPUT_HEIGHT, MARGIN_X, STATUS_HEIGHT};

#[derive(Clone, Debug)]
pub struct LayoutRegions {
    pub chat: Rect,
    pub input: Rect,
    pub status: Rect,
}

pub fn compute(area: Rect) -> LayoutRegions {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Min(4),
            Constraint::Length(INPUT_HEIGHT),
            Constraint::Length(STATUS_HEIGHT),
        ])
        .split(area);
    let chat = Rect {
        x: area.x + MARGIN_X,
        y: chunks[0].y,
        width: area.width.saturating_sub(2 * MARGIN_X),
        height: chunks[0].height,
    };
    LayoutRegions {
        chat,
        input: chunks[1],
        status: chunks[2],
    }
}
