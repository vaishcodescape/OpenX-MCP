//! Single-panel render: chat, input bar, status, optional palette overlay.

use ratatui::layout::Rect;
use ratatui::Frame;

use crate::app::App;
use crate::ui::layout;
use crate::ui::theme::SPINNER;
use crate::ui::widgets::{render_chat, render_input, render_palette, render_status};

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
        app.input_has_focus(),
    );
    render_status(
        f,
        regions.status,
        app.state.loading,
        spinner_char,
        &app.git_branch,
        app.connected,
        app.input_has_focus(),
    );

    if app.state.palette.visible {
        // Overlay palette inside the chat area (bottom of chat region).
        let max_palette_h = regions.chat.height.saturating_sub(2).min(16);
        let palette_area = Rect {
            x: regions.chat.x,
            y: regions.chat.y + regions.chat.height.saturating_sub(max_palette_h),
            width: regions.chat.width,
            height: max_palette_h,
        };
        render_palette(f, &app.state.palette, palette_area);
    }
}
