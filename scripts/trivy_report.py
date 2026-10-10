#!/usr/bin/env python3
"""Turn Trivy JSON results into a Markdown report and apply the merge gate.

Usage: trivy_report.py RESULTS.json [--output REPORT.md]

Exits 1 when the scan finds any CRITICAL vulnerability, or any HIGH
vulnerability that has a fixed version available. Exits 0 otherwise.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

MARKER = "<!-- security-report -->"
SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
MISE_INSTALLS = "home/ubuntu/.local/share/mise/installs/"
MAX_DETAIL_ROWS = 100


def is_blocking(vuln: dict) -> bool:
    if vuln["Severity"] == "CRITICAL":
        return True
    return vuln["Severity"] == "HIGH" and bool(vuln.get("FixedVersion"))


def short_target(result: dict) -> str:
    target = result["Target"]
    if result.get("Class") == "os-pkgs":
        return "Ubuntu packages"
    if target.startswith(MISE_INSTALLS):
        return "mise: " + target[len(MISE_INSTALLS):]
    return target


def build_report(results: list[dict]) -> tuple[str, bool]:
    totals: Counter[str] = Counter()
    fixable: Counter[str] = Counter()
    # target -> severity -> count of blocking findings
    by_target: dict[str, Counter[str]] = defaultdict(Counter)
    # (id, package, installed, fixed, severity) -> targets
    details: dict[tuple[str, str, str, str, str], set[str]] = defaultdict(set)

    for result in results:
        target = short_target(result)
        for vuln in result.get("Vulnerabilities") or []:
            severity = vuln["Severity"]
            totals[severity] += 1
            if vuln.get("FixedVersion"):
                fixable[severity] += 1
            if is_blocking(vuln):
                by_target[target][severity] += 1
                key = (
                    vuln["VulnerabilityID"],
                    vuln["PkgName"],
                    vuln.get("InstalledVersion", ""),
                    vuln.get("FixedVersion", "") or "none",
                    severity,
                )
                details[key].add(target)

    blocking = sum(sum(counts.values()) for counts in by_target.values())
    failed = blocking > 0

    lines = [MARKER, "## Security scan (Trivy)", ""]
    if failed:
        lines.append(
            f"❌ **Failing:** {blocking} blocking findings "
            f"({len(details)} unique) across {len(by_target)} targets."
        )
    else:
        lines.append("✅ **Passing:** no blocking findings.")
    lines += [
        "",
        "A finding blocks when it is CRITICAL, or HIGH with a fixed version available.",
        "",
        "| Severity | Findings | Fix available |",
        "|---|---|---|",
    ]
    for severity in SEVERITIES:
        if totals[severity]:
            lines.append(f"| {severity.title()} | {totals[severity]} | {fixable[severity]} |")
    if not totals:
        lines.append("| (none) | 0 | 0 |")

    if failed:
        lines += [
            "",
            "### Blocking findings by target",
            "",
            "| Target | Critical | High (fix available) |",
            "|---|---|---|",
        ]
        ranked = sorted(by_target.items(), key=lambda item: (-item[1]["CRITICAL"], -item[1]["HIGH"], item[0]))
        for target, counts in ranked:
            lines.append(f"| `{target}` | {counts['CRITICAL']} | {counts['HIGH']} |")

        rows = sorted(details.items(), key=lambda item: (SEVERITIES.index(item[0][4]), -len(item[1]), item[0][0]))
        lines += [
            "",
            f"<details><summary>{len(rows)} unique blocking vulnerabilities</summary>",
            "",
            "| Vulnerability | Severity | Package | Installed | Fixed in | Targets |",
            "|---|---|---|---|---|---|",
        ]
        for (vuln_id, package, installed, fixed, severity), targets in rows[:MAX_DETAIL_ROWS]:
            lines.append(
                f"| {vuln_id} | {severity.title()} | `{package}` | {installed} | {fixed} | {len(targets)} |"
            )
        if len(rows) > MAX_DETAIL_ROWS:
            lines += ["", f"…and {len(rows) - MAX_DETAIL_ROWS} more. See the full JSON results in the workflow artifacts."]
        lines += ["", "</details>"]

    lines += ["", "Scanned for vulnerabilities in OS packages and in language packages and binaries inside the image."]
    return "\n".join(lines) + "\n", failed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    results = json.loads(args.results.read_text()).get("Results") or []
    report, failed = build_report(results)
    if args.output:
        args.output.write_text(report)
    print(report, end="")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
