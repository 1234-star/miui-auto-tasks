#!/usr/bin/env bash
# new Env("MIUI-Auto-Task 环境配置")
echo "在本任务运行完后请不要忘记禁用该任务！"
echo "在本任务运行完后请不要忘记禁用该任务！"
echo "在本任务运行完后请不要忘记禁用该任务！"
echo "————————————"
SCRIPT_PATH="$(readlink -f "$0")"
ROOT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" || exit 1; pwd)"
QL_BASE="${QL_DIR:-/ql/data}"

# 尝试定位仓库根目录，优先当前脚本所在目录，其次青龙默认 repo 目录
for CANDIDATE in \
    "$ROOT_DIR" \
    "$QL_BASE/repo/1234-star_miui-auto-tasks_master" \
    "$QL_BASE/repo/miui-auto-tasks" \
    "$QL_BASE/repo/$(basename "$ROOT_DIR")" \
    "$QL_BASE/repo"/*miui-auto-tasks*; do
    if [ -f "$CANDIDATE/requirements.txt" ] && [ -f "$CANDIDATE/miuitask.py" ]; then
        ROOT_DIR="$(cd "$CANDIDATE" || exit 1; pwd)"
        break
    fi
done

CONFIG_DIR="$ROOT_DIR/data"
REQ_FILE="$ROOT_DIR/requirements.txt"
echo "开始安装依赖"
if [ ! -f "$REQ_FILE" ]; then
  echo "未找到 requirements.txt，当前目录: $ROOT_DIR"
  exit 1
fi
python3 -m pip install -i https://mirrors.aliyun.com/pypi/simple/ -r "$REQ_FILE"
echo "依赖已安装完毕"
echo "————————————"
echo "开始首次执行"
python3 "${ROOT_DIR}/miuitask.py"
echo "首次执行完毕"
echo "————————————"
echo "请不要忘记禁用该任务！"
echo "请不要忘记禁用该任务！"
echo "请不要忘记禁用该任务！"
echo "请到 ${CONFIG_DIR} 目录下的 config.yaml 或 config.yml 中配置参数 (支持 two_captcha_api_key 等新字段)"
echo "————————————"
