"""
Location: src/transpiler_pro/utils/logger.py
Description: Dynamic Logging Utility with Clickable Links and SUSE Style Guide Integration.
"""

import os
from pathlib import Path
from datetime import datetime

class AuditLogger:
    def __init__(self, log_dir="data/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # Unique log per run
        self.log_file = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
        # Official SUSE Style Guide URL
        self.guide_url = "https://documentation.suse.com/style/current/html/style-guide-adoc/index.html"
        self._prepare_log()

    def _prepare_log(self):
        if not self.log_file.exists():
            header = (
                "# 🛡️ Style Guide Audit Report\n\n"
                f"**Run Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                "| Clickable Source | Severity | Rule | Message | Action & Reference |\n"
                "| :--- | :--- | :--- | :--- | :--- |\n"
            )
            self.log_file.write_text(header)

    def log_issue(self, file_path, line, severity, message, rule_id):
        """
        Logs a violation with an absolute clickable URI and dynamic documentation link.
        """
        # 1. Paths for Display vs. Paths for Linking
        abs_path = os.path.abspath(file_path)
        try:
            rel_display_path = os.path.relpath(file_path, os.getcwd())
        except Exception:
            rel_display_path = file_path

        # 2. Format Clickable URI
        # Using file:// protocol with absolute paths is the most reliable way 
        # to ensure VS Code opens the file at the specific line.
        clickable_uri = f"file://{abs_path}#L{line}"
        clickable_source = f"[`{rel_display_path}:{line}`]({clickable_uri})"
        
        # 3. Generate Style Guide Reference Link
        safe_rule_id = str(rule_id) if rule_id else "Style.General"
        anchor = safe_rule_id.lower()
        doc_link = f"[📖 Guide Reference]({self.guide_url}#{anchor})"
        
        # 4. Derive Action Message
        action_desc = self._derive_dynamic_action(safe_rule_id, message)
        
        # 5. Build Final Table Row
        action_column = f"{action_desc} <br/> {doc_link}"
        
        row = f"| {clickable_source} | {severity} | `{safe_rule_id}` | {message} | {action_column} |\n"
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(row)

    def _derive_dynamic_action(self, rule_id, message):
        """Logic-based recommendation engine."""
        parts = rule_id.split('.')
        style_group = parts[0] if len(parts) > 1 else "General"
        
        if "Spelling" in rule_id:
            # Safely extract word from message like "Did you mean 'wifi'?"
            word = message.split("'")[1] if "'" in message else "term"
            return f"**Verify spelling of '{word}'.** If valid, add to `knowledge_base.json`."
        
        if style_group == "asciidoc":
            return "**Structural Issue.** Check AsciiDoc syntax requirements for this block."
            
        if style_group == "common" or style_group == "SUSE":
            return "**Style violation.** Adjust sentence for tone, clarity, or capitalization."

        return "**Manual Review Required.** Refer to the linked documentation."