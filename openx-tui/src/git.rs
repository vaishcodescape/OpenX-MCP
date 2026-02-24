//! Git helpers: current branch name and unstaged diff preview.

use std::process::Command;

/// Return the current git branch name, or a fallback string on error.
pub fn git_branch() -> String {
    run_git(&["rev-parse", "--abbrev-ref", "HEAD"])
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "no-git".into())
}

/// Return up to `max_lines` lines of `git diff`, or `"No unstaged diff"`.
#[allow(dead_code)]
pub fn git_diff_preview(max_lines: usize) -> String {
    run_git(&["diff", "--"])
        .filter(|s| !s.is_empty())
        .map(|s| s.lines().take(max_lines).collect::<Vec<_>>().join("\n"))
        .unwrap_or_else(|| "No unstaged diff".into())
}

/// Run a git subcommand and return trimmed stdout, or `None` on failure.
fn run_git(args: &[&str]) -> Option<String> {
    let out = Command::new("git").args(args).output().ok()?;
    if out.status.success() {
        Some(String::from_utf8_lossy(&out.stdout).trim().to_string())
    } else {
        None
    }
}
