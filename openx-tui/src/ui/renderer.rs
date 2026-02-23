//! Single-panel render: chat, input bar, status, optional palette overlay.

use ratatui::Frame;

use crate::app::App;
use crate::ui::layout;
use crate::ui::theme::{OPENX_LOADING_FRAMES, SPINNER};
use crate::ui::widgets::{render_chat, render_header, render_input, render_palette, render_status};

pub fn render(f: &mut Frame, app: &App, tick: usize) {
    let area = f.area();
    let regions = layout::compute(area);

    let spinner_char = SPINNER[tick % SPINNER.len()];
    let openx_loading_frame = OPENX_LOADING_FRAMES[tick % OPENX_LOADING_FRAMES.len()];

    render_header(f, regions.header);
    render_chat(
        f,
        &app.state.chat,
        regions.chat,
        app.state.loading,
        spinner_char,
        openx_loading_frame,
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
        render_palette(f, &app.state.palette, layout::palette_overlay_rect(regions.chat));
    }
}
