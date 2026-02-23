//! OpenX TUI — terminal lifecycle and event loop.

mod actions;
mod app;
mod backend;
mod commands;
mod events;
mod git;
mod services;
mod state;
mod ui;

use std::io;

use anyhow::Result;
use crossterm::{
    event::{self, DisableMouseCapture, Event},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{backend::CrosstermBackend, Terminal};
use tracing_subscriber::EnvFilter;

use app::App;
use backend::BackendClient;
use events::{key_to_action, TICK_RATE};

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("openx_tui=info".parse()?))
        .with_target(false)
        .init();

    let base_url =
        std::env::var("OPENX_BASE_URL").unwrap_or_else(|_| "http://127.0.0.1:8000".to_string());
    let client = BackendClient::new(base_url);

    enable_raw_mode().map_err(anyhow::Error::msg)?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, DisableMouseCapture).map_err(anyhow::Error::msg)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend).map_err(anyhow::Error::msg)?;

    let mut app = App::new(client);
    app.bootstrap();

    // Ensure cursor is visible for input (some terminals hide it in raw mode).
    let _ = terminal.show_cursor();

    let result = run_loop(&mut terminal, &mut app);

    disable_raw_mode().map_err(anyhow::Error::msg)?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen).map_err(anyhow::Error::msg)?;
    terminal.show_cursor().map_err(anyhow::Error::msg)?;

    result
}

fn run_loop(
    terminal: &mut Terminal<CrosstermBackend<io::Stdout>>,
    app: &mut App,
) -> Result<()> {
    loop {
        app.tick = app.tick.wrapping_add(1);
        let tick = app.tick;
        terminal.draw(|f| ui::render(f, &*app, tick))?;

        if event::poll(TICK_RATE).map_err(anyhow::Error::msg)? {
            let ev = event::read().map_err(anyhow::Error::msg)?;
            // Ignore mouse events so scroll wheel doesn't affect the app.
            if let Event::Key(key) = ev {
                let input_empty = app.state.input_buffer().is_empty();
                let action = key_to_action(
                    &key,
                    app.state.palette.visible,
                    app.input_has_focus(),
                    input_empty,
                );
                if let Some(a) = action {
                    app.dispatch(a);
                    if app.should_quit {
                        return Ok(());
                    }
                }
            }
        }
    }
}
