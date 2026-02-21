//! Command palette: IDE-style list with accent bar selection.

use ratatui::{
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, BorderType, Paragraph},
    Frame,
};

use crate::state::PaletteState;
use crate::ui::theme::colors;

const MAX_PALETTE_HEIGHT: usize = 14;

pub fn render(f: &mut Frame, palette: &PaletteState, area: ratatui::prelude::Rect) {
    if !palette.visible || palette.filtered.is_empty() {
        return;
    }
    let block = Block::default()
        .title("  Commands  ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(Style::default().fg(colors::BORDER))
        .style(Style::default().bg(colors::ELEVATED));
    let inner = block.inner(area);
    f.render_widget(block, area);

    let take = (inner.height as usize).min(MAX_PALETTE_HEIGHT);
    let lines: Vec<Line> = palette
        .filtered
        .iter()
        .take(take)
        .enumerate()
        .map(|(i, &idx)| {
            let cmd = &palette.commands[idx];
            let selected = i == palette.selected_index;
            Line::from(vec![
                Span::styled(
                    if selected { "▎ " } else { "  " },
                    Style::default().fg(colors::ACCENT),
                ),
                Span::styled(
                    cmd.name.as_str(),
                    if selected {
                        Style::default().fg(colors::TEXT).add_modifier(Modifier::BOLD)
                    } else {
                        Style::default().fg(colors::TEXT_DIM)
                    },
                ),
                Span::raw("  "),
                Span::styled(
                    cmd.description.as_str(),
                    Style::default().fg(if selected { colors::TEXT_DIM } else { colors::MUTED }),
                ),
            ])
        })
        .collect();
    let para = Paragraph::new(lines);
    f.render_widget(para, inner);
}
