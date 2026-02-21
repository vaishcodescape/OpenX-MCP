//! Markdown to ratatui Line/Spans (code blocks, inline code, bold).

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
    let opts = Options::empty();

    for event in Parser::new_ext(md, opts) {
        match event {
            Event::Start(Tag::CodeBlock(CodeBlockKind::Fenced(_))) => {
                flush_spans(&mut current, &mut lines);
                in_code_block = true;
                code_block_lines.clear();
            }
            Event::End(Tag::CodeBlock(_)) => {
                if in_code_block {
                    for line in &code_block_lines {
                        lines.push(Line::from(Span::styled(
                            line.clone(),
                            Style::default().fg(MD_TEXT).bg(colors::CODE_BG),
                        )));
                    }
                    lines.push(Line::from(Span::raw("")));
                    in_code_block = false;
                }
            }
            Event::Text(t) => {
                let s = t.to_string();
                if in_code_block {
                    code_block_lines.push(s);
                } else {
                    let style = if bold {
                        Style::default().fg(MD_TEXT).add_modifier(Modifier::BOLD)
                    } else {
                        Style::default().fg(MD_TEXT)
                    };
                    current.push(Span::styled(s, style));
                }
            }
            Event::Code(t) => {
                let s = t.to_string();
                current.push(Span::styled(
                    s,
                    Style::default().fg(colors::ACCENT).bg(colors::CODE_BG),
                ));
            }
            Event::Start(Tag::Strong) | Event::Start(Tag::Emphasis) => {
                bold = true;
            }
            Event::End(Tag::Strong) | Event::End(Tag::Emphasis) => {
                bold = false;
            }
            Event::SoftBreak | Event::HardBreak => {
                flush_spans(&mut current, &mut lines);
            }
            Event::End(Tag::Paragraph) | Event::End(Tag::Heading(..)) => {
                flush_spans(&mut current, &mut lines);
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
