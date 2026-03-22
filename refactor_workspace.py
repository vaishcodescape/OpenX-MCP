import re

with open("openx-agent/workspace.py", "r") as f:
    content = f.read()

# Remove _WS_EXECUTOR
content = re.sub(r'_WS_EXECUTOR = ThreadPoolExecutor\(max_workers=4, thread_name_prefix="workspace"\)\n', '', content)
content = re.sub(r'from concurrent\.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError\n', '', content)

# Replace _git to run synchronously
def replace_git(match):
    return """def _git(repo_path: str, *args: str) -> str:
    cwd = _resolve(repo_path)
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"git {' '.join(args)} timed out")"""

content = re.sub(r'def _git\(repo_path: str, \*args: str\) -> str:.*?raise TimeoutError\(f"git \{\' \'\.join\(args\)\} timed out"\)', replace_git, content, flags=re.DOTALL)

with open("openx-agent/workspace.py", "w") as f:
    f.write(content)
