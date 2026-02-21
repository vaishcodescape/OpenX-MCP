//! Logs panel: append-only messages, auto-scroll.

use ratatui::{
    style::{Modifier, Style},
    text::Line,
    widgets::{Block, Borders, BorderType, Paragraph, Wrap},
    Frame,
};

use crate::state::{LogEntry, LogLevel};
use crate::ui::theme::colors;

fn level_style(level: LogLevel) -> Style {
    match level {
        LogLevel::Info => Style::default().fg(colors::TEXT_DIM),
        LogLevel::Warn => Style::default().fg(colors::WARNING),
        LogLevel::Error => Style::default().fg(colors::ERROR),
        LogLevel::Debug => Style::default().fg(colors::MUTED),
    }
}

pub fn render(
    f: &mut Frame,
    entries: &[LogEntry],
    scroll: usize,
    auto_scroll: bool,
    area: ratatui::prelude::Rect,
    focused: bool,
) {
    let border_style = if focused {
        Style::default().fg(colors::PRIMARY)
    } else {
        Style::default().fg(colors::BORDERS)
    };
    let title = if auto_scroll { " Logs (auto) " } else { " Logs " };
    let block = Block::default()
        .title(title)
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(border_style)
        .style(Style::default().bg(colors::ELEVATED));
    let inner = block.inner(area);
    f.render_widget(block, area);

    let lines: Vec<Line> = entries
        .iter()
        .map(|e| {
            let prefix = format!("[{}] ", match e.level {
                LogLevel::Info => "INF",
                LogLevel::Warn => "WRN",
                LogLevel::Error => "ERR",
                LogLevel::Debug => "DBG",
            });
            Line::from(vec![
                ratatui::text::Span::styled(prefix, level_style(e.level).add_modifier(Modifier::BOLD)),
                ratatui::text::Span::raw(e.message.as_str()),
            ])
        })
        .collect();
    let height = inner.height as usize;
    let total = lines.len();
    let scroll_val = scroll.min(total.saturating_sub(height));
    let visible: Vec<Line> = lines.into_iter().skip(scroll_val).take(height).collect();
    let para = Paragraph::new(visible)
        .style(Style::default().fg(colors::TEXT_DIM))
        .wrap(Wrap { trim: false })
        .scroll((scroll_val as u16, 0));
    f.render_widget(para, inner);
}
