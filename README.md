# V2Ray Monitor

一个自用的 V2Ray 流量监控面板，基于 FastAPI。当前目标是监控 AWS 服务器代理流量，重点避免超过每月 100GB 免费流量额度。

## 开源协议

本项目使用 MIT License。详见 [LICENSE](LICENSE)。

## 开源前安全说明

仓库只提交示例配置和源码，不提交真实运行配置。请不要把下面这些内容提交到 GitHub：

- `config.toml`
- `data/*.sqlite3`
- V2Ray access log / error log
- 密码、token、私钥、真实服务器 IP、真实用户访问日志

## 已有功能

- 实时读取 `v2ray api stats` 输出
- 用户 / inbound / outbound 累计流量表格
- V2Ray API 状态和最后更新时间
- SQLite 历史采样，不需要额外安装数据库
- 今日流量统计
- 本月流量统计
- AWS 月度总额度监控，默认 100GB
- 本月剩余额度和使用率
- 每个用户今日 / 本月流量
- 可选的用户参考额度和使用率进度条
- 实时上传 / 下载速度估算
- 页面内告警记录
- 月度流量阈值告警（80% / 90% / 100% 可配置）
- 新告警邮件通知（SMTP，可选）
- 每日用量邮件日报（SMTP，可选）
- V2Ray access log 读取
- 最近访问日志列表
- 按用户过滤访问日志
- 按域名 / IP / 用户搜索访问日志
- 访问域名排行
- 来源 IP 排行
- 简单 HTTP Basic 密码保护，默认关闭

## 即将开发

- Bark / Telegram 外部告警通知（配置项已预留 `provider`，尚未实现）
- 告警通知发送状态记录
- 最近 24 小时流量趋势图
- 本月每日流量柱状图
- 用户最后活跃时间
- 陌生来源 IP 告警
- 高风险访问频率提示
- CSV 导出
- systemd 部署文件
- Nginx 反向代理示例

## 项目结构

```text
v2ray-monitor/
  app/
    main.py                # FastAPI 入口
    config.py              # 配置加载
    models.py              # 数据结构
    services/
      access_log.py        # V2Ray access log 读取与解析
      alerts.py            # 告警规则
      notify.py            # 外部通知（邮件 SMTP 等）
      history.py           # SQLite 历史记录
      v2ray.py             # V2Ray stats 读取与解析
    static/
      css/app.css
      js/dashboard.js
    templates/
      index.html
  data/
    .gitkeep               # SQLite 数据库默认放这里
  docs/
    development.md         # 开发文档
  config.example.toml      # 配置示例
  requirements.txt
```

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.toml config.toml
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

打开：

```text
http://127.0.0.1:8000
```

## 服务器试运行

```bash
cd /opt/v2ray-monitor
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 7011
```

如果项目放在其他目录，把 `/opt/v2ray-monitor` 换成你的实际路径。

## 配置

复制示例配置：

```bash
cp config.example.toml config.toml
```

常用配置：

```toml
[v2ray]
api_address = "127.0.0.1:10085"
command = "v2ray"

[traffic]
monthly_quota_gb = 100

[logs]
access_path = "/var/log/v2ray/access.log"
max_lines = 500

[daily_report]
enabled = true
send_time = "09:00"
top_limit = 10
log_max_lines = 2000

[quota]
# 可选：仅用于面板展示单个用户参考额度，不参与总额度告警。
# 整个 V2Ray 的月度总额度由 [traffic].monthly_quota_gb 控制。
# yujl = 20

[auth]
enabled = false
username = "admin"
password = "change-me"

[alerts]
enabled = true
provider = "email"
thresholds = [80, 90, 100]

[alerts.email]
# 密码填网易「客户端授权码」，不是登录密码；勿将真实授权码提交到 Git
smtp_host = "smtp.163.com"
smtp_port = 465
use_tls = false
use_ssl = true
username = "you@163.com"
password = "your-163-client-auth-code"
from_addr = "you@163.com"
to_addrs = ["you@163.com"]
```

### 邮件告警示例

| 邮箱 | smtp_host | 端口 | 加密 |
|------|-----------|------|------|
| 网易 163 | `smtp.163.com` | 465（推荐）或 587 | 465：`use_ssl = true`；587：`use_tls = true` |
| Gmail | `smtp.gmail.com` | 587 | `use_tls = true` |
| QQ 邮箱 | `smtp.qq.com` | 465 | `use_ssl = true` |
| 企业邮 / 自建 | 向管理员索取 | 通常 587 或 465 | 按服务商说明 |

#### 网易 163 邮箱（告警推荐）

1. 浏览器登录 [网易邮箱](https://mail.163.com/) → **设置** → **POP3/SMTP/IMAP**。
2. 开启 **IMAP/SMTP** 或 **POP3/SMTP** 服务，在 **客户端授权密码** 处新增授权码（短信验证）；授权码只显示一次，请立即保存。
3. 编辑 `config.toml`：`provider = "email"`，在 `[alerts.email]` 中填写完整 `@163.com` 地址与授权码；`password` 必须是授权码，不能填网页登录密码。
4. **推荐**：`smtp.163.com`、端口 **465**、`use_ssl = true`、`use_tls = false`。若 465 被网络拦截，可改用端口 **587**、`use_tls = true`、`use_ssl = false`。

`provider = "none"` 时告警仅写入 SQLite 并在面板展示，不发告警邮件。每日用量日报由 `[daily_report]` 单独控制，但复用 `[alerts.email]` SMTP 配置。SMTP 字段不完整时会跳过发送并打 warning 日志，不影响 `/api/stats` 响应。

### 每日用量日报

开启 `[daily_report]` 后，服务进程会按本地时间每天发送一次邮件：

- 当前月度总额度、已用、剩余、使用率
- 今日已用流量
- 用户本月 / 今日用量排行
- access log 中访问最多的 URL / 目标地址
- access log 中出现过的来源 IP

面板顶部的“立即发送日报”按钮可以手动发送一次同样内容的邮件，不影响当天定时日报的发送记录。

注意：V2Ray access log 当前格式不包含每条访问的字节数，所以 URL 和来源 IP 排行统计的是访问次数，不是按流量字节排序。真正的 100GB 流量额度按整个 V2Ray 总流量统计，由 `[traffic].monthly_quota_gb` 控制。

## V2Ray 要求

V2Ray 需要启用 stats API，并让本项目可以访问配置里的 API 地址，默认是：

```text
127.0.0.1:10085
```

access log 建议配置为：

```json
"log": {
  "access": "/var/log/v2ray/access.log",
  "error": "/var/log/v2ray/error.log",
  "loglevel": "warning"
}
```

面板运行用户需要能读取 access log：

```bash
sudo chmod 755 /var/log/v2ray
sudo chmod 644 /var/log/v2ray/access.log
```
