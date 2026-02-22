//! TUI widgets: header, chat, input, status, command palette.

mod chat;
mod header;
mod input;
mod palette;
mod status;

pub use chat::render as render_chat;
pub use header::render as render_header;
pub use input::render as render_input;
pub use palette::render as render_palette;
pub use status::render as render_status;
