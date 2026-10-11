<p align="center"><img src="deploy/market/assets/icon.png" width="96" alt="OMuse"></p>

<h1 align="center">OMuse</h1>
<p align="center"><b>Your private AI agent that lives on your Olares — and asks before it acts.</b><br>
运行在你 Olares 上的私人 AI 智能体——重要的事，先问你。</p>

![OMuse](deploy/market/assets/featured.webp)

[English](#english) · [中文](#中文)

---

## English

OMuse is a local-first AI agent for [Olares](https://www.olares.com). It doesn't just chat: it turns a request into a plan and carries it out across your email, Notion, Slack and the web. Anything that sends, posts, pays or deletes waits for your approval.

### Features

- **Chat → plan → act** – every step and tool call is visible.
- **Email** (several mailboxes: Gmail, Outlook / Hotmail via OAuth 2.0, Yahoo, iCloud, QQ Mail, NetEase 163 / 126, Zoho, AOL, any IMAP / SMTP server) – search, read, draft, reply, send, one-click unsubscribe. Sign-in codes and reset links are hidden from the model.
- **Notion & Slack** – look things up, write reports, update boards, read and post messages.
- **Web browser** – its own Chromium with a restricted API, live view, and human takeover for logins/CAPTCHAs.
- **MCP connectors** – plug in any MCP (Model Context Protocol) server; tool definitions are pinned.
- **Automations** – multi-day goals, event triggers (new email / Slack message / Notion change) and schedules.
- **Telegram remote control** – give tasks and approve actions from your phone.
- **Research library** – give it a subject; it researches in depth, writes a Markdown report you refine in that subject's chat and refresh later; every report is searchable by the agent.
- **Memory & skills**, **English / 中文 UI**.

### Safe by design

| Layer | What it does |
|---|---|
| **Sentinel** | Independent guard service: ALLOW / DENY / ASK for every action. |
| **Vault** | App passwords and tokens are encrypted in Sentinel; the agent and the model never see them. |
| **Prompt-injection defences** | Emails, pages and tool output are untrusted; suspicious content escalates writes to human approval. |
| **Audit trail** | Append-only, hash-chained log of every model call, tool call, decision and approval. |

### Architecture

```
 browser / Telegram ──► Sentinel :8080  (UI, policy, vault, approvals, audit, connectors)
                            │
                            ├──► Runtime :8081  (planner / executor, scheduler, goals, memory)
                            │        └──► LLM (OpenAI-compatible, default: Olares router)
                            └──► Browser broker :8082  (Playwright + Xvfb)
```

### Install

- **Olares Market**: search for *OMuse* (after the listing is approved).
- **Manual**: `python3 build.py omuse` → upload `dist/omuse-<version>.tgz` in Olares Market ▸ *Upload custom chart*.

The model endpoint defaults to `https://router.<your-olares-name>.olares.com/v1`; change it in the app's settings or the `PERSONA_MODEL_URL` / `PERSONA_MODEL` environment values. If the configured model isn't served, OMuse picks an available one.

### Run with Docker

One container holds all three services; state lives in the `omuse-data` volume.

```bash
docker build -t omuse .
docker run -d --name omuse --restart unless-stopped \
  -p 8080:8080 -v omuse-data:/omuse \
  -e OMUSE_PASSWORD='choose-a-long-password' \
  -e OMUSE_MODEL_URL=https://api.openai.com/v1 \
  -e OMUSE_MODEL=gpt-4.1 \
  -e OMUSE_MODEL_API_KEY=sk-... \
  -e TZ=America/Los_Angeles \
  omuse
```

Open `http://localhost:8080` and sign in as `omuse` (change with `OMUSE_USER`) with your password. `OMUSE_PASSWORD` is only the initial password: change it in Settings → Password (the UI reminds you until you do); the new one is stored hashed in the volume and wins from then on. Olares normally does the login; here the container asks for HTTP Basic auth and refuses to start without `OMUSE_PASSWORD`. Before opening the port to the internet, put HTTPS in front (Cloudflare Tunnel, Tailscale Funnel, Caddy, …) — Basic auth over plain HTTP sends the password in the clear. `OMUSE_MODEL_API_KEY` is sent as a Bearer token to the model endpoint and is never stored in Settings. Add `-p 8083:8083` only if you use the Telnyx phone line.

**Configuration.** Instead of `-e` flags you can keep the settings in a file on the host and pass it with `--env-file` (one `NAME=value` per line, no quotes; keep it out of git, it holds your password and API key):

```bash
docker run -d --name omuse --restart unless-stopped \
  -p 8080:8080 -v omuse-data:/omuse \
  --env-file ~/.config/omuse/omuse.env omuse
```

Docker reads the file when the container is created: after editing it, `docker rm -f omuse` and run it again (your data stays in the volume). To use another host port, change the left side of `-p`, e.g. `-p 9000:8080`.

| Variable | Meaning |
|---|---|
| `OMUSE_PASSWORD` | Login password (required) |
| `OMUSE_USER` | Login name (default `omuse`) |
| `OMUSE_AUTH=off` | No login — only behind another proxy that already authenticates |
| `OMUSE_MODEL_URL`, `OMUSE_MODEL` | OpenAI-compatible endpoint and model id (defaults; a value saved in Settings wins) |
| `OMUSE_PLANNER_MODEL`, `OMUSE_VISION_MODEL`, `OMUSE_STT_MODEL` | Optional model ids for planning, vision (screenshots, images) and speech-to-text on the same endpoint. Unset: planner and vision use `OMUSE_MODEL`, speech-to-text uses a whisper-like model if the endpoint has one. A value saved in Settings wins |
| `OMUSE_MODEL_API_KEY` | API key for the model endpoint (environment only, not in Settings) |
| `TZ` | Default timezone (a value saved in Settings wins) |
| `TELEGRAM_BOT=0`, `VOICE_PORT=0` | Turn off the Telegram bot / the phone port |
| `BROWSER_HEADLESS=1` | Run the browser headless instead of on the virtual display |
| `OMUSE_STRIPE_API_KEY`, `OMUSE_STRIPE_CUSTOMER_ID`, `OMUSE_STRIPE_SUBSCRIPTION_ID` | Optional. With all three set, Settings ends with a "Manage subscription" section that opens the Stripe customer portal |

Everything else (connections, vault, language, limits) is set in the web UI and stored in the volume.

### Deploy on Fly.io

`fly.toml` and `Dockerfile.fly` run the same container on [Fly.io](https://fly.io): one always-on machine with one volume for all state, HTTPS from Fly.

```bash
fly launch --no-deploy --copy-config        # once: creates the app (choose a name and region)
fly volumes create omuse_data --size 10     # once
fly secrets set OMUSE_PASSWORD='choose-a-long-password' OMUSE_MODEL_API_KEY=sk-...
fly deploy
```

Then open `https://<app>.fly.dev` and sign in as `omuse`. The model endpoint and the other variables from the table above go in `[env]` in `fly.toml` (secrets with `fly secrets set`). Keep it at one machine: the state is on the volume.

### Publish images for Products Provisioner

`.github/workflows/release-image.yml` builds `Dockerfile.fly` for **linux/amd64**,
tests the resulting image, pushes that same image to Fly's registry, then imports
its immutable digest into Products Provisioner. It does not deploy customer
instances or change their pinned image. No login password, LLM key, or Stripe key
is baked into the image; those are supplied to each instance at runtime.

Set these under GitHub **Settings → Secrets and variables → Actions**:

| Kind | Name | Value |
|---|---|---|
| Variable | `LOCIUS_IMAGE_APP` | Globally unique Fly image-repository app name, e.g. `locius-images-test` |
| Variable | `LOCIUS_FLY_ORG` | Fly organization slug for that repository app |
| Variable | `RELEASE_PRODUCT_KEY` | Product key in the provisioner; defaults to `locius` (independent of the OMuse display name) |
| Variable | `RELEASE_IMPORT_URL` | Provisioner HTTPS origin only, e.g. `https://product-provisioner.fly.dev` (no `/api/images` suffix) |
| Secret | `FLY_API_TOKEN` | Token allowed to push images and create the repository app in the designated organization |
| Secret | `RELEASE_IMPORT_TOKEN` | This product's image-source `callback_token`, **not** `PP_ADMIN_TOKEN` or `PP_MASTER_KEY` |

Publish the product's callback configuration in the provisioner before the first
automatic import. Configure its Fly credentials for the same organization that
can pull the private image. The workflow creates the image-repository app if
missing; that app stores images and does not need a running Machine or volume.

After committing and pushing the workflow, tag the intended source commit:

```bash
git switch stripe-subscription
git tag locius-v0.1.0
git push origin locius-v0.1.0
```

Tag pushes run the workflow from the tagged commit, even while it lives on this
branch. Manual dispatch becomes available once the workflow is on the default
branch; choose the desired source branch and enter a `locius-v*` version. A manual
run can disable `import_release` to publish an image before a product is ready.
Use a new version for changed source; do not move existing release tags.

Imports use `POST /api/images` with `product_key`, `version`, `image` (digest), and
`parent_version: null`. The callback retries transient failures. The
`image-manifest-<version>` Actions artifact retains the import JSON even if the
callback fails. An identical version/digest import is idempotent.

To verify a local image without any live credentials:

```bash
docker build --platform linux/amd64 -f Dockerfile.fly -t locius:local .
bash tests/docker_image_smoke.sh locius:local
```

On an Apple Silicon Mac, `--platform linux/arm64` builds a native test image;
the release workflow always builds AMD64 for Fly. The smoke test verifies all
three services, login enforcement, unprivileged startup with a root-owned volume,
Chromium PDF rendering, and settings/vault persistence after container replacement.
It deletes only its own temporary containers and volume, leaving the image.

Provisioner image settings should expose port **8080**, mount persistent storage
at **`/omuse`**, and check **`/sentinel/api/health`**. No config file is required.
Supply a generated `OMUSE_PASSWORD` and the environment variables documented above.
Port 8083 is a separate optional phone service; publishing the main UI port does
not expose it. Keep the app always-on if background schedules, event triggers,
or Telegram polling must continue while no browser is open.

### Development

```bash
pip install -r requirements.txt -r requirements-browser.txt
bash tests/run_local.sh            # fake LLM + all services on localhost
python3 -m pytest -q tests/test_units.py
python3 tests/integration.py        # and the other *_e2e.py suites
bash tests/stop_local.sh
```

Or run the local e2e suites inside the Docker image, with nothing on the host but Docker (it installs the test-only dependencies in the container and gives every suite a freshly started stack with the fake LLM):

```bash
bash tests/run_in_docker.sh                  # every suite, about 15 minutes
bash tests/run_in_docker.sh e2e_027 mcp_e2e  # only these
```

It builds the `omuse` image from the Dockerfile if it is missing (`OMUSE_IMAGE` picks another image), prints one `SUITE <name> rc=… pass=… fail=…` line per suite, and exits 1 if any suite fails. `tests/docker_browser_e2e.py` is separate: it drives a running container with a real, vision-capable model (see its docstring).

---

## 中文

OMuse 是为 [Olares](https://www.olares.com) 打造的本地优先（local-first）AI 智能体（AI Agent）。它不只是聊天：会把你的需求拆成计划，在邮件、Notion、Slack 和网页之间把事情做完。凡是发送、发布、付款、删除这类操作，都会先等你批准。

### 功能

- **对话 → 计划 → 执行**：每一步、每次工具调用都看得见。
- **邮箱（支持多个）**：Gmail、Outlook / Hotmail（OAuth 2.0 授权）、Yahoo、iCloud、QQ 邮箱、网易 163 / 126、Zoho、AOL 及任何 IMAP / SMTP 邮箱；搜索、阅读、草稿、回复、发送、一键退订；验证码和重置链接对模型自动屏蔽。
- **Notion 与 Slack**：查资料、写报告、更新任务表、读取和发送消息。
- **浏览器**：独立 Chromium，受限 API，实时画面，登录 / 验证码（CAPTCHA）可由你接管。
- **MCP 连接器**：接入任意 MCP（Model Context Protocol，模型上下文协议）服务器，工具定义锁定防篡改。
- **自动化**：持续多天推进的场景目标、事件触发（新邮件 / Slack 新消息 / Notion 变化）、定时任务。
- **Telegram 遥控**：在手机上布置任务、一键审批。
- **研究库**：交给它一个课题，它会深入研究写成 Markdown 报告；在课题对话里追问、修改，之后可刷新；所有报告都可被 Agent 搜索。
- **记忆与技能**，**中文 / English 界面**。

### 安全设计

| 层 | 作用 |
|---|---|
| **Sentinel 哨兵** | 独立的权限服务，对每个操作做 允许 / 拒绝 / 询问（ALLOW / DENY / ASK）决策。 |
| **凭据保险箱（Vault）** | 应用专用密码和令牌（token）加密保存在 Sentinel，Agent 和模型都看不到。 |
| **防提示注入（Prompt Injection）** | 邮件、网页、工具结果一律视为不可信；发现可疑内容时，所有写操作升级为人工审批。 |
| **审计记录（Audit Trail）** | 只追加、哈希链（hash chain）防篡改的日志，记录每次模型调用、工具调用、决策和审批。 |

### 安装

- **Olares 应用商店**：审核通过后搜索 *OMuse*。
- **手动安装**：`python3 build.py omuse`，然后在 Olares 应用商店 ▸ *上传自定义 Chart* 中上传 `dist/omuse-<版本>.tgz`。

模型接口默认是 `https://router.<你的 Olares 名称>.olares.com/v1`，可在应用设置或环境变量 `PERSONA_MODEL_URL` / `PERSONA_MODEL` 中修改；如果配置的模型不存在，OMuse 会自动选择一个可用模型。

---

License: [MIT](LICENSE) © 2026 Lucas Lu
