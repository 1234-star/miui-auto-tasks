#!/usr/bin/env bash
# new Env("MIUI-Auto-Task 环境配置")
echo "在本任务运行完后请不要忘记禁用该任务！"
echo "在本任务运行完后请不要忘记禁用该任务！"
echo "在本任务运行完后请不要忘记禁用该任务！"
echo "————————————"
SCRIPT_PATH="$(readlink -f "$0")"
QL_BASE="${QL_DIR:-/ql/data}"
ROOT_DIR=""

# 尝试定位仓库根目录，兼容 repo/scripts 以及不同仓库名
CANDIDATES=(
  "$(dirname "$SCRIPT_PATH")"
  "$QL_BASE/repo/1234-star_miui-auto-tasks_master"
  "$QL_BASE/repo/1234-star_miui-auto-tasks"
  "$QL_BASE/repo/0-8-4_miui-auto-tasks_master"
  "$QL_BASE/scripts/1234-star_miui-auto-tasks_master"
  "$QL_BASE/scripts/1234-star_miui-auto-tasks"
  "$QL_BASE/scripts/0-8-4_miui-auto-tasks_master"
  "$QL_BASE/repo"/*miui-auto-tasks*
  "$QL_BASE/scripts"/*miui-auto-tasks*
)

for CANDIDATE in "${CANDIDATES[@]}"; do
  [ -d "$CANDIDATE" ] || continue
  if [ -f "$CANDIDATE/requirements.txt" ] && [ -f "$CANDIDATE/miuitask.py" ]; then
    ROOT_DIR="$(cd "$CANDIDATE" || exit 1; pwd)"
    break
  fi
done

if [ -z "$ROOT_DIR" ]; then
  # 尝试全局搜索
  for FOUND in $(find "$QL_BASE" /ql/data/scripts /ql/data/repo 2>/dev/null -maxdepth 5 -type f -name "miuitask.py" | head -n 5); do
    BASE_DIR="$(dirname "$FOUND")"
    if [ -f "$BASE_DIR/requirements.txt" ]; then
      ROOT_DIR="$BASE_DIR"
      break
    fi
  done
fi

if [ -z "$ROOT_DIR" ]; then
  echo "未找到仓库目录，请确认已拉取 1234-star/miui-auto-tasks 到 /ql/data/repo 或 /ql/data/scripts 下"
  exit 1
fi

CONFIG_DIR="$ROOT_DIR/data"
REQ_FILE="$ROOT_DIR/requirements.txt"
echo "仓库目录: $ROOT_DIR"
mkdir -p "$CONFIG_DIR"
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
