//! Git helpers: branch name and unstaged diff.

use std::process::Command;

#[allow(dead_code)]
pub fn git_branch() -> String {
    let out = Command::new("git")
        .args(["rev-parse", "--abbrev-ref", "HEAD"])
        .output();
    match out {
        Ok(o) if o.status.success() => {
            let s = String::from_utf8_lossy(&o.stdout).trim().to_string();
            if s.is_empty() {
                "detached".into()
            } else {
                s
            }
        }
        _ => "no-git".into(),
    }
}

#[allow(dead_code)]
pub fn git_diff_preview(max_lines: usize) -> String {
    let out = Command::new("git").args(["diff", "--"]).output();
    match out {
        Ok(o) if o.status.success() => {
            let s = String::from_utf8_lossy(&o.stdout);
            let lines: Vec<&str> = s.lines().take(max_lines).collect();
            if lines.is_empty() {
                "No unstaged diff".into()
            } else {
                lines.join("\n")
            }
        }
        _ => "No unstaged diff".into(),
    }
}
