//! Header banner: OpenX TUI title, version, directory — colored box.

use ratatui::{
    text::{Line, Span},
    widgets::Paragraph,
    Frame,
};

use crate::ui::theme::styles;

const VERSION: &str = env!("CARGO_PKG_VERSION");
const HELP_HINT: &str = " /help ";
const DIR_LABEL: &str = "directory: ";
/// Reserve +1 for ⚡ (wide in terminal) so "/help" doesn't clip.
const EMOJI_WIDTH_SLOP: usize = 1;

/// Truncate to `max_chars` from the end with ellipsis. Single pass over chars.
fn truncate_end(s: &str, max_chars: usize) -> String {
    let count = s.chars().count();
    if count <= max_chars {
        return s.to_string();
    }
    let take = max_chars.saturating_sub(1);
    let skip = count.saturating_sub(take);
    format!("…{}", s.chars().skip(skip).collect::<String>())
}

pub fn render(f: &mut Frame, area: ratatui::prelude::Rect) {
    let dir = std::env::current_dir()
        .ok()
        .and_then(|p| p.into_os_string().into_string().ok())
        .unwrap_or_else(|| "—".to_string());

    let w = area.width.saturating_sub(3) as usize;
    let inner = w.saturating_sub(4);

    let top_line = format!("{}{}", "─".repeat(w), "╮");
    let bottom_line = format!("╰{}{}", "─".repeat(w.saturating_sub(1)), "╯");
    let empty_line = format!("  │{}│", " ".repeat(inner));

    let title_content = format!("⚡ OpenX (v{VERSION})");
    let title_len = title_content.chars().count();
    let help_len = HELP_HINT.chars().count();
    let pad = inner.saturating_sub(title_len + 1 + help_len + EMOJI_WIDTH_SLOP);

    let dir_max = inner.saturating_sub(DIR_LABEL.chars().count());
    let dir_show = truncate_end(&dir, dir_max);
    let line3_content_len = DIR_LABEL.chars().count() + dir_show.chars().count();
    let line3_pad = inner.saturating_sub(line3_content_len);

    let border = styles::border();
    let lines = vec![
        Line::from(vec![
            Span::styled("  ", border),
            Span::styled(top_line, border),
        ]),
        Line::from(vec![
            Span::styled("  │ ", border),
            Span::styled("⚡ ", styles::accent_bold()),
            Span::styled("OpenX ", styles::openx_orange_bold()),
            Span::styled(format!("(v{VERSION})"), styles::text_dim()),
            Span::styled(" ".repeat(pad), ratatui::style::Style::default()),
            Span::styled(HELP_HINT, styles::muted()),
            Span::styled("│", border),
        ]),
        Line::from(vec![Span::styled(empty_line, border)]),
        Line::from(vec![
            Span::styled("  │ ", border),
            Span::styled(DIR_LABEL, styles::text_dim()),
            Span::styled(dir_show, styles::openx_role()),
            Span::styled(" ".repeat(line3_pad), ratatui::style::Style::default()),
            Span::styled("│", border),
        ]),
        Line::from(vec![
            Span::styled("  ", border),
            Span::styled(bottom_line, border),
        ]),
    ];

    let para = Paragraph::new(lines).style(styles::elevated_bg());
    f.render_widget(para, area);
}
