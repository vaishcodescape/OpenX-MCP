//! Shared utilities (output formatting, command normalization).

use serde_json::Value;

pub fn format_output(value: Option<Value>) -> String {
    match value {
        None => "(no output)".to_string(),
        Some(Value::String(s)) => s,
        Some(v) => serde_json::to_string_pretty(&v).unwrap_or_else(|_| "(invalid json)".into()),
    }
}

/// Slash command to internal command name.
const SLASH_MAP: &[(&str, &str)] = &[
    ("/help", "help"),
    ("/tools", "tools"),
    ("/schema", "schema"),
    ("/call", "call"),
    ("/analyzerepo", "analyze_repo"),
    ("/listrepos", "list_repos"),
    ("/listprs", "list_prs"),
    ("/getpr", "get_pr"),
    ("/commentpr", "comment_pr"),
    ("/mergepr", "merge_pr"),
    ("/listworkflows", "list_workflows"),
    ("/triggerworkflow", "trigger_workflow"),
    ("/listworkflowruns", "list_workflow_runs"),
    ("/getworkflowrun", "get_workflow_run"),
    ("/getfailingprs", "get_failing_prs"),
    ("/getcilogs", "get_ci_logs"),
    ("/analyzecifailure", "analyze_ci_failure"),
    ("/locatecodecontext", "locate_code_context"),
    ("/generatefixpatch", "generate_fix_patch"),
    ("/applyfixtopr", "apply_fix_to_pr"),
    ("/rerunci", "rerun_ci"),
    ("/chat", "chat"),
    ("/ask", "chat"),
    ("/index", "index"),
    ("/reset", "reset"),
];

pub fn normalize_slash_command(raw: &str) -> String {
    let raw = raw.trim();
    if !raw.starts_with('/') {
        return raw.to_string();
    }
    let parts: Vec<&str> = raw.splitn(2, char::is_whitespace).collect();
    let head = parts[0].to_lowercase();
    let tail = parts.get(1).map(|s| s.trim()).unwrap_or("");
    let mapped = SLASH_MAP
        .iter()
        .find(|(k, _)| *k == head)
        .map(|(_, v)| *v)
        .unwrap_or(head.trim_start_matches('/'));
    format!("{} {}", mapped, tail).trim().to_string()
}
