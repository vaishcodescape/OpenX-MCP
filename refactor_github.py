import re

with open("openx-agent/github_client.py", "r") as f:
    content = f.read()

content = re.sub(r'def _load_github\(\) -> Any:\n\s+try:\n\s+from github import Github  # type: ignore\n\s+except ImportError as exc:\n\s+raise RuntimeError\(\n\s+"PyGithub is not installed. Run `pip install -r requirements.txt`."\n\s+\) from exc\n\s+return Github\n\n\n', '', content)
content = content.replace('Github = _load_github()', 'from github import Github')

with open("openx-agent/github_client.py", "w") as f:
    f.write(content)
