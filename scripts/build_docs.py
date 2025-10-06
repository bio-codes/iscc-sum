"""Copy README.md and CHANGELOG.md to documentation"""

from __future__ import annotations

import re
from os.path import abspath, dirname, join

HERE = dirname(abspath(__file__))
README_SRC = join(HERE, "../README.md")
README_DST = join(HERE, "../docs/developers.md")
CHANGELOG_SRC = join(HERE, "../CHANGELOG.md")
CHANGELOG_DST = join(HERE, "../docs/changelog.md")


def convert_github_alerts_to_admonitions(text):
    # type: (str) -> str
    """Convert GitHub-style alerts to mkdocs-material admonitions."""
    # Map GitHub alert types to mkdocs-material admonition types
    alert_mapping = {
        "NOTE": "note",
        "TIP": "tip",
        "IMPORTANT": "important",
        "WARNING": "warning",
        "CAUTION": "danger",
    }

    # Pattern to match GitHub alerts
    # Matches: > [!TYPE] followed by content lines starting with >
    pattern = r"> \[!(" + "|".join(alert_mapping.keys()) + r")\]\n((?:> .*\n)*)"

    def replace_alert(match):
        # type: (re.Match) -> str
        """Replace a single GitHub alert with mkdocs-material admonition."""
        alert_type = match.group(1)
        content_lines = match.group(2)

        # Get the corresponding admonition type
        admonition_type = alert_mapping[alert_type]

        # Remove the leading "> " from each content line and strip trailing newline
        content = content_lines.replace("> ", "").rstrip("\n")

        # Build the admonition
        # Replace newlines with indented newlines
        indented_content = content.replace("\n", "\n    ")
        return f"!!! {admonition_type}\n\n    {indented_content}\n"

    return re.sub(pattern, replace_alert, text)


def main():
    """Copy root files to documentation site."""
    # Copy README.md to developers.md
    with open(README_SRC, "rt", encoding="utf-8") as infile:
        text = infile.read()

    # Convert GitHub alerts to mkdocs-material admonitions
    text = convert_github_alerts_to_admonitions(text)

    with open(README_DST, "wt", encoding="utf-8", newline="\n") as outf:
        outf.write(text)

    # Copy CHANGELOG.md to changelog.md
    with open(CHANGELOG_SRC, "rt", encoding="utf-8") as infile:
        changelog_text = infile.read()

    # Convert GitHub alerts in changelog if any
    changelog_text = convert_github_alerts_to_admonitions(changelog_text)

    with open(CHANGELOG_DST, "wt", encoding="utf-8", newline="\n") as outf:
        outf.write(changelog_text)


if __name__ == "__main__":
    main()
