//! Command palette: inline list rendered directly in the chat area — no borders, no modal.

use ratatui::{
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Clear, Paragraph},
    Frame,
};

use crate::state::PaletteState;
use crate::ui::theme::colors;

pub fn render(f: &mut Frame, palette: &PaletteState, area: ratatui::prelude::Rect) {
    if !palette.visible || palette.filtered.is_empty() {
        return;
    }

    let width = area.width as usize;
    let max_items = (area.height as usize).saturating_sub(2).min(12);

    // Build lines: separator, commands, footer.
    let mut lines: Vec<Line> = Vec::new();

    // Thin separator line.
    let sep = "─".repeat(width);
    lines.push(Line::from(Span::styled(
        sep,
        Style::default().fg(colors::BORDER),
    )));

    // Header.
    let header = if palette.query.is_empty() {
        " Commands".to_string()
    } else {
        format!(" /{}", palette.query)
    };
    lines.push(Line::from(Span::styled(
        header,
        Style::default()
            .fg(colors::ACCENT)
            .add_modifier(Modifier::BOLD),
    )));

    // Command items.
    for (i, &idx) in palette.filtered.iter().take(max_items).enumerate() {
        let cmd = &palette.commands[idx];
        let selected = i == palette.selected_index;
        let (indicator_style, name_style, desc_style) = if selected {
            (
                Style::default().fg(colors::SYSTEM).add_modifier(Modifier::BOLD),
                Style::default().fg(colors::SYSTEM).add_modifier(Modifier::BOLD),
                Style::default().fg(colors::SYSTEM),
            )
        } else {
            (
                Style::default().fg(colors::MUTED),
                Style::default().fg(colors::TEXT_DIM),
                Style::default().fg(colors::MUTED),
            )
        };
        let indicator = if selected { " ▸ " } else { "   " };
        let content_len = 3 + cmd.name.len() + 2 + cmd.description.len();
        let pad = width.saturating_sub(content_len);

        lines.push(Line::from(vec![
            Span::styled(indicator, indicator_style),
            Span::styled(&cmd.name, name_style),
            Span::styled("  ", Style::default()),
            Span::styled(&cmd.description, desc_style),
            Span::styled(" ".repeat(pad), Style::default()),
        ]));
    }

    // Footer count.
    let showing = palette.filtered.len();
    let total = palette.commands.len();
    lines.push(Line::from(Span::styled(
        format!(" {} of {} commands", showing, total),
        Style::default().fg(colors::MUTED),
    )));

    // Calculate the area for these lines, anchored to the bottom of the given area.
    let line_count = lines.len() as u16;
    let render_height = line_count.min(area.height);
    let render_area = ratatui::prelude::Rect {
        x: area.x,
        y: area.y + area.height.saturating_sub(render_height),
        width: area.width,
        height: render_height,
    };

    f.render_widget(Clear, render_area);
    let para = Paragraph::new(lines).style(Style::default().bg(colors::BG));
    f.render_widget(para, render_area);
}
