#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-}"
PROCESS_NAME="${2:-}"
if [[ "$ACTION" != "check" && "$ACTION" != "stop" ]]; then
  echo "usage: $0 check|stop PROCESS_NAME EXPECTED_EXECUTABLE [EXPECTED_EXECUTABLE ...]" >&2
  exit 2
fi
if [[ -z "$PROCESS_NAME" || "$#" -lt 3 ]]; then
  echo "usage: $0 check|stop PROCESS_NAME EXPECTED_EXECUTABLE [EXPECTED_EXECUTABLE ...]" >&2
  exit 2
fi
shift 2

EXPECTED_EXECUTABLES=("$@")
for executable in "${EXPECTED_EXECUTABLES[@]}"; do
  if [[ "$executable" != /* || "${executable##*/}" != "$PROCESS_NAME" ]]; then
    echo "Expected executable must be an absolute path ending in $PROCESS_NAME: $executable" >&2
    exit 2
  fi
done

MATCHING_PIDS=()
while IFS= read -r pid; do
  [[ -n "$pid" ]] || continue
  for expected_executable in "${EXPECTED_EXECUTABLES[@]}"; do
    if /usr/sbin/lsof -a -p "$pid" -d txt -Fn 2>/dev/null \
        | grep -Fqx "n$expected_executable"; then
      MATCHING_PIDS+=("$pid")
      break
    fi
  done
done < <(pgrep -x "$PROCESS_NAME" 2>/dev/null || true)

if [[ "$ACTION" == "check" ]]; then
  [[ "${#MATCHING_PIDS[@]}" -gt 0 ]]
  exit
fi
if [[ "${#MATCHING_PIDS[@]}" -eq 0 ]]; then
  exit 0
fi

kill -TERM "${MATCHING_PIDS[@]}" 2>/dev/null || true
for _ in {1..40}; do
  still_running=false
  for pid in "${MATCHING_PIDS[@]}"; do
    if /usr/sbin/lsof -a -p "$pid" -d txt -Fn 2>/dev/null | grep -q '^n'; then
      still_running=true
      break
    fi
  done
  if [[ "$still_running" == false ]]; then
    exit 0
  fi
  sleep 0.05
done

for pid in "${MATCHING_PIDS[@]}"; do
  if /usr/sbin/lsof -a -p "$pid" -d txt -Fn 2>/dev/null | grep -q '^n'; then
    kill -KILL "$pid" 2>/dev/null || true
  fi
done
