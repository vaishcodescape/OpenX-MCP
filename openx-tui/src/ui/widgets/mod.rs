//! TUI widgets: chat, input, status, command palette.

mod chat;
mod input;
mod palette;
mod status;

pub use chat::render as render_chat;
pub use input::render as render_input;
pub use palette::render as render_palette;
pub use status::render as render_status;
