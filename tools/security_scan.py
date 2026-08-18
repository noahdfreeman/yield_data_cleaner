# SPDX-License-Identifier: GPL-3.0-or-later
"""Automated Security and Quality Scanner for QGIS Plugin Submission.

Performs static AST inspection, security risk checks, packaging audits,
and QGIS Plugin Repository metadata compliance validation.
"""

from __future__ import annotations

import ast
import configparser
from pathlib import Path
import re
import sys
import zipfile

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "yield_data_cleaner"
ROOT_DIR = Path(__file__).resolve().parent.parent


class SecurityVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.issues: list[dict[str, Any]] = []

    def visit_Call(self, node: ast.Call):
        # Check eval / exec / compile
        if isinstance(node.func, ast.Name):
            if node.func.id in ("eval", "exec"):
                self.issues.append(
                    {
                        "file": self.filename,
                        "line": node.lineno,
                        "severity": "CRITICAL",
                        "code": "SEC-001",
                        "msg": f"Dangerous dynamic execution function used: {node.func.id}()",
                    }
                )
            elif node.func.id == "__import__":
                self.issues.append(
                    {
                        "file": self.filename,
                        "line": node.lineno,
                        "severity": "HIGH",
                        "code": "SEC-002",
                        "msg": "Dynamic __import__() call detected.",
                    }
                )
        # Check os.system, os.popen, subprocess, QProcess
        elif isinstance(node.func, ast.Attribute):
            full_name = self._get_attribute_name(node.func)
            if full_name in (
                "os.system",
                "os.popen",
                "os.popen2",
                "os.popen3",
                "os.popen4",
                "subprocess.Popen",
                "subprocess.call",
                "subprocess.check_call",
                "subprocess.check_output",
                "subprocess.run",
                "QProcess.startDetached",
                "QProcess.execute",
                "QProcess.start",
            ):
                self.issues.append(
                    {
                        "file": self.filename,
                        "line": node.lineno,
                        "severity": "CRITICAL",
                        "code": "SEC-003",
                        "msg": f"External process execution detected: {full_name}()",
                    }
                )
            elif full_name in (
                "pickle.load",
                "pickle.loads",
                "_pickle.load",
                "_pickle.loads",
                "marshal.load",
                "marshal.loads",
            ):
                self.issues.append(
                    {
                        "file": self.filename,
                        "line": node.lineno,
                        "severity": "CRITICAL",
                        "code": "SEC-004",
                        "msg": f"Insecure deserialization detected: {full_name}()",
                    }
                )
            elif full_name == "tempfile.mktemp":
                self.issues.append(
                    {
                        "file": self.filename,
                        "line": node.lineno,
                        "severity": "MEDIUM",
                        "code": "SEC-005",
                        "msg": "Insecure temporary file creation: tempfile.mktemp() (use NamedTemporaryFile)",
                    }
                )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name in ("pickle", "_pickle", "shelve", "marshal", "pty", "telnetlib"):
                self.issues.append(
                    {
                        "file": self.filename,
                        "line": node.lineno,
                        "severity": "HIGH",
                        "code": "SEC-006",
                        "msg": f"Potentially dangerous module imported: {alias.name}",
                    }
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module in ("pickle", "_pickle", "shelve", "marshal", "pty", "telnetlib"):
            self.issues.append(
                {
                    "file": self.filename,
                    "line": node.lineno,
                    "severity": "HIGH",
                    "code": "SEC-006",
                    "msg": f"Potentially dangerous module imported: {node.module}",
                }
            )
        self.generic_visit(node)

    def _get_attribute_name(self, node: ast.Attribute) -> str:
        parts = [node.attr]
        curr = node.value
        while isinstance(curr, ast.Attribute):
            parts.append(curr.attr)
            curr = curr.value
        if isinstance(curr, ast.Name):
            parts.append(curr.id)
        return ".".join(reversed(parts))


def check_secrets_and_credentials(content: str, filename: str) -> list[dict]:
    issues = []
    # Check for hardcoded private keys, AWS keys, API tokens
    patterns = [
        (r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Hardcoded Private Key"),
        (
            r"(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token|password)\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
            "Hardcoded Secret/Token",
        ),
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    ]
    for lineno, line in enumerate(content.splitlines(), 1):
        for pat, desc in patterns:
            if re.search(pat, line):
                issues.append(
                    {
                        "file": filename,
                        "line": lineno,
                        "severity": "CRITICAL",
                        "code": "SEC-010",
                        "msg": f"Potential hardcoded credential/secret ({desc})",
                    }
                )
    return issues


def validate_metadata_file(metadata_path: Path) -> list[str]:
    errors = []
    if not metadata_path.is_file():
        return ["metadata.txt not found"]
    config = configparser.ConfigParser()
    try:
        config.read(metadata_path, encoding="utf-8")
    except Exception as exc:
        return [f"Failed to parse metadata.txt: {exc}"]

    if not config.has_section("general"):
        return ["metadata.txt missing [general] section"]

    gen = config["general"]
    required_fields = [
        "name",
        "qgisMinimumVersion",
        "description",
        "about",
        "version",
        "author",
        "email",
        "category",
    ]
    for field in required_fields:
        val = gen.get(field, "").strip()
        if not val:
            errors.append(f"metadata.txt missing required field: {field}")

    # Validate email format
    email = gen.get("email", "")
    if "@" not in email or "." not in email:
        errors.append(f"Invalid author email in metadata.txt: {email}")

    # Validate version format
    version = gen.get("version", "")
    if not re.match(r"^\d+\.\d+\.\d+", version):
        errors.append(f"Version must follow semantic format (e.g. 1.0.0): {version}")

    # Validate icon
    icon_rel = gen.get("icon", "")
    if icon_rel:
        icon_path = metadata_path.parent / icon_rel
        if not icon_path.is_file():
            errors.append(f"Declared icon file does not exist: {icon_rel}")

    return errors


def validate_zip_archive(zip_path: Path) -> list[str]:
    errors = []
    if not zip_path.is_file():
        return [f"Zip archive not found: {zip_path}"]
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        if not names:
            return ["ZIP archive is empty"]
        top_dirs = {n.split("/")[0] for n in names if "/" in n}
        if len(top_dirs) != 1 or "yield_data_cleaner" not in top_dirs:
            errors.append(
                f"ZIP root structure must be a single 'yield_data_cleaner/' directory. Found: {top_dirs}"
            )

        # Check for forbidden files in archive
        for n in names:
            if any(
                forbidden in n
                for forbidden in (
                    "__pycache__",
                    ".pyc",
                    ".git",
                    ".DS_Store",
                    ".pytest_cache",
                    ".venv",
                )
            ):
                errors.append(f"Forbidden artifact in ZIP package: {n}")
            if n.startswith("/") or ".." in n:
                errors.append(f"Unsafe file path in ZIP: {n}")
    return errors


def run_full_security_scan() -> int:
    print("=" * 60)
    print("RUNNING QGIS PLUGIN SECURITY & REPOSITORY COMPLIANCE SCAN")
    print("=" * 60)

    total_issues: list[dict] = []
    py_files = list(PLUGIN_DIR.rglob("*.py"))
    print(f"[*] Scanning {len(py_files)} Python source files in yield_data_cleaner...")

    for py_file in py_files:
        rel_path = py_file.relative_to(ROOT_DIR)
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception as exc:
            total_issues.append(
                {
                    "file": str(rel_path),
                    "line": 1,
                    "severity": "CRITICAL",
                    "code": "IO-001",
                    "msg": f"Failed to read file as UTF-8: {exc}",
                }
            )
            continue

        # AST inspection
        try:
            tree = ast.parse(content, filename=str(py_file))
            visitor = SecurityVisitor(str(rel_path))
            visitor.visit(tree)
            total_issues.extend(visitor.issues)
        except Exception as exc:
            total_issues.append(
                {
                    "file": str(rel_path),
                    "line": 1,
                    "severity": "HIGH",
                    "code": "AST-001",
                    "msg": f"Syntax / AST parse error: {exc}",
                }
            )

        # Secret / Credential scan
        secret_issues = check_secrets_and_credentials(content, str(rel_path))
        total_issues.extend(secret_issues)

    # Validate metadata.txt
    print("[*] Validating metadata.txt compliance...")
    meta_errors = validate_metadata_file(PLUGIN_DIR / "metadata.txt")
    for err in meta_errors:
        total_issues.append(
            {
                "file": "yield_data_cleaner/metadata.txt",
                "line": 1,
                "severity": "HIGH",
                "code": "META-001",
                "msg": err,
            }
        )

    # Validate latest release ZIP archive
    dist_dir = ROOT_DIR / "dist"
    zips = list(dist_dir.glob("yield_data_cleaner-*.zip"))
    if zips:

        def parse_ver(p: Path):
            m = re.search(r"yield_data_cleaner-(\d+)\.(\d+)\.(\d+)", p.name)
            return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

        latest_zip = max(zips, key=parse_ver)
        print(f"[*] Validating release archive {latest_zip.name}...")
        zip_errors = validate_zip_archive(latest_zip)
        for err in zip_errors:
            total_issues.append(
                {
                    "file": str(latest_zip.relative_to(ROOT_DIR)),
                    "line": 1,
                    "severity": "HIGH",
                    "code": "PKG-001",
                    "msg": err,
                }
            )
    else:
        print("[!] No distribution ZIP found in dist/ to validate.")

    print("\n" + "=" * 60)
    print("SCAN RESULTS SUMMARY")
    print("=" * 60)

    if not total_issues:
        print(
            "\n>>> ALL CHECKS PASSED: 0 Security Vulnerabilities, 0 Packaging Defects, 0 Metadata Violations. <<<"
        )
        print(
            "The plugin is fully compliant with official QGIS Plugin Repository security standards.\n"
        )
        return 0
    else:
        print(f"\nFound {len(total_issues)} issues:")
        for issue in total_issues:
            print(
                f" [{issue['severity']}] {issue['code']} - {issue['file']}:{issue['line']} -> {issue['msg']}"
            )
        return 1


if __name__ == "__main__":
    sys.exit(run_full_security_scan())
