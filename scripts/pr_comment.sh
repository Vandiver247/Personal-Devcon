#!/usr/bin/env bash
# Post a Markdown file as a pull request comment, replacing the previous
# comment that starts with the same first line (an HTML marker comment).
#
# Usage: pr_comment.sh PR_NUMBER REPORT.md
# Needs `gh` authenticated (GH_TOKEN or GITHUB_TOKEN) and GITHUB_REPOSITORY set.
set -euo pipefail

pr="$1"
file="$2"
repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY must be set}"
marker="$(head -n 1 "$file")"

comment_id="$(
    gh api "repos/$repo/issues/$pr/comments" --paginate \
        --jq ".[] | select(.body | startswith(\"$marker\")) | .id" | head -n 1
)"

if [[ -n "$comment_id" ]]; then
    gh api --method PATCH "repos/$repo/issues/comments/$comment_id" -F "body=@$file" --silent
    echo "updated comment $comment_id"
else
    gh api --method POST "repos/$repo/issues/$pr/comments" -F "body=@$file" --silent
    echo "created comment"
fi
