# Gmail 条件转发工具

根据配置规则自动转发 Gmail 邮件到指定邮箱。部署在服务器上常驻运行，通过 Gmail API 增量轮询新邮件。

## 功能

- 按发件人、主题关键词、标签过滤邮件
- 支持多条转发规则，每条规则可转发到多个收件人
- 发件人支持精确匹配和域名通配（`@domain.com`）
- 增量处理，重启不遗漏不重复
- 自动刷新 OAuth token，无需人工干预

## 前置条件

- Python 3.10+
- Google 账号

## Google Cloud 设置

### 1. 创建项目并启用 Gmail API

1. 打开 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目（或选择已有项目）
3. 进入 **API 和服务 → 库**，搜索 **Gmail API**，点击启用

### 2. 创建 OAuth 2.0 凭据

1. 进入 **API 和服务 → 凭据**
2. 点击 **创建凭据 → OAuth 客户端 ID**
3. 应用类型选择 **桌面应用**
4. 下载 JSON 文件，重命名为 `client_secret.json`
5. 放入项目的 `credentials/` 目录

### 3. 配置 OAuth 同意屏幕

1. 进入 **API 和服务 → OAuth 同意屏幕**
2. 选择 **外部**，填写应用名称和邮箱
3. 添加范围：`https://mail.google.com/`
4. 添加测试用户（你自己的 Gmail 地址）
5. **重要**：发布应用（设为"正式版"），否则 refresh_token 7 天后过期

## 安装

```bash
git clone <repo-url> && cd gmail-forward
pip install -r requirements.txt
```

## 配置

```bash
cp config.yaml.example config.yaml
```

编辑 `config.yaml`：

```yaml
gmail:
  client_secret_file: credentials/client_secret.json
  token_file: credentials/token.json

poll:
  interval_seconds: 30

rules:
  - name: "转发紧急邮件"
    conditions:
      from: ["boss@company.com"]
      subject_contains: ["紧急", "urgent"]
    forward_to: ["admin@company.com"]

  - name: "转发客户邮件"
    conditions:
      from: ["@client-domain.com"]
    forward_to:
      - "sales@company.com"
      - "manager@company.com"

forward:
  add_prefix: true
  include_original_headers: true
```

### 规则说明

| 字段 | 说明 |
|------|------|
| `conditions.from` | 发件人匹配。精确地址或 `@domain.com` 域名通配 |
| `conditions.subject_contains` | 主题包含关键词（OR 匹配） |
| `conditions.labels` | Gmail 标签（如 `INBOX`、`IMPORTANT`） |
| `forward_to` | 转发目标地址列表 |

同一规则内各条件为 AND 关系（全部满足才转发）。

## 运行

```bash
python -m src.main
```

首次运行会自动打开浏览器进行 OAuth 授权，授权后生成 `credentials/token.json`，之后无需再次授权。

## 服务器部署（systemd）

创建 `/etc/systemd/system/gmail-forward.service`：

```ini
[Unit]
Description=Gmail Forward Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/gmail-forward
ExecStart=/path/to/gmail-forward/.venv/bin/python -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable gmail-forward
sudo systemctl start gmail-forward
sudo systemctl status gmail-forward
```

## 文件说明

```
gmail-forward/
├── src/
│   ├── main.py           # 主入口，轮询循环
│   ├── config.py         # YAML 配置加载
│   ├── auth.py           # OAuth 2.0 认证
│   ├── gmail_client.py   # Gmail API 封装
│   ├── filter_engine.py  # 邮件过滤引擎
│   ├── forwarder.py      # 邮件转发
│   └── state.py          # 状态持久化
├── config.yaml.example   # 配置模板
├── credentials/          # OAuth 密钥和 token
└── state.json            # 运行状态（自动生成）
```

## 注意事项

- 转发的邮件会出现在你的 Gmail **已发送** 文件夹
- Gmail API 每天有用量配额（通常足够个人使用）
- `state.json` 记录处理进度，删除后将从当前邮件重新开始（不会转发旧邮件）
- 建议将 `poll.interval_seconds` 设为 30 秒以上，避免触发 API 限流
