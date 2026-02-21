//! Single-panel render: chat, input bar, status, optional palette overlay.

use ratatui::layout::Rect;
use ratatui::Frame;

use crate::app::App;
use crate::ui::layout;
use crate::ui::theme::SPINNER;
use crate::ui::widgets::{render_chat, render_input, render_palette, render_status};

const PALETTE_OVERLAY_HEIGHT: u16 = 14;

pub fn render(f: &mut Frame, app: &App, tick: usize) {
    let area = f.area();
    let regions = layout::compute(area);

    let spinner_char = SPINNER[tick % SPINNER.len()];

    render_chat(
        f,
        &app.state.chat,
        regions.chat,
        app.state.loading,
        spinner_char,
    );
    render_input(
        f,
        app.state.input_buffer(),
        app.state.input_cursor(),
        regions.input,
    );
    render_status(f, regions.status, app.state.loading, spinner_char);

    if app.state.palette.visible {
        let palette_area = Rect {
            x: area.x,
            y: area.y + area.height.saturating_sub(PALETTE_OVERLAY_HEIGHT + 2),
            width: area.width,
            height: PALETTE_OVERLAY_HEIGHT,
        };
        render_palette(f, &app.state.palette, palette_area);
    }
}
