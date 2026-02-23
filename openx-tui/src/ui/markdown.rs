//! Markdown to ratatui Line/Spans: headings, syntax-highlighted code blocks,
//! inline code, bold, lists, horizontal rules. Codex-style formatting.

use pulldown_cmark::{CodeBlockKind, Event, Options, Parser, Tag};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use syntect::easy::HighlightLines;
use syntect::highlighting::{FontStyle, ThemeSet};
use syntect::parsing::SyntaxSet;
use syntect::util::LinesWithEndings;
use std::sync::OnceLock;

use super::theme::colors;

/// Body text in markdown — white for maximum visibility.
const MD_TEXT: Color = Color::White;

/// SyntaxSet and ThemeSet loaded once for syntax highlighting.
fn syntax_set() -> &'static SyntaxSet {
    static PS: OnceLock<SyntaxSet> = OnceLock::new();
    PS.get_or_init(SyntaxSet::load_defaults_newlines)
}

fn theme_set() -> &'static ThemeSet {
    static TS: OnceLock<ThemeSet> = OnceLock::new();
    TS.get_or_init(ThemeSet::load_defaults)
}

/// Convert syntect highlighting Style to ratatui Style (for syntax-highlighted spans).
fn syntect_style_to_ratatui(
    s: &syntect::highlighting::Style,
    code_bg: Color,
) -> ratatui::style::Style {
    let fg = if s.foreground.a > 0 {
        Some(Color::Rgb(s.foreground.r, s.foreground.g, s.foreground.b))
    } else {
        None
    };
    let bg = if s.background.a > 0 {
        Color::Rgb(s.background.r, s.background.g, s.background.b)
    } else {
        code_bg
    };
    let mut modifier = Modifier::empty();
    if s.font_style.contains(FontStyle::BOLD) {
        modifier.insert(Modifier::BOLD);
    }
    if s.font_style.contains(FontStyle::ITALIC) {
        modifier.insert(Modifier::ITALIC);
    }
    if s.font_style.contains(FontStyle::UNDERLINE) {
        modifier.insert(Modifier::UNDERLINED);
    }
    Style::default()
        .fg(fg.unwrap_or(MD_TEXT))
        .bg(bg)
        .add_modifier(modifier)
}

/// Map markdown code block language to syntect extension.
fn lang_to_ext(lang: &str) -> &'static str {
    match lang.trim().to_lowercase().as_str() {
        "python" | "py" => "py",
        "rust" | "rs" => "rs",
        "javascript" | "js" => "js",
        "typescript" | "ts" => "ts",
        "tsx" => "tsx",
        "jsx" => "jsx",
        "go" => "go",
        "java" => "java",
        "ruby" | "rb" => "rb",
        "csharp" | "cs" | "c#" => "cs",
        "cpp" | "c++" => "cpp",
        "c" => "c",
        "h" => "h",
        "hpp" => "hpp",
        "sql" => "sql",
        "bash" | "sh" | "shell" => "sh",
        "yaml" | "yml" => "yml",
        "json" => "json",
        "toml" => "toml",
        "html" => "html",
        "css" => "css",
        "markdown" | "md" => "md",
        _ => "txt",
    }
}

/// Render a single code block with optional syntax highlighting. Pushes Codex-style
/// box (top/bottom border, left gutter) and highlighted lines.
fn push_code_block(lines: &mut Vec<Line<'static>>, code_lines: &[String], lang: Option<&str>) {
    let gutter = Span::styled(
        " ┃ ",
        Style::default()
            .fg(colors::BORDER)
            .bg(colors::CODE_BG),
    );
    let blank_line = Line::from(Span::raw(""));

    // Top border — Codex-style
    lines.push(Line::from(vec![
        Span::styled(
            " ┌─",
            Style::default()
                .fg(colors::BORDER)
                .bg(colors::CODE_BG),
        ),
        Span::styled(
            " ".repeat(2),
            Style::default().bg(colors::CODE_BG),
        ),
    ]));

    let (syntax, theme) = if let Some(l) = lang {
        let ext = lang_to_ext(l);
        let ps = syntax_set();
        let ts = theme_set();
        let syn = ps
            .find_syntax_by_extension(ext)
            .or_else(|| Some(ps.find_syntax_plain_text()));
        let th = ["base16-ocean.dark", "InspiredGitHub", "Solarized (dark)"]
            .into_iter()
            .find_map(|name| ts.themes.get(name))
            .or_else(|| ts.themes.values().next());
        match (syn, th) {
            (Some(s), Some(t)) => (Some(s), Some(t)),
            _ => (None, None),
        }
    } else {
        (None, None)
    };

    if let (Some(syntax), Some(theme)) = (syntax, theme) {
        let mut highlighter = HighlightLines::new(syntax, theme);
        let ps = syntax_set();
        for code_line in code_lines {
            let with_newline = format!("{}\n", code_line);
            for line in LinesWithEndings::from(&with_newline) {
                let mut spans = vec![gutter.clone()];
                match highlighter.highlight_line(line, ps) {
                    Ok(ranges) => {
                        for (style, s) in ranges {
                            let rt_style =
                                syntect_style_to_ratatui(&style, colors::CODE_BG);
                            spans.push(Span::styled(s.to_string(), rt_style));
                        }
                    }
                    _ => {
                        spans.push(Span::styled(
                            line.trim_end_matches('\n').to_string(),
                            Style::default()
                                .fg(MD_TEXT)
                                .bg(colors::CODE_BG),
                        ));
                    }
                }
                lines.push(Line::from(spans));
            }
        }
    } else {
        for line in code_lines {
            lines.push(Line::from(vec![
                gutter.clone(),
                Span::styled(
                    line.clone(),
                    Style::default()
                        .fg(MD_TEXT)
                        .bg(colors::CODE_BG),
                ),
            ]));
        }
    }

    // Bottom border
    lines.push(Line::from(Span::styled(
        " └",
        Style::default()
            .fg(colors::BORDER)
            .bg(colors::CODE_BG),
    )));
    lines.push(blank_line);
}

/// Convert markdown string to a list of Lines (owned, no lifetime).
pub fn to_lines(md: &str) -> Vec<Line<'static>> {
    let mut lines: Vec<Line<'static>> = Vec::new();
    let mut current: Vec<Span<'static>> = Vec::new();
    let mut in_code_block = false;
    let mut code_block_lines: Vec<String> = Vec::new();
    let mut code_block_lang: Option<String> = None;
    let mut bold = false;
    let mut in_heading = false;
    let mut list_depth: usize = 0;
    let mut ordered_index: Option<u64> = None;
    let opts = Options::all();

    for event in Parser::new_ext(md, opts) {
        match event {
            // ── Code blocks (with optional language for syntax highlighting) ──
            Event::Start(Tag::CodeBlock(CodeBlockKind::Fenced(lang))) => {
                flush_spans(&mut current, &mut lines);
                in_code_block = true;
                code_block_lines.clear();
                code_block_lang = Some(lang.to_string());
            }
            Event::End(Tag::CodeBlock(_)) => {
                if in_code_block {
                    push_code_block(
                        &mut lines,
                        &code_block_lines,
                        code_block_lang.as_deref(),
                    );
                    in_code_block = false;
                    code_block_lang = None;
                }
            }

            // ── Headings ─────────────────────────────────────────
            Event::Start(Tag::Heading(level, _, _)) => {
                flush_spans(&mut current, &mut lines);
                in_heading = true;
                let prefix = match level {
                    pulldown_cmark::HeadingLevel::H1 => "# ",
                    pulldown_cmark::HeadingLevel::H2 => "## ",
                    pulldown_cmark::HeadingLevel::H3 => "### ",
                    _ => "#### ",
                };
                current.push(Span::styled(
                    prefix.to_string(),
                    Style::default()
                        .fg(colors::HEADING)
                        .add_modifier(Modifier::BOLD),
                ));
            }
            Event::End(Tag::Heading(_, _, _)) => {
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
                    Style::default()
                        .fg(colors::ACCENT)
                        .bg(colors::CODE_BG),
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
