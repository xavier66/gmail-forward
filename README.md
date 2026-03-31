# Gmail 条件转发工具

根据配置规则自动转发 Gmail 邮件到指定邮箱。部署在服务器上常驻运行，通过 IMAP 轮询新邮件，SMTP 转发。

## 功能

- 按发件人、主题关键词过滤邮件
- 支持多条转发规则，每条规则可转发到多个收件人
- 发件人支持精确匹配和域名通配（`@domain.com`）
- 已处理邮件持久化，重启不遗漏不重复
- 自动断线重连

## 费用说明

> **本项目完全免费，所有依赖服务均零成本。**

| 组件 | 费用 | 说明 |
|------|------|------|
| Gmail IMAP/SMTP | **免费** | Gmail 内置功能，个人账号即可使用 |
| 应用专用密码 | **免费** | Google 账号设置中一键生成 |
| Python 及依赖库 | **免费** | 仅依赖 `pyyaml`，其余全部 Python 内置库 |
| 服务器 | 取决于你 | 可运行在任何已有服务器、VPS 或树莓派上 |

无隐藏费用，无付费计划，无需绑定信用卡。

## 前置条件

- Python 3.10+
- Gmail 账号（需开启两步验证）

## 快速开始

### 1. 生成应用专用密码

1. 打开 [Google 账号安全设置](https://myaccount.google.com/security)
2. 确保已开启 **两步验证**
3. 搜索 **应用专用密码**（或在两步验证页面底部找到）
4. 选择"邮件"，生成一个 16 位密码，复制备用

### 2. 安装

```bash
git clone https://github.com/xavier66/gmail-forward.git && cd gmail-forward
pip install -r requirements.txt
```

### 3. 配置

```bash
cp config.yaml.example config.yaml
```

编辑 `config.yaml`：

```yaml
gmail:
  email: your-email@gmail.com
  app_password: xxxx xxxx xxxx xxxx    # 第 1 步生成的应用专用密码

poll:
  interval_seconds: 5

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

### 4. 运行

```bash
python -m src.main
```

就这样，没有 OAuth 配置，没有 Google Cloud 项目，填好邮箱和密码就能跑。

## 规则说明

| 字段 | 说明 |
|------|------|
| `conditions.from` | 发件人匹配。精确地址或 `@domain.com` 域名通配 |
| `conditions.subject_contains` | 主题包含关键词（OR 匹配） |
| `forward_to` | 转发目标地址列表 |

同一规则内各条件为 AND 关系（全部满足才转发）。

## 服务器后台运行

```bash
nohup python -m src.main > output.log 2>&1 &
```

停止：`kill $(pgrep -f "python -m src.main")`

## 文件说明

```
gmail-forward/
├── src/
│   ├── main.py           # 主入口，轮询循环
│   ├── config.py         # YAML 配置加载
│   ├── imap_client.py    # IMAP 邮件获取
│   ├── filter_engine.py  # 邮件过滤引擎
│   ├── forwarder.py      # SMTP 邮件转发
│   └── state.py          # 状态持久化
├── config.yaml.example   # 配置模板
└── state.json            # 运行状态（自动生成）
```

## 注意事项

- 转发的邮件会出现在 Gmail **已发送** 文件夹
- `state.json` 记录已处理邮件，删除后将重新处理未读邮件
- 建议将 `poll.interval_seconds` 设为 5 秒（默认值），平衡及时性和资源消耗
