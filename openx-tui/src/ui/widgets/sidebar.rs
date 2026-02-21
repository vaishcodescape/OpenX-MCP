//! File tree sidebar: expandable nodes, selection highlight.

use ratatui::{
    style::{Modifier, Style},
    text::Line,
    widgets::{Block, Borders, BorderType, List, ListItem, Paragraph},
    Frame,
};
use std::path::PathBuf;

use crate::state::FileNode;
use crate::ui::theme::colors;

/// (depth, path, name, is_dir, expanded)
fn flatten_visible(node: &FileNode, depth: usize, out: &mut Vec<(usize, PathBuf, String, bool, bool)>) {
    out.push((depth, node.path.clone(), node.name.clone(), node.is_dir, node.expanded));
    if node.expanded {
        for c in &node.children {
            flatten_visible(c, depth + 1, out);
        }
    }
}

pub fn render(
    f: &mut Frame,
    root: Option<&FileNode>,
    selected_index: usize,
    area: ratatui::prelude::Rect,
    focused: bool,
) {
    let border_style = if focused {
        Style::default().fg(colors::PRIMARY)
    } else {
        Style::default().fg(colors::BORDERS)
    };
    let block = Block::default()
        .title(" Files ")
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(border_style)
        .style(Style::default().bg(colors::ELEVATED));
    let inner = block.inner(area);
    f.render_widget(block, area);

    let mut flat: Vec<(usize, PathBuf, String, bool, bool)> = Vec::new();
    if let Some(r) = root {
        flatten_visible(r, 0, &mut flat);
    }

    if flat.is_empty() {
        let p = Paragraph::new("Loading…")
            .style(Style::default().fg(colors::MUTED));
        f.render_widget(p, inner);
        return;
    }

    let items: Vec<ListItem> = flat
        .iter()
        .enumerate()
        .map(|(i, (depth, _, name, is_dir, expanded))| {
            let prefix = "  ".repeat(*depth);
            let icon = if *is_dir { if *expanded { "▾ " } else { "▸ " } } else { "  " };
            let style = if i == selected_index {
                Style::default()
                    .fg(colors::TEXT)
                    .bg(colors::BORDERS)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(colors::TEXT_DIM)
            };
            ListItem::new(Line::from(format!("{}{}{}", prefix, icon, name))).style(style)
        })
        .collect();
    let list = List::new(items);
    f.render_widget(list, inner);
}
