# The LoCoMo answer-key audit (Penfield Labs, 2026-04-04,
# github.com/dial481/locomo-audit, CC BY-NC 4.0): 99 of 1,540 gold answers
# wrong. Downloaded at a pinned commit, not copied into this repo.
#   bash fetch_audit.sh && LOCOMO_AUDIT=results/locomo_audit_errors.json python score.py results/<dir>
set -eu
cd "$(dirname "$0")"
C=9493fb4b4af4256ed17a18e8fd0b3cfdeec29539
F=results/locomo_audit_errors.json
curl -sSfL -o $F https://raw.githubusercontent.com/dial481/locomo-audit/$C/errors.json
echo "f298ef46263fada20688a1d672be37d4f488c6da3b19343eea55ae5c1b5fe55e  $F" | sha256sum -c -
# the audit's deliberately wrong answers (judge leniency test, judge_stress.py)
for v in v1 v2; do
  curl -sSfL -o results/locomo_audit_ap_$v.json https://raw.githubusercontent.com/dial481/locomo-audit/$C/ap-baseline/$v/ap_eval_results.json
done
echo "080338f63c229d36b2a177cf4c0720a47aedff830f8202c908c40412d76f5feb  results/locomo_audit_ap_v1.json
3118fcc86f683d32e0b7294f65345ff8d612e74bd8d5da9af82627d12b82810a  results/locomo_audit_ap_v2.json" | sha256sum -c -
