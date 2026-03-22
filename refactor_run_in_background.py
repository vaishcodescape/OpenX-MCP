import re

# 1. Update github_client.py
with open("openx-agent/github_client.py", "r") as f:
    content = f.read()

content = re.sub(r'gh_cli\.run_in_background\(gh_cli\.([a-zA-Z0-9_]+),\s*(.*?)\)', r'gh_cli.\1(\2)', content)
with open("openx-agent/github_client.py", "w") as f:
    f.write(content)

# 2. Update tools/github.py
with open("openx-agent/tools/github.py", "r") as f:
    content = f.read()

content = content.replace('from ..gh_cli import run_gh_command as _run_gh_command, run_in_background', 'from ..gh_cli import run_gh_command as _run_gh_command')
content = content.replace('output = run_in_background(_run_gh_command, cmd, timeout=30)', 'output = _run_gh_command(cmd, timeout=30)')

with open("openx-agent/tools/github.py", "w") as f:
    f.write(content)

# 3. Update gh_cli.py
with open("openx-agent/gh_cli.py", "r") as f:
    content = f.read()

# Remove run_in_background and _EXECUTOR
content = re.sub(r'_EXECUTOR = ThreadPoolExecutor\(max_workers=10, thread_name_prefix="gh_cli"\)\n', '', content)
content = re.sub(r'def run_in_background\(.*?\n\s+except FuturesTimeoutError:\n\s+raise TimeoutError\(.*?\n', '', content, flags=re.DOTALL)

with open("openx-agent/gh_cli.py", "w") as f:
    f.write(content)

