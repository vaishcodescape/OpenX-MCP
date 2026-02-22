//! Status bar: git branch, connection status, shortcut pills — multi-color.

use ratatui::{
    text::{Line, Span},
    widgets::Paragraph,
    Frame,
};

use crate::ui::theme::styles;

/// Shortcut pills when input has focus.
const PILLS_FOCUSED: &[(&str, &str)] = &[
    ("Esc", "unfocus"),
    ("Enter", "send"),
    ("Ctrl+C", "cancel"),
];

/// Shortcut pills when input does not have focus.
const PILLS_UNFOCUSED: &[(&str, &str)] = &[
    ("/", "commands"),
    ("PgUp/Dn", "scroll"),
    ("q", "quit"),
];

fn span_width(s: &Span) -> usize {
    s.content.chars().count()
}

pub fn render(
    f: &mut Frame,
    area: ratatui::prelude::Rect,
    loading: bool,
    spinner_char: char,
    git_branch: &str,
    connected: bool,
    input_focused: bool,
) {
    let mut left_spans = Vec::with_capacity(8);

    let conn_style = if connected { styles::green() } else { styles::error() };
    left_spans.push(Span::styled(" ● ", conn_style));

    if !git_branch.is_empty() && git_branch != "no-git" {
        left_spans.push(Span::styled(
            format!(" {git_branch} "),
            styles::green_bold(),
        ));
        left_spans.push(Span::styled("│", styles::border()));
    }

    if loading {
        left_spans.push(Span::styled(
            format!(" {spinner_char} "),
            styles::accent(),
        ));
        left_spans.push(Span::styled("Thinking… ", styles::text_dim()));
    } else {
        left_spans.push(Span::styled(" Ready ", styles::muted()));
    }

    let left_width: usize = left_spans.iter().map(span_width).sum();
    let pills = if input_focused { PILLS_FOCUSED } else { PILLS_UNFOCUSED };

    let mut right_spans = Vec::with_capacity(pills.len() * 2);
    for (key, label) in pills {
        right_spans.push(Span::styled(format!(" {key} "), styles::pill_key()));
        right_spans.push(Span::styled(format!(" {label} "), styles::muted()));
    }

    let right_width: usize = right_spans.iter().map(span_width).sum();
    let pad = (area.width as usize)
        .saturating_sub(left_width)
        .saturating_sub(right_width);

    left_spans.push(Span::styled(
        " ".repeat(pad),
        styles::elevated_bg(),
    ));
    left_spans.extend(right_spans);

    let para = Paragraph::new(Line::from(left_spans)).style(styles::elevated_bg());
    f.render_widget(para, area);
}
