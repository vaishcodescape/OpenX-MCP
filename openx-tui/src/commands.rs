//! Command registry: fuzzy filter for palette (commands from backend).

use crate::state::PaletteState;
use fuzzy_matcher::FuzzyMatcher;
use fuzzy_matcher::skim::SkimMatcherV2;

/// Update palette filtered list from query (fuzzy match on name + description).
pub fn update_palette_filter(palette: &mut PaletteState) {
    let query = palette.query.trim().to_lowercase();
    if query.is_empty() {
        palette.filtered = (0..palette.commands.len()).collect();
    } else {
        let matcher = SkimMatcherV2::default();
        let mut scored: Vec<(i64, usize)> = palette
            .commands
            .iter()
            .enumerate()
            .filter_map(|(i, c)| {
                let name_score = matcher.fuzzy_match(&c.name.to_lowercase(), &query);
                let desc_score = matcher.fuzzy_match(&c.description.to_lowercase(), &query);
                let score = name_score.or(desc_score).map(|s| (s as i64, i));
                score
            })
            .collect();
        scored.sort_by(|a, b| b.0.cmp(&a.0));
        palette.filtered = scored.into_iter().map(|(_, i)| i).collect();
    }
    palette.selected_index = 0;
}
