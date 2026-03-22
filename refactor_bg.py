import re

with open("openx-agent/github_client.py", "r") as f:
    content = f.read()

# Remove def _bg
content = re.sub(r'def _bg\(func, \*args, timeout=30, \*\*kwargs\):\n\s+""".*?"""\n\s+return gh_cli.run_in_background\(func, \*args, timeout=timeout, \*\*kwargs\)\n\n\n', '', content, flags=re.DOTALL)

# Replace def _do(): and return _bg(_do)
def replace_do(match):
    body = match.group(1)
    # unindent body by 4 spaces
    body = '\n'.join(line[4:] if line.startswith('    ') else line for line in body.split('\n'))
    return body

content = re.sub(r'    def _do\(\):\n(.*?)\n    return _bg\(_do\)', replace_do, content, flags=re.DOTALL)

with open("openx-agent/github_client.py", "w") as f:
    f.write(content)
