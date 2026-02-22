//! Input bar: Claude/Codex-style bordered prompt with placeholder.

use ratatui::{
    layout::Position,
    style::Modifier,
    text::{Line, Span},
    widgets::{Block, Borders, BorderType, Paragraph},
    Frame,
};

use crate::ui::theme::styles;

pub fn render(
    f: &mut Frame,
    buffer: &str,
    cursor_pos: usize,
    area: ratatui::prelude::Rect,
    input_focused: bool,
) {
    let border_style = if input_focused {
        styles::accent()
    } else {
        styles::border()
    };

    let block = Block::default()
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(border_style)
        .style(styles::elevated_bg());
    let inner = block.inner(area);
    f.render_widget(block, area);

    let prompt_icon = if input_focused { "❯ " } else { "▸ " };

    let line = if buffer.is_empty() {
        let icon_style = if input_focused {
            styles::accent_bold()
        } else {
            styles::muted().add_modifier(Modifier::BOLD)
        };
        Line::from(vec![
            Span::styled(prompt_icon, icon_style),
            Span::styled("Type a message… (/ for commands)", styles::muted()),
        ])
    } else {
        Line::from(vec![
            Span::styled(prompt_icon, styles::accent_bold()),
            Span::styled(buffer, styles::text()),
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
