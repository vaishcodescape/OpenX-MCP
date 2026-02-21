//! Input bar: Claude/Codex-style bordered prompt with placeholder.

use ratatui::{
    layout::Position,
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, BorderType, Paragraph},
    Frame,
};

use crate::ui::theme::colors;

pub fn render(
    f: &mut Frame,
    buffer: &str,
    cursor_pos: usize,
    area: ratatui::prelude::Rect,
    input_focused: bool,
) {
    let border_color = if input_focused {
        colors::ACCENT
    } else {
        colors::BORDER
    };

    let block = Block::default()
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(Style::default().fg(border_color))
        .style(Style::default().bg(colors::ELEVATED));
    let inner = block.inner(area);
    f.render_widget(block, area);

    let prompt_icon = if input_focused { "❯ " } else { "▸ " };

    let line = if buffer.is_empty() {
        Line::from(vec![
            Span::styled(
                prompt_icon,
                Style::default()
                    .fg(if input_focused { colors::ACCENT } else { colors::MUTED })
                    .add_modifier(Modifier::BOLD),
            ),
            Span::styled(
                "Type a message… (/ for commands)",
                Style::default().fg(colors::MUTED),
            ),
        ])
    } else {
        Line::from(vec![
            Span::styled(
                prompt_icon,
                Style::default()
                    .fg(colors::ACCENT)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::styled(buffer, Style::default().fg(colors::TEXT)),
        ])
    };

    // Center the text line vertically within the inner area.
    let text_y = inner.y + inner.height / 2;
    let text_area = ratatui::prelude::Rect {
        x: inner.x,
        y: text_y,
        width: inner.width,
        height: 1,
    };

    let para = Paragraph::new(line);
    f.render_widget(para, text_area);

    // Position the cursor.
    let prompt_len = prompt_icon.chars().count() as u16;
    let cursor_x = text_area.x
        + prompt_len
        + buffer
            .get(..cursor_pos)
            .map(|s| s.chars().count())
            .unwrap_or(0) as u16;
    let x = cursor_x.min(text_area.x + text_area.width.saturating_sub(1));
    f.set_cursor_position(Position {
        x,
        y: text_area.y,
    });
}
