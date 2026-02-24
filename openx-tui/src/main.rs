//! Terminal lifecycle, event loop, and cleanup for the OpenX TUI.

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
    // Initialise structured logging (RUST_LOG controls the filter).
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::from_default_env().add_directive("openx_tui=info".parse()?),
        )
        .with_target(false)
        .init();

    let base_url =
        std::env::var("OPENX_BASE_URL").unwrap_or_else(|_| "http://127.0.0.1:8000".into());

    // Set up the terminal in raw / alternate-screen mode.
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, DisableMouseCapture)?;
    let mut terminal = Terminal::new(CrosstermBackend::new(stdout))?;
    terminal.show_cursor()?;

    let mut app = App::new(BackendClient::new(base_url));
    app.bootstrap();

    let result = run_loop(&mut terminal, &mut app);

    // Always restore the terminal, even on error.
    let _ = disable_raw_mode();
    let _ = execute!(terminal.backend_mut(), LeaveAlternateScreen);
    let _ = terminal.show_cursor();

    result
}

fn run_loop(
    terminal: &mut Terminal<CrosstermBackend<io::Stdout>>,
    app: &mut App,
) -> Result<()> {
    loop {
        app.tick = app.tick.wrapping_add(1);
        app.poll_results();

        if app.should_quit {
            return Ok(());
        }

        let tick = app.tick;
        terminal.draw(|frame| ui::render(frame, app, tick))?;

        if event::poll(TICK_RATE)? {
            if let Event::Key(key) = event::read()? {
                let action = key_to_action(
                    &key,
                    app.state.palette.visible,
                    app.input_has_focus(),
                    app.state.input_buffer.is_empty(),
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
