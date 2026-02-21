//! Markdown to ratatui Line/Spans: headings, code blocks, inline code, bold, lists, horizontal rules.

use pulldown_cmark::{CodeBlockKind, Event, Tag, Options, Parser};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};

use super::theme::colors;

/// Body text in markdown — white for maximum visibility.
const MD_TEXT: Color = Color::White;

/// Convert markdown string to a list of Lines (owned, no lifetime).
pub fn to_lines(md: &str) -> Vec<Line<'static>> {
    let mut lines: Vec<Line<'static>> = Vec::new();
    let mut current: Vec<Span<'static>> = Vec::new();
    let mut in_code_block = false;
    let mut code_block_lines: Vec<String> = Vec::new();
    let mut bold = false;
    let mut in_heading = false;
    let mut list_depth: usize = 0;
    let mut ordered_index: Option<u64> = None;
    let opts = Options::all();

    for event in Parser::new_ext(md, opts) {
        match event {
            // ── Code blocks ──────────────────────────────────────
            Event::Start(Tag::CodeBlock(CodeBlockKind::Fenced(_))) => {
                flush_spans(&mut current, &mut lines);
                in_code_block = true;
                code_block_lines.clear();
            }
            Event::End(Tag::CodeBlock(_)) => {
                if in_code_block {
                    for line in &code_block_lines {
                        lines.push(Line::from(vec![
                            Span::styled(
                                " ┃ ".to_string(),
                                Style::default().fg(colors::BORDER).bg(colors::CODE_BG),
                            ),
                            Span::styled(
                                line.clone(),
                                Style::default().fg(MD_TEXT).bg(colors::CODE_BG),
                            ),
                        ]));
                    }
                    lines.push(Line::from(Span::raw("")));
                    in_code_block = false;
                }
            }

            // ── Headings ─────────────────────────────────────────
            Event::Start(Tag::Heading(..)) => {
                flush_spans(&mut current, &mut lines);
                in_heading = true;
                current.push(Span::styled(
                    "# ".to_string(),
                    Style::default()
                        .fg(colors::HEADING)
                        .add_modifier(Modifier::BOLD),
                ));
            }
            Event::End(Tag::Heading(..)) => {
                in_heading = false;
                flush_spans(&mut current, &mut lines);
            }

            // ── Lists ────────────────────────────────────────────
            Event::Start(Tag::List(start)) => {
                flush_spans(&mut current, &mut lines);
                list_depth += 1;
                ordered_index = start;
            }
            Event::End(Tag::List(_)) => {
                list_depth = list_depth.saturating_sub(1);
                if list_depth == 0 {
                    ordered_index = None;
                }
            }
            Event::Start(Tag::Item) => {
                let indent = "  ".repeat(list_depth.saturating_sub(1));
                let bullet = if let Some(idx) = ordered_index {
                    let s = format!("{}{}. ", indent, idx);
                    ordered_index = Some(idx + 1);
                    s
                } else {
                    let marker = if list_depth <= 1 { "• " } else { "◦ " };
                    format!("{}{}", indent, marker)
                };
                current.push(Span::styled(
                    bullet,
                    Style::default().fg(colors::ACCENT),
                ));
            }
            Event::End(Tag::Item) => {
                flush_spans(&mut current, &mut lines);
            }

            // ── Text ─────────────────────────────────────────────
            Event::Text(t) => {
                let s = t.to_string();
                if in_code_block {
                    code_block_lines.push(s);
                } else {
                    let style = if in_heading {
                        Style::default()
                            .fg(colors::HEADING)
                            .add_modifier(Modifier::BOLD)
                    } else if bold {
                        Style::default()
                            .fg(MD_TEXT)
                            .add_modifier(Modifier::BOLD)
                    } else {
                        Style::default().fg(MD_TEXT)
                    };
                    current.push(Span::styled(s, style));
                }
            }

            // ── Inline code ──────────────────────────────────────
            Event::Code(t) => {
                let s = t.to_string();
                current.push(Span::styled(
                    format!(" {} ", s),
                    Style::default().fg(colors::ACCENT).bg(colors::CODE_BG),
                ));
            }

            // ── Bold / emphasis ──────────────────────────────────
            Event::Start(Tag::Strong) | Event::Start(Tag::Emphasis) => {
                bold = true;
            }
            Event::End(Tag::Strong) | Event::End(Tag::Emphasis) => {
                bold = false;
            }

            // ── Line breaks ──────────────────────────────────────
            Event::SoftBreak | Event::HardBreak => {
                flush_spans(&mut current, &mut lines);
            }
            Event::End(Tag::Paragraph) => {
                flush_spans(&mut current, &mut lines);
            }

            // ── Horizontal rule ──────────────────────────────────
            Event::Rule => {
                flush_spans(&mut current, &mut lines);
                lines.push(Line::from(Span::styled(
                    "────────────────────────────────────────".to_string(),
                    Style::default().fg(colors::BORDER),
                )));
            }

            _ => {}
        }
    }
    flush_spans(&mut current, &mut lines);
    if lines.is_empty() {
        lines.push(Line::from(Span::raw("")));
    }
    lines
}

fn flush_spans(current: &mut Vec<Span<'static>>, lines: &mut Vec<Line<'static>>) {
    if !current.is_empty() {
        lines.push(Line::from(std::mem::take(current)));
    }
}
