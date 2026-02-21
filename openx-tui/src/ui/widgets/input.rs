//! Input bar: Claude/Codex-style prompt and cursor.

use ratatui::{
    layout::Position,
    style::{Modifier, Style},
    text::Span,
    widgets::{Block, Paragraph},
    Frame,
};

use crate::ui::theme::colors;

pub fn render(
    f: &mut Frame,
    buffer: &str,
    cursor_pos: usize,
    area: ratatui::prelude::Rect,
) {
    let prompt = " ▸ ";
    let line = ratatui::text::Line::from(vec![
        Span::styled(prompt, Style::default().fg(colors::ACCENT).add_modifier(Modifier::BOLD)),
        Span::styled(buffer, Style::default().fg(colors::TEXT)),
    ]);
    let block = Block::default()
        .style(Style::default().bg(colors::ELEVATED))
        .borders(ratatui::widgets::Borders::TOP)
        .border_style(Style::default().fg(colors::BORDER))
        .border_type(ratatui::widgets::BorderType::Plain);
    let inner = block.inner(area);
    f.render_widget(block, area);
    let para = Paragraph::new(line);
    f.render_widget(para, inner);

    let cursor_x = inner.x + 3 + buffer.get(..cursor_pos).map(|s| s.chars().count()).unwrap_or(0) as u16;
    let cursor_y = inner.y;
    let x = cursor_x.min(inner.x + inner.width.saturating_sub(1));
    f.set_cursor_position(Position { x, y: cursor_y });
}
