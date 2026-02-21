//! UI layer: layout, theme, markdown, renderer, widgets.

mod layout;
mod markdown;
mod renderer;
mod theme;

pub mod widgets;

pub use renderer::render;
