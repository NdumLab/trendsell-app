#!/usr/bin/env bash
set -euo pipefail

# This is a deliberately redacting credential-shape scan. It reports only a file and,
# for history, a commit; it never prints the matching line or suspected credential.

repository=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
openai_prefix='s''k-'
github_prefix='g''hp_'
github_fine_prefix='github_''pat_'
aws_prefix='AK''IA'
google_prefix='AI''za'
slack_prefix='xo''x[abpr]-'
private_key='-----BE''GIN [A-Z ]*PRIVATE KEY-----'
pattern="(${openai_prefix}[A-Za-z0-9]{16,}|${github_prefix}[A-Za-z0-9]{20,}|${github_fine_prefix}[A-Za-z0-9_]{20,}|${aws_prefix}[0-9A-Z]{16}|${google_prefix}[0-9A-Za-z_-]{30,}|${slack_prefix}[0-9A-Za-z-]{10,}|${private_key})"

usage() {
    echo "usage: $0 [--tracked] [--history] [--directory PATH]" >&2
    exit 2
}

scan_tracked=false
scan_history=false
directories=()
if [[ $# -eq 0 ]]; then
    scan_tracked=true
fi
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tracked)
            scan_tracked=true
            shift
            ;;
        --history)
            scan_history=true
            shift
            ;;
        --directory)
            [[ $# -ge 2 ]] || usage
            directories+=("$2")
            shift 2
            ;;
        *) usage ;;
    esac
done

failed=false

if [[ "$scan_tracked" == true ]]; then
    cd "$repository"
    mapfile -t tracked_hits < <(git grep -IlE "$pattern" -- . || true)
    if [[ ${#tracked_hits[@]} -gt 0 ]]; then
        failed=true
        for path in "${tracked_hits[@]}"; do
            echo "suspected credential in tracked file: $path" >&2
        done
    fi
fi

if [[ "$scan_history" == true ]]; then
    cd "$repository"
    # Older CI versions stored the scanner expression itself in PATTERN. Ignore only
    # that declaration line; do not suppress the workflow or any other historical file.
    while IFS= read -r commit; do
        mapfile -t candidate_paths < <(git grep -IlE "$pattern" "$commit" -- . 2>/dev/null | \
            sed "s#^${commit}:##" || true)
        for path in "${candidate_paths[@]}"; do
            if git show "${commit}:${path}" | grep -E "$pattern" | \
               grep -Ev "^[[:space:]]*PATTERN=.*PRIVATE KEY" >/dev/null; then
                failed=true
                echo "suspected credential in history: $commit $path" >&2
            fi
        done
    done < <(git rev-list --all)
fi

for directory in "${directories[@]}"; do
    if [[ ! -d "$directory" ]]; then
        echo "secret-scan directory does not exist: $directory" >&2
        exit 2
    fi
    mapfile -t directory_hits < <(grep -RIlE --binary-files=without-match \
        --exclude-dir=.git "$pattern" "$directory" || true)
    if [[ ${#directory_hits[@]} -gt 0 ]]; then
        failed=true
        for path in "${directory_hits[@]}"; do
            echo "suspected credential in release content: $path" >&2
        done
    fi
done

if [[ "$failed" == true ]]; then
    echo "credential-shape scan failed; rotate any real credential before removing it" >&2
    exit 1
fi

echo "Credential-shape scan passed."
