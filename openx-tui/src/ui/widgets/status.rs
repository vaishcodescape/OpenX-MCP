//! Status bar: git branch, connection status, shortcut pills — multi-color.

use ratatui::{
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::Paragraph,
    Frame,
};

use crate::ui::theme::colors;

pub fn render(
    f: &mut Frame,
    area: ratatui::prelude::Rect,
    loading: bool,
    spinner_char: char,
    git_branch: &str,
    connected: bool,
    input_focused: bool,
) {
    let mut left_spans: Vec<Span> = Vec::new();

    // Connection indicator dot.
    if connected {
        left_spans.push(Span::styled(" ● ", Style::default().fg(colors::GREEN)));
    } else {
        left_spans.push(Span::styled(" ● ", Style::default().fg(colors::ERROR)));
    }

    // Git branch.
    if !git_branch.is_empty() && git_branch != "no-git" {
        left_spans.push(Span::styled(
            format!(" {} ", git_branch),
            Style::default()
                .fg(colors::GREEN)
                .add_modifier(Modifier::BOLD),
        ));
        left_spans.push(Span::styled("│", Style::default().fg(colors::BORDER)));
    }

    // Loading indicator.
    if loading {
        left_spans.push(Span::styled(
            format!(" {} ", spinner_char),
            Style::default().fg(colors::ACCENT),
        ));
        left_spans.push(Span::styled(
            "Thinking… ",
            Style::default().fg(colors::TEXT_DIM),
        ));
    } else {
        left_spans.push(Span::styled(
            " Ready ",
            Style::default().fg(colors::MUTED),
        ));
    }

    // Calculate left width.
    let left_width: usize = left_spans.iter().map(|s| s.content.chars().count()).sum();

    // Right-side shortcut pills — context-aware.
    let pills: Vec<(&str, &str)> = if input_focused {
        vec![
            ("Esc", "unfocus"),
            ("Enter", "send"),
            ("Ctrl+C", "cancel"),
        ]
    } else {
        vec![
            ("/", "commands"),
            ("PgUp/Dn", "scroll"),
            ("q", "quit"),
        ]
    };

    let mut right_spans: Vec<Span> = Vec::new();
    for (key, label) in &pills {
        right_spans.push(Span::styled(
            format!(" {} ", key),
            Style::default()
                .fg(colors::BG)
                .bg(colors::MUTED),
        ));
        right_spans.push(Span::styled(
            format!(" {} ", label),
            Style::default().fg(colors::MUTED),
        ));
    }

    let right_width: usize = right_spans.iter().map(|s| s.content.chars().count()).sum();

    // Pad between left and right.
    let width = area.width as usize;
    let pad = width.saturating_sub(left_width + right_width);

    let mut all_spans = left_spans;
    all_spans.push(Span::styled(
        " ".repeat(pad),
        Style::default().bg(colors::ELEVATED),
    ));
    all_spans.extend(right_spans);

    let line = Line::from(all_spans);
    let para = Paragraph::new(line).style(Style::default().bg(colors::ELEVATED));
    f.render_widget(para, area);
}
