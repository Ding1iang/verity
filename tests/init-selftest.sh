#!/usr/bin/env bash
# verity init 自测：正常生成、重复目录拒绝、缺参数提示、adapter 字段带入。
# 只使用 bash 和 Python 标准库；在临时目录里运行，不改仓库文件。
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
CLI="$ROOT/scripts/verity.py"
CHECK="$ROOT/scripts/check_evidence.py"
TODAY="$(date +%F)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/verity-init-selftest.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

PASS=0
FAIL=0

pass() {
    echo "[PASS] $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "[FAIL] $1"
    FAIL=$((FAIL + 1))
}

# 取仓库 HEAD；取不到时与脚本的“未取到”对齐。
HEAD="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || true)"
if [ -z "$HEAD" ]; then
    HEAD="未取到"
fi

# ---------- 1. 正常生成 ----------
NORMAL="$TMP/normal"
mkdir -p "$NORMAL"
NORMAL_OK=1
"$PYTHON" "$CLI" init "自测任务" --mode acceptance --dir "$NORMAL" >"$TMP/normal.out" 2>"$TMP/normal.err"
if [ "$?" -ne 0 ]; then
    NORMAL_OK=0
    echo "  正常生成退出码非 0"
    sed -n '1,20p' "$TMP/normal.err"
fi

TARGET="$NORMAL/$TODAY-自测任务"
for name in task-card.md 07-验收回归清单.md blocking-form.md; do
    if [ ! -f "$TARGET/$name" ]; then
        NORMAL_OK=0
        echo "  缺少文件：$name"
    fi
done
if [ ! -d "$TARGET/evidence" ]; then
    NORMAL_OK=0
    echo "  缺少目录：evidence/"
fi
if ! grep -q "$TODAY" "$TARGET/task-card.md"; then
    NORMAL_OK=0
    echo "  task-card.md 未填日期"
fi
if ! grep -q "$HEAD" "$TARGET/task-card.md" || ! grep -q "$HEAD" "$TARGET/07-验收回归清单.md"; then
    NORMAL_OK=0
    echo "  HEAD 未带入任务卡或 07"
fi
if ! grep -q "acceptance" "$TARGET/07-验收回归清单.md"; then
    NORMAL_OK=0
    echo "  模式未带入 07"
fi
if ! cmp -s "$ROOT/templates/blocking-form.md" "$TARGET/blocking-form.md"; then
    NORMAL_OK=0
    echo "  举证单与模板不一致"
fi
if [ -n "$(find "$TARGET/evidence" -type f -print -quit)" ]; then
    NORMAL_OK=0
    echo "  evidence/ 不应自动生成文件"
fi
if ! grep -q "未覆盖" "$TARGET/07-验收回归清单.md"; then
    NORMAL_OK=0
    echo "  账本初始状态不是未覆盖"
fi

# 空账本应被检查器以“缺字段”拒绝，而不是抛异常。
(cd "$TARGET" && "$PYTHON" "$CHECK" "07-验收回归清单.md") >"$TMP/empty.out" 2>&1
EMPTY_CODE=$?
if [ "$EMPTY_CODE" -eq 0 ]; then
    NORMAL_OK=0
    echo "  空账本不应通过检查"
elif ! grep -q "E_FIELD" "$TMP/empty.out" || ! grep -q "没有任何验收项" "$TMP/empty.out"; then
    NORMAL_OK=0
    echo "  空账本没有可读的缺字段提示"
fi
if [ "$NORMAL_OK" -eq 1 ]; then
    pass "正常生成：四个文件齐全，空账本报缺字段"
else
    fail "正常生成"
fi

# ---------- 2. 重复目录拒绝 ----------
DUP="$TMP/duplicate"
mkdir -p "$DUP"
DUP_OK=1
"$PYTHON" "$CLI" init "重复任务" --mode bug-fix --dir "$DUP" >/dev/null 2>"$TMP/dup1.err"
if [ "$?" -ne 0 ]; then
    DUP_OK=0
    echo "  第一次生成失败"
fi
DUP_TARGET="$DUP/$TODAY-重复任务"
if [ -f "$DUP_TARGET/task-card.md" ]; then
    BEFORE="$(cksum "$DUP_TARGET/task-card.md")"
else
    BEFORE=""
    DUP_OK=0
fi
"$PYTHON" "$CLI" init "重复任务" --mode bug-fix --dir "$DUP" >"$TMP/dup2.out" 2>"$TMP/dup2.err"
DUP_CODE=$?
if [ "$DUP_CODE" -ne 1 ]; then
    DUP_OK=0
    echo "  重复目录退出码应为 1，实际 $DUP_CODE"
fi
if ! grep -q "拒绝覆盖" "$TMP/dup2.err"; then
    DUP_OK=0
    echo "  重复目录没有拒绝覆盖提示"
fi
if [ -n "$BEFORE" ] && [ "$BEFORE" != "$(cksum "$DUP_TARGET/task-card.md")" ]; then
    DUP_OK=0
    echo "  拒绝覆盖时改动了原任务卡"
fi
if [ "$DUP_OK" -eq 1 ]; then
    pass "重复目录：exit 1，原文件未改"
else
    fail "重复目录拒绝"
fi

# ---------- 3. 缺参数提示 ----------
"$PYTHON" "$CLI" init >"$TMP/missing.out" 2>&1
MISSING_CODE=$?
MISSING_OK=1
if [ "$MISSING_CODE" -eq 0 ]; then
    MISSING_OK=0
    echo "  缺参数时不应成功"
fi
if ! grep -q "任务名" "$TMP/missing.out" || ! grep -q -- "--mode" "$TMP/missing.out"; then
    MISSING_OK=0
    echo "  缺参数提示未同时指出任务名和 --mode"
fi
"$PYTHON" "$CLI" init "只有任务名" >"$TMP/missing-mode.out" 2>&1
if [ "$?" -eq 0 ] || ! grep -q -- "--mode" "$TMP/missing-mode.out"; then
    MISSING_OK=0
    echo "  缺少 --mode 时提示不清晰"
fi
if [ "$MISSING_OK" -eq 1 ]; then
    pass "缺参数：非 0 退出并提示任务名/--mode"
else
    fail "缺参数提示"
fi

# ---------- 4. adapter 字段带入 ----------
ADAPTER="$TMP/adapter.json"
ADAPTER_DIR="$TMP/adapter"
mkdir -p "$ADAPTER_DIR"
printf '%s\n' '{"schema":"verity-adapter/v1","schema_version":1,"min_verity_version":"1.3.0","project":{"name":"演示项目"}}' >"$ADAPTER"
ADAPTER_OK=1
"$PYTHON" "$CLI" init "适配任务" --mode new-feature --dir "$ADAPTER_DIR" --adapter "$ADAPTER" >"$TMP/adapter.out" 2>"$TMP/adapter.err"
if [ "$?" -ne 0 ]; then
    ADAPTER_OK=0
    echo "  adapter 生成失败"
    sed -n '1,20p' "$TMP/adapter.err"
fi
ADAPTER_TARGET="$ADAPTER_DIR/$TODAY-适配任务"
if ! grep -q "项目：演示项目" "$ADAPTER_TARGET/task-card.md"; then
    ADAPTER_OK=0
    echo "  task-card.md 未带入 adapter.project"
fi
if ! grep -q "项目：演示项目" "$ADAPTER_TARGET/07-验收回归清单.md"; then
    ADAPTER_OK=0
    echo "  07 未带入 adapter.project"
fi
if ! grep -q "new-feature" "$ADAPTER_TARGET/task-card.md"; then
    ADAPTER_OK=0
    echo "  模式未带入 task-card.md"
fi
if [ "$ADAPTER_OK" -eq 1 ]; then
    pass "adapter：项目名与模式带入"
else
    fail "adapter 字段带入"
fi

# ---------- 5. 无 ledger_template 时默认按 v2 检查 ----------
NO_TEMPLATE="$TMP/no-template-adapter.json"
printf '%s\n' "{\"schema\":\"verity-adapter/v1\",\"schema_version\":1,\"min_verity_version\":\"1.3.0\",\"project\":{\"name\":\"演示项目\",\"root\":\"$ROOT\"}}" >"$NO_TEMPLATE"
"$PYTHON" "$CHECK" examples/04-project-v1/07-验收回归清单.md --adapter "$NO_TEMPLATE" >"$TMP/no-template.out" 2>&1
NO_TEMPLATE_CODE=$?
if [ "$NO_TEMPLATE_CODE" -eq 0 ]; then
    pass "无 ledger_template：默认 v2，examples/04 可检查"
else
    fail "无 ledger_template 默认 v2"
    sed -n '1,15p' "$TMP/no-template.out"
fi

# ---------- 6. 缺 schema_version 的 adapter 必须失败 ----------
BAD_ADAPTER="$TMP/bad-adapter.json"
printf '%s\n' '{"schema":"verity-adapter/v1","project":{"name":"演示项目"}}' >"$BAD_ADAPTER"
"$PYTHON" "$CLI" init "坏适配任务" --mode new-feature --dir "$TMP/bad-adapter-dir" --adapter "$BAD_ADAPTER" >"$TMP/bad-adapter.out" 2>&1
BAD_ADAPTER_CODE=$?
if [ "$BAD_ADAPTER_CODE" -ne 0 ] && grep -q "schema_version" "$TMP/bad-adapter.out"; then
    pass "缺 schema_version：init 拒绝并指出字段"
else
    fail "缺 schema_version 未被拒绝"
fi

echo "结果：$PASS/6 通过"
if [ "$FAIL" -ne 0 ]; then
    exit 1
fi
