from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict


def _strip_json_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    cleaned_lines = []
    for line in text.splitlines():
        if '//' in line:
            quote_open = False
            result = []
            i = 0
            while i < len(line):
                ch = line[i]
                if ch == '"' and (i == 0 or line[i - 1] != '\'):
                    quote_open = not quote_open
                if not quote_open and ch == '/' and i + 1 < len(line) and line[i + 1] == '/':
                    break
                result.append(ch)
                i += 1
            cleaned_lines.append(''.join(result))
        else:
            cleaned_lines.append(line)
    return "
".join(cleaned_lines)


def load_config(base_dir: Path) -> Dict[str, Any]:
    candidates = [base_dir / 'config.json', base_dir / 'config.jsonc']
    for config_path in candidates:
        if config_path.exists():
            raw = config_path.read_text(encoding='utf-8')
            return json.loads(_strip_json_comments(raw))
    raise FileNotFoundError('Could not find config.json or config.jsonc in the project root.')
