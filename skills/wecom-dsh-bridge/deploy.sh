#!/bin/bash
# 企业微信智能机器人 中继 一键部署脚本
# 用法: bash deploy.sh   （需先填好 config.json 里的三个凭证）
set -e
mkdir -p ~/aibot-relay
cp relay.py ~/aibot-relay/relay.py 2>/dev/null || true
cp config.json ~/aibot-relay/config.json 2>/dev/null || true
chmod 600 ~/aibot-relay/config.json
chmod +x ~/aibot-relay/relay.py

# 安装依赖
python3 -m pip install -q wecom-aibot-sdk-python aiohttp 2>&1 | tail -2 || true

# 清理旧进程
pkill -f "relay.py" 2>/dev/null || true
sleep 1

# 启动守护进程
cd ~/aibot-relay
nohup python3 relay.py >> relay.log 2>&1 &
echo "PID: $!"
sleep 7
echo "=== relay.log 最新 ==="
tail -5 relay.log
