import re


class Sanitizer:
    PATTERNS = [
        (re.compile(r"(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token)['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?"), r"\1: [REDACTED]"),
        (re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]+"), "Bearer [REDACTED]"),
        (re.compile(r"(?i)password['\"]?\s*[:=]\s*['\"]?[^\s'\"]{6,}['\"]?"), "password: [REDACTED]"),
        (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[EMAIL_REDACTED]"),
        (re.compile(r"(?i)(ghp|gho|github_pat)_[a-zA-Z0-9_]{36,}"), "[GITHUB_TOKEN_REDACTED]"),
        (re.compile(r"(?i)glpat-[a-zA-Z0-9\-]{20,}"), "[GITLAB_TOKEN_REDACTED]"),
        (re.compile(r"(?i)xox[baprs]-[a-zA-Z0-9]{10,}"), "[SLACK_TOKEN_REDACTED]"),
    ]

    def clean(self, data: dict[str, str]) -> dict[str, str]:
        cleaned = {}
        for key, value in data.items():
            if not isinstance(value, str):
                cleaned[key] = value
                continue

            result = value
            for pattern, replacement in self.PATTERNS:
                result = pattern.sub(replacement, result)

            cleaned[key] = result
        return cleaned
