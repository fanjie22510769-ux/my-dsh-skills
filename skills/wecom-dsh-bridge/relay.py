#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 企业微信智能机器人 中继 —— 收消息 -> DeepSeek 对话 -> [RUN] 命令执行 -> 回复
# 依赖: pip install wecom-aibot-sdk-python aiohttp
import asyncio, json, os, sys, time, subprocess, re
from wecom_aibot_sdk import WSClient
import aiohttp

BASE = os.path.expanduser("~/aibot-relay")
CONFIG = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
INBOX = os.path.join(BASE, "inbox.jsonl")
CHATS = os.path.join(BASE, "chats")
os.makedirs(CHATS, exist_ok=True)

# SDK 认识的键（业务配置 deepseek_api_key/model 不要传进去，否则报 unexpected keyword）
SDK_KEYS = {"bot_id", "secret", "reconnect_interval", "max_reconnect_attempts",
            "heartbeat_interval", "request_timeout", "ws_url", "logger"}


def sdk_opts():
    return {k: v for k, v in CONFIG.items() if k in SDK_KEYS}


SYSTEM_PROMPT = (
    "你是运行在用户 Windows 电脑（内含 WSL Ubuntu 环境）上的智能助手「DSH」，通过企业微信与用户对话。\n"
    "用户是科研工作者（生物信息学/生物化学/材料科学），研究数据主要在 D:\\FJ（WSL 里为 /mnt/d/FJ）。\n"
    "规则：\n"
    "1. 用简体中文简洁、自然地回答，像朋友一样。\n"
    "2. 当你需要执行命令控制电脑（查文件、跑脚本、看系统状态等）时，在回复中单独一行输出 [RUN] <shell命令>，"
    "命令会在 WSL bash 中执行（用绝对路径，如 /mnt/d/FJ/...）。一次回复最多一个 [RUN]。\n"
    "3. 不要编造命令执行结果，执行结果会由系统自动附加到你的回复末尾。\n"
    "4. 危险操作（rm -rf、格式化、覆盖重要文件等）必须先征得用户同意再输出 [RUN]。\n"
    "5. 纯聊天问题直接回答，不必执行命令。\n"
)


def chat_key_of(msg):
    cid = msg.get("chat_id") or ""
    if cid:
        return "group-" + cid
    sender = msg.get("sender") or {}
    uid = sender.get("userid") if isinstance(sender, dict) else str(sender)
    return "single-" + (uid or "unknown")


def load_history(key):
    p = os.path.join(CHATS, key + ".jsonl")
    hist = []
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            try:
                hist.append(json.loads(line))
            except Exception:
                pass
    return hist[-20:]


def save_turn(key, role, content):
    with open(os.path.join(CHATS, key + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"role": role, "content": content}, ensure_ascii=False) + "\n")


async def deepseek_chat(messages):
    async with aiohttp.ClientSession() as s:
        async with s.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": "Bearer " + CONFIG["deepseek_api_key"],
                     "Content-Type": "application/json"},
            json={"model": CONFIG.get("model", "deepseek-chat"),
                  "messages": messages, "max_tokens": 2000, "temperature": 0.7},
            timeout=aiohttp.ClientTimeout(total=90),
        ) as r:
            data = await r.json()
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    return "[调用出错] " + json.dumps(data, ensure_ascii=False)[:300]


def run_command(cmd):
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, timeout=60)
        out = (r.stdout or "").strip()[-3000:]
        err = (r.stderr or "").strip()[-1000:]
        parts = []
        if out:
            parts.append(out)
        if err:
            parts.append("[stderr] " + err)
        if r.returncode != 0:
            parts.append(f"[退出码 {r.returncode}]")
        return "\n".join(parts) if parts else "(无输出)"
    except subprocess.TimeoutExpired:
        return "(命令执行超时 >60s 已终止)"
    except Exception as e:
        return f"(命令执行异常: {e})"


async def on_text(frame):
    body = frame.body or {}
    headers = frame.headers or {}
    text = body.get("text")
    content = text.get("content", "") if isinstance(text, dict) else str(body.get("content", ""))
    sender = body.get("from") or body.get("sender") or {}
    msg = {
        "type": "text", "chat_id": body.get("chat_id") or headers.get("chat_id") or "",
        "sender": sender, "content": content,
        "req_id": headers.get("req_id") or body.get("req_id") or "",
        "ts": int(time.time()),
    }
    with open(INBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    print("MSG:", sender, "|", content[:60], flush=True)

    key = chat_key_of(msg)
    hist = load_history(key)
    hist.append({"role": "user", "content": content})
    save_turn(key, "user", content)

    try:
        await client.reply_stream(frame, "stream-" + str(int(time.time())),
                                  "正在思考…", finish=True)
    except Exception:
        pass

    try:
        reply = await deepseek_chat([{"role": "system", "content": SYSTEM_PROMPT}] + hist)
    except Exception as e:
        reply = f"[出错] {e}"

    run_out = ""
    m = re.search(r"\[RUN\]\s*(.+)", reply, re.IGNORECASE)
    if m:
        cmd = m.group(1).strip()
        run_out = run_command(cmd)
        reply = re.sub(r"\[RUN\]\s*.+", "", reply, flags=re.IGNORECASE).strip()

    full = reply
    if run_out:
        full += "\n\n**执行结果：**\n```\n" + run_out + "\n```"

    full = full[:20000]
    save_turn(key, "assistant", full)
    try:
        await client.reply(frame, {"msgtype": "markdown", "markdown": {"content": full}})
        print("REPLIED OK", flush=True)
    except Exception as e:
        print("REPLY FAIL:", e, flush=True)


async def on_enter(frame):
    try:
        await client.reply_welcome(frame, {"msgtype": "markdown",
                                           "markdown": {"content": "我是 DSH 助手，现在可以直接对话了。想让我操作电脑，直接说需求即可（涉及删除等危险操作我会先确认）。"}})
    except Exception as e:
        print("WELCOME FAIL:", e, flush=True)


async def send_text(chat_id, content, chat_type=1):
    c = WSClient(sdk_opts())
    await c.connect_async()
    await asyncio.sleep(2)
    from wecom_aibot_sdk import generate_req_id
    req_id = generate_req_id("aibot_send_msg")
    r = await c._ws_manager.send_reply(
        req_id,
        {"chatid": chat_id, "chat_type": chat_type,
         "msgtype": "markdown", "markdown": {"content": content}},
        "aibot_send_msg")
    print("SEND_RESULT:", str(r)[:500], flush=True)
    await c.disconnect()


async def main():
    if len(sys.argv) > 1 and sys.argv[1] == "send":
        ct = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] in ("1", "2") else 1
        await send_text(sys.argv[2], sys.argv[3], ct)
        return
    global client
    client = WSClient(sdk_opts())
    client.on("message.text", on_text)
    client.on("event.enter_chat", on_enter)
    await client.connect_async()
    print("RELAY_STARTED authenticated:", client.is_authenticated, flush=True)

    async def auth_reporter():
        for _ in range(10):
            await asyncio.sleep(2)
            if client.is_authenticated:
                print("AUTH_OK connected:", client.is_connected, flush=True)
                return
        print("AUTH_STATUS:", client.is_authenticated, flush=True)

    asyncio.create_task(auth_reporter())
    while client.is_connected:
        await asyncio.sleep(1)


asyncio.run(main())
