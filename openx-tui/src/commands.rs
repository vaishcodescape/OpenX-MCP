//! Command palette: fuzzy-filter commands from backend + built-ins.

use crate::state::PaletteState;
use fuzzy_matcher::{skim::SkimMatcherV2, FuzzyMatcher};

/// Rebuild `palette.filtered` from `palette.query` using fuzzy matching.
///
/// Scores both `name` and `description`; the best score per command wins.
/// Resets `selected_index` to 0 after every update.
pub fn update_palette_filter(palette: &mut PaletteState) {
    let query = palette.query.trim().to_lowercase();

    palette.filtered = if query.is_empty() {
        (0..palette.commands.len()).collect()
    } else {
        let matcher = SkimMatcherV2::default();
        let mut scored: Vec<(i64, usize)> = palette
            .commands
            .iter()
            .enumerate()
            .filter_map(|(i, cmd)| {
                let name_score = matcher.fuzzy_match(&cmd.name.to_lowercase(), &query);
                let desc_score = matcher.fuzzy_match(&cmd.description.to_lowercase(), &query);
                name_score.or(desc_score).map(|score| (score, i))
            })
            .collect();
        scored.sort_unstable_by(|a, b| b.0.cmp(&a.0));
        scored.into_iter().map(|(_, i)| i).collect()
    };

    palette.selected_index = 0;
}
