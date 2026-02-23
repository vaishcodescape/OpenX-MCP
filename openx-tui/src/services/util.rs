//! Shared utilities (output formatting, command normalization).

use serde_json::Value;

#[allow(dead_code)]
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
    ("/h", "help"),
    ("/?", "help"),
    ("/tools", "tools"),
    ("/schema", "schema"),
    ("/call", "call"),
    ("/analyze", "analyze_repo"),
    ("/analyzerepo", "analyze_repo"),
    ("/repos", "list_repos"),
    ("/listrepos", "list_repos"),
    ("/prs", "list_prs"),
    ("/listprs", "list_prs"),
    ("/pr", "get_pr"),
    ("/getpr", "get_pr"),
    ("/issues", "list_issues"),
    ("/listissues", "list_issues"),
    ("/issue", "get_issue"),
    ("/getissue", "get_issue"),
    ("/newissue", "create_issue"),
    ("/createissue", "create_issue"),
    ("/commentissue", "comment_issue"),
    ("/closeissue", "close_issue"),
    ("/comment", "comment_pr"),
    ("/commentpr", "comment_pr"),
    ("/merge", "merge_pr"),
    ("/mergepr", "merge_pr"),
    ("/readme", "get_readme"),
    ("/getreadme", "get_readme"),
    ("/updatereadme", "update_readme"),
    ("/workflows", "list_workflows"),
    ("/listworkflows", "list_workflows"),
    ("/trigger", "trigger_workflow"),
    ("/triggerworkflow", "trigger_workflow"),
    ("/runs", "list_workflow_runs"),
    ("/listworkflowruns", "list_workflow_runs"),
    ("/run", "get_workflow_run"),
    ("/getworkflowrun", "get_workflow_run"),
    ("/failing", "get_failing_prs"),
    ("/getfailingprs", "get_failing_prs"),
    ("/heal", "heal_ci"),
    ("/healci", "heal_ci"),
    ("/healfailingpr", "heal_ci"),
    ("/logs", "get_ci_logs"),
    ("/getcilogs", "get_ci_logs"),
    ("/analyze-failure", "analyze_ci_failure"),
    ("/analyzecifailure", "analyze_ci_failure"),
    ("/context", "locate_code_context"),
    ("/locatecodecontext", "locate_code_context"),
    ("/patch", "generate_fix_patch"),
    ("/generatefixpatch", "generate_fix_patch"),
    ("/apply", "apply_fix_to_pr"),
    ("/applyfixtopr", "apply_fix_to_pr"),
    ("/rerun", "rerun_ci"),
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
