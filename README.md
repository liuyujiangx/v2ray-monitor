# V2Ray Monitor

一个自用的 V2Ray 流量监控面板，基于 FastAPI。当前目标是监控 AWS 服务器代理流量，重点避免超过每月 100GB 免费流量额度。

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
- 每个用户月度配额和使用率进度条
- 实时上传 / 下载速度估算
- 页面内告警记录
- V2Ray access log 读取
- 最近访问日志列表
- 按用户过滤访问日志
- 按域名 / IP / 用户搜索访问日志
- 访问域名排行
- 来源 IP 排行
- 简单 HTTP Basic 密码保护，默认关闭

## 即将开发

- Bark / Telegram 外部告警通知
- 告警通知去重和发送状态记录
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
cd /home/ec2-user/project/v2ray-monitor
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 7011
```

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

[quota]
# 单位 GB，用户名需要和 V2Ray stats 里的 email 一致。
# yujl = 60
# other = 20

[auth]
enabled = false
username = "admin"
password = "change-me"
```

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
