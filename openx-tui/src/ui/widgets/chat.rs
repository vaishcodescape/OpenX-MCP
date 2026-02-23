//! Chat: multi-color message blocks with role icons and timestamps. 

use ratatui::{
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph, Wrap},
    Frame,
};
use std::time::SystemTime;

use crate::state::{ChatState, MessageRole};
use crate::ui::markdown;
use crate::ui::theme::{colors, MESSAGE_GAP};

/// Use pure white for chat body so it's visible in any terminal.
const CHAT_TEXT: Color = Color::White;

/// Format a SystemTime as "HH:MM".
fn format_time(t: &SystemTime) -> String {
    let secs = t
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let total_mins = secs / 60;
    let hours = (total_mins / 60) % 24;
    let mins = total_mins % 60;
    format!("{:02}:{:02}", hours, mins)
}

pub fn render(
    f: &mut Frame,
    chat: &ChatState,
    area: ratatui::prelude::Rect,
    loading: bool,
    _spinner_char: char,
    openx_loading_frame: &str,
) {
    let block = Block::default()
        .borders(Borders::NONE)
        .style(Style::default().bg(colors::BG));
    let inner = block.inner(area);
    f.render_widget(block, area);

    let height = inner.height as usize;
    let estimated_lines = chat
        .messages
        .iter()
        .map(|m| 1 + m.content.lines().count() + MESSAGE_GAP)
        .sum::<usize>()
        .saturating_add(8);
    let mut lines = Vec::with_capacity(estimated_lines.min(2048));

    // ── Build message lines ──────────────────────────────────────
    let mut first_message = true;

    for msg in &chat.messages {
        if !first_message {
            for _ in 0..MESSAGE_GAP {
                lines.push(Line::from(Span::raw("")));
            }
        }
        first_message = false;

        let (icon, label, label_style, time_str) = match msg.role {
            MessageRole::User => (
                "❯ ",
                "You",
                Style::default()
                    .fg(colors::USER_ROLE)
                    .add_modifier(Modifier::BOLD),
                format_time(&msg.timestamp),
            ),
            MessageRole::OpenX => (
                "◆ ",
                "OpenX",
                Style::default()
                    .fg(colors::OPENX_ROLE)
                    .add_modifier(Modifier::BOLD),
                format_time(&msg.timestamp),
            ),
            MessageRole::System => (
                "● ",
                "",
                Style::default().fg(colors::SYSTEM),
                String::new(),
            ),
        };

        let content_style = Style::default().fg(CHAT_TEXT);
        // Codex-style: format both user and OpenX with markdown (headings, code blocks, lists).
        let content_lines: Vec<Line> = markdown::to_lines(&msg.content);

        // First line: icon + label + timestamp + first content line.
        let mut it = content_lines.into_iter();
        if let Some(first) = it.next() {
            let mut spans: Vec<Span> = Vec::new();
            if label.is_empty() {
                spans.push(Span::styled(icon, label_style));
            } else {
                spans.push(Span::styled(
                    format!("{}{}", icon, label),
                    label_style,
                ));
                spans.push(Span::styled(" ", content_style));
                if !time_str.is_empty() {
                    spans.push(Span::styled(
                        format!("{} ", time_str),
                        Style::default().fg(colors::TIMESTAMP),
                    ));
                }
            }
            for s in first {
                spans.push(s);
            }
            lines.push(Line::from(spans));
        }

        // Continuation lines with consistent indent.
        let indent = if label.is_empty() { "  " } else { "        " };
        for line in it {
            let mut spans = vec![Span::styled(indent, content_style)];
            for s in line {
                spans.push(s);
            }
            lines.push(Line::from(spans));
        }
    }

    // ── Streaming / loading indicator (OpenX loading animation) ───
    if loading && chat.streaming_content.is_empty() {
        if !lines.is_empty() {
            for _ in 0..MESSAGE_GAP {
                lines.push(Line::from(Span::raw("")));
            }
        }
        lines.push(Line::from(vec![
            Span::styled(
                "◆ OpenX ",
                Style::default()
                    .fg(colors::OPENX_ROLE)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::styled(openx_loading_frame, Style::default().fg(colors::TEXT_DIM)),
        ]));
    } else if !chat.streaming_content.is_empty() {
        if !lines.is_empty() {
            for _ in 0..MESSAGE_GAP {
                lines.push(Line::from(Span::raw("")));
            }
        }
        lines.push(Line::from(vec![
            Span::styled(
                "◆ OpenX ",
                Style::default()
                    .fg(colors::OPENX_ROLE)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::styled(
                chat.streaming_content.clone(),
                Style::default().fg(CHAT_TEXT),
            ),
        ]));
    }

    // Empty state — minimal prompt.
    if lines.is_empty() {
        lines.push(Line::from(Span::styled(
            "Type a message to get started.",
            Style::default().fg(colors::MUTED),
        )));
    }

    // ── Scroll and render ────────────────────────────────────────
    let total = lines.len();
    let scroll = chat.scroll.min(total.saturating_sub(height));
    let visible: Vec<Line> = lines.into_iter().skip(scroll).take(height).collect();
    let para = Paragraph::new(visible)
        .style(Style::default().fg(CHAT_TEXT).bg(colors::BG))
        .wrap(Wrap { trim: false });
    f.render_widget(para, inner);
}
