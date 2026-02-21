//! Status bar: minimal, hint + shortcuts.

use ratatui::{
    style::Style,
    text::Span,
    widgets::Paragraph,
    Frame,
};

use crate::ui::theme::colors;

pub fn render(
    f: &mut Frame,
    area: ratatui::prelude::Rect,
    loading: bool,
    spinner_char: char,
) {
    let left = if loading {
        format!(" {} Thinking…", spinner_char)
    } else {
        " Ready".to_string()
    };
    let right = " j/k scroll  ↑↓ history  / palette  Enter send  q quit ";
    let width = area.width as usize;
    let left_len = left.chars().count();
    let right_len = right.chars().count();
    let pad = width.saturating_sub(left_len + right_len);
    let line = format!("{}{}{}", left, " ".repeat(pad), right);
    let span = Span::styled(
        line,
        Style::default().fg(colors::MUTED).bg(colors::ELEVATED),
    );
    let para = Paragraph::new(span);
    f.render_widget(para, area);
}
