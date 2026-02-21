//! Chat: high-visibility message blocks (white text on dark bg).

use ratatui::{
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, BorderType, Paragraph, Wrap},
    Frame,
};

use crate::state::{ChatState, MessageRole};
use crate::ui::markdown;
use crate::ui::theme::{colors, MESSAGE_GAP};

/// Use pure white for chat body so it's visible in any terminal.
const CHAT_TEXT: Color = Color::White;

pub fn render(
    f: &mut Frame,
    chat: &ChatState,
    area: ratatui::prelude::Rect,
    loading: bool,
    spinner_char: char,
) {
    let mut lines: Vec<Line> = Vec::new();
    let mut first_message = true;

    for msg in &chat.messages {
        if !first_message {
            for _ in 0..MESSAGE_GAP {
                lines.push(Line::from(Span::raw("")));
            }
        }
        first_message = false;

        let (label, label_style) = match msg.role {
            MessageRole::User => ("You", Style::default().fg(colors::ACCENT).add_modifier(Modifier::BOLD)),
            MessageRole::OpenX => ("OpenX", Style::default().fg(colors::ACCENT_SOFT).add_modifier(Modifier::BOLD)),
            MessageRole::System => ("", Style::default().fg(colors::TEXT_DIM)),
        };

        let content_style = Style::default().fg(CHAT_TEXT);
        let content_lines: Vec<Line> = if matches!(msg.role, MessageRole::OpenX) {
            markdown::to_lines(&msg.content)
        } else {
            msg.content
                .lines()
                .map(|s| Line::from(Span::styled(s, content_style)))
                .collect()
        };

        let mut it = content_lines.into_iter();
        if let Some(first) = it.next() {
            let mut spans = if label.is_empty() {
                vec![]
            } else {
                vec![Span::styled(format!("{} ", label), label_style.clone())]
            };
            for s in first {
                spans.push(s);
            }
            lines.push(Line::from(spans));
        }
        for line in it {
            let mut spans = vec![Span::styled(
                if label.is_empty() { "" } else { "     " },
                content_style,
            )];
            for s in line {
                spans.push(s);
            }
            lines.push(Line::from(spans));
        }
    }

    if loading && chat.streaming_content.is_empty() {
        if !lines.is_empty() {
            for _ in 0..MESSAGE_GAP {
                lines.push(Line::from(Span::raw("")));
            }
        }
        lines.push(Line::from(vec![
            Span::styled("OpenX ", Style::default().fg(colors::ACCENT_SOFT).add_modifier(Modifier::BOLD)),
            Span::styled(format!(" {} ", spinner_char), Style::default().fg(colors::ACCENT)),
            Span::styled("Thinking…", Style::default().fg(CHAT_TEXT)),
        ]));
    } else if !chat.streaming_content.is_empty() {
        if !lines.is_empty() {
            for _ in 0..MESSAGE_GAP {
                lines.push(Line::from(Span::raw("")));
            }
        }
        lines.push(Line::from(vec![
            Span::styled("OpenX ", Style::default().fg(colors::ACCENT_SOFT).add_modifier(Modifier::BOLD)),
            Span::styled(chat.streaming_content.as_str(), Style::default().fg(CHAT_TEXT)),
        ]));
    }

    if lines.is_empty() {
        lines.push(Line::from(Span::styled(
            "Ask anything.  /  command palette · Enter to send",
            Style::default().fg(CHAT_TEXT),
        )));
    }

    let block = Block::default()
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(Style::default().fg(colors::BORDER))
        .style(Style::default().bg(colors::BG));
    let inner = block.inner(area);
    f.render_widget(block, area);

    let height = inner.height as usize;
    let total = lines.len();
    let scroll = chat.scroll.min(total.saturating_sub(height));
    let visible: Vec<Line> = lines.into_iter().skip(scroll).take(height).collect();
    let para = Paragraph::new(visible)
        .style(Style::default().fg(CHAT_TEXT).bg(colors::BG))
        .wrap(Wrap { trim: false })
        .scroll((scroll as u16, 0));
    f.render_widget(para, inner);
}
