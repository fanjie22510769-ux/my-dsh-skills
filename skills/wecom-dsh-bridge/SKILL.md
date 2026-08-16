---
name: wecom-dsh-bridge
description: 指导用户把「企业微信智能机器人」联通到 DSH，实现在企业微信里与 AI 自然对话、并让 AI 控制这台电脑（执行命令）。当用户表达「在企业微信里和 AI 聊天 / 用企业微信机器人 / 微信控制电脑 / 接入企业微信机器人 / 远程操控电脑」等意图时，加载本 skill 并按其步骤一步步引导用户完成。
license: MIT
metadata:
    author: FJ
    version: 1.0.0
    updated: 2026-08-16
---

# 企业微信智能机器人 ↔ DSH 联通指南

## 这个 skill 能做什么

把「企业微信智能机器人」变成你的私人 AI 助手入口：
- 你（或任何人）在企业微信 App 里发消息 → AI 用自然语言回复你；
- 你可以从手机上直接命令 AI 操作这台电脑（查文件、跑脚本、看状态等）；
- 全程中文，手机上操作即可，不用坐在电脑前。

完成后的大致样子：
```
你（手机企业微信） ──发消息──▶ 企业微信智能机器人（长连接）
                                   │ WebSocket
                                   ▼
                            中继程序（跑在电脑上）
                                   │ 调 DeepSeek 对话
                                   ▼
                              AI 回复 / 执行命令 ──▶ 推回你手机
```

## 你需要准备的 3 样东西（缺一不可）

| # | 东西 | 在哪里弄 | 是否花钱 |
|---|------|---------|---------|
| 1 | 企业微信（一个能创建机器人的账号，通常是企业管理员） | 企业微信 App / 网页管理后台 | 免费（基础功能） |
| 2 | 一台常开机的电脑（Windows，最好装了 WSL/Ubuntu） | 你自己的电脑 | 已有 |
| 3 | DeepSeek API 密钥（sk- 开头） | platform.deepseek.com → API Keys | 按用量付费，很便宜 |

> ⚠️ 重要：智能机器人的「API 长连接」能力一般要求账号是**企业主体**，个人版企业微信可能没有此入口。如果找不到机器人菜单，先确认你的企业微信是「企业」而不是「个人微信」。

---

## 第一部分：在企业微信里创建智能机器人

### 第 1 步：打开管理后台
1. 打开电脑浏览器，访问：https://work.weixin.qq.com
2. 用「企业微信」扫码登录（不是个人微信！）。
3. 登录后进入「管理后台」（首页有个「进入管理后台」按钮）。

### 第 2 步：找到「智能机器人」入口
1. 在管理后台左侧或顶部菜单，找「应用管理」或「智能机器人 / AI 助手」。
   - 不同版本位置略不同，常见路径：**应用管理 → 智能机器人** 或 **管理工具 → 智能机器人**。
2. 点击「创建智能机器人 / 添加机器人」，给机器人起个名字（比如「我的AI助手」），按提示完成创建。

### 第 3 步：开启「API 模式 → 长连接」（关键！）
这是最容易漏的一步，不做后面连不上：
1. 在机器人详情页，找到「API 接入」或「接收消息」的配置项。
2. 把模式切成 **「API 模式」**，并在两种方式里选 **「长连接」**（不是「设置接收消息回调地址」）。
3. 保存。

### 第 4 步：记下 BotID 和 Secret（关键凭证）
开启长连接后，页面会显示两个字段：
- **BotID**：智能机器人的唯一标识，通常是一串字母数字（例如 `aibD76d...`）。
- **Secret**：长连接专用密钥，通常需要点「显示/复制」按钮，也是一串长字符。

> ⚠️ 千万别和别的混淆：
> - BotID 不是浏览器地址栏里那个纯数字的 `aibotid=...`，是页面「API 凭证」里那串字母数字；
> - Secret 是「长连接专用密钥」，不是「Token / EncodingAESKey」（那是回调模式用的，本方案不用）。

把这两串原样发给 DSH（或按 DSH 的提示粘贴）。

---

## 第二部分：获取 DeepSeek API 密钥

1. 浏览器打开：https://platform.deepseek.com
2. 注册/登录（可用手机号）。
3. 左侧菜单点「API Keys」。
4. 点「创建 API Key」，复制生成的 `sk-` 开头字符串（只显示一次，请妥善保存）。
5. 把这串 `sk-...` 发给 DSH。

> 费用说明：按 token 计费，普通聊天/控制电脑用量极低，几块钱能用很久。可在平台「用量」页查看余额。

---

## 第三部分：让 DSH 部署中继（DSH 执行）

拿到 BotID、Secret、DeepSeek key 后，DSH 需要在一台常开机的电脑上部署「中继程序」。DSH 按以下步骤操作：

### 第 1 步：确认电脑有 Python 3.9+
```bash
python3 --version
```
没有则先装（推荐 miniconda 或直接 apt install python3）。

### 第 2 步：安装 SDK
```bash
pip install wecom-aibot-sdk-python aiohttp
```

### 第 3 步：部署本 skill 附带的 `relay.py`
1. 把 `relay.py` 放到一个固定目录，例如 `~/aibot-relay/relay.py`；
2. 在同目录建 `config.json`，内容用附带的 `config.example.json` 模板，填入三样凭证；
3. `chmod 600 ~/aibot-relay/config.json`（保护密钥）。

### 第 4 步：启动并验证
```bash
cd ~/aibot-relay
nohup python relay.py >> relay.log 2>&1 &
sleep 7 && tail -5 relay.log
```
看到 `AUTH_OK connected: True` 即联通成功。

### 第 5 步：让用户在企业微信里发一条消息测试
用户在企业微信 App 找到该机器人，发一句「你好」。DSH 查看 `~/aibot-relay/inbox.jsonl` 与 `relay.log` 确认消息已收到、AI 已回复。

---

## 使用说明（给最终用户）

- **聊天**：在企业微信里直接发消息，机器人用自然语言回复。
- **控制电脑**：用大白话说需求，例如「帮我看看 D 盘有多少空间」「把 D:\FJ 下的项目列出来」。AI 会自动执行命令并把结果回给你。
- **危险操作会先问**：删除文件等危险命令，AI 会先征求同意。
- **连续对话**：机器人会记住最近的上下文（每 20 轮）。

---

## 排错手册（DSH 遇到问题时查这里）

| 现象 | 原因 | 解决 |
|------|------|------|
| 认证失败，提示 `853000 invalid bot_id or secret` | BotID/Secret 填错；或 BotID 错用了网址里纯数字的 aibotid | 用管理后台「API 凭证」里那串字母数字 BotID + 长连接 Secret；未开启「API 模式→长连接」先开启 |
| 回复报错 `40008 invalid message type` | 回复/推送用了 `text` 类型 | 智能机器人回复只支持 `markdown / template_card / file / image / voice / video`，改用 `msgtype:"markdown"` |
| 单聊收不到 chatid | 智能机器人回调里 `chatid` **只对群聊返回** | 单聊用 `from.userid` 标识；主动推送单聊时 `chatid` 填 userid 且加 `chat_type:1` |
| 主动推送发不出去 | 缺 `chat_type`；或 SDK 的 `send_message` 没带该字段 | 用 `_ws_manager.send_reply(req_id, {"chatid":..,"chat_type":1,"msgtype":"markdown",...}, "aibot_send_msg")` |
| `WSClientOptions got unexpected keyword argument` | 给 SDK 传了它不认识的配置键（如 deepseek_api_key） | 把 SDK 认识的键（bot_id/secret/心跳/重连）单独过滤后再传，业务配置单独读 |
| 消息偶尔丢失 | 长连接断线重连期间，服务端推送的消息不补发 | 保持电脑常开、网络稳定；重连由 SDK 自动处理 |
| 机器人没反应 | 智能机器人没「发布/上线」，或模式选成了「设置接收消息回调地址」 | 后台确认已发布 + API 模式=长连接 |

---

## 安全提示

- `Secret` 和 `DeepSeek key` 属于敏感凭证，`config.json` 权限设为 600，不要提交到公开仓库、不要发群。
- 中继会执行 AI 判断出的命令，等价于把命令行权限交给了「能通过企业微信联系到机器人的人」。务必只用在自己可控的账号，机器人尽量只加自己和信任的人。
- 若凭证泄露，立即在后台「重置 Secret」、在 DeepSeek 平台「删除并重建 API Key」。

---

## 附带的参考文件

- `relay.py`：中继主程序（收消息→DeepSeek 对话→`[RUN]` 命令执行→回复）
- `config.example.json`：配置模板（填三个凭证即可）
- `deploy.sh`：一键部署脚本（复制文件 + 装依赖 + 启动守护进程）
