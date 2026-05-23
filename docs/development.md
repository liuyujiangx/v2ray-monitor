# V2Ray Monitor 开发文档

## 1. 项目目标

这个项目是一个自用型 V2Ray 流量监控面板。它不追求复杂的多租户后台，而是优先解决个人服务器上的几个实际问题：

- 当前谁用了多少流量
- 今天和本月用了多少流量
- 哪些用户接近月度配额
- V2Ray API 是否正常
- 出问题时页面不要直接崩溃

## 2. 第一阶段功能

第一阶段先做成一个稳定可用的 dashboard。

### 页面能力

- 顶部状态区：
  - V2Ray API 状态
  - 最后更新时间
  - 总上传
  - 总下载
  - 总流量
- 用户流量表：
  - 用户名
  - 上传
  - 下载
  - 总量
  - 月度配额
  - 使用率
- inbound 流量表：
  - tag
  - 上传
  - 下载
  - 总量
- outbound 流量表：
  - tag
  - 上传
  - 下载
  - 总量

### API 能力

- `GET /`
  - 返回 dashboard 页面
- `GET /api/stats`
  - 返回当前 V2Ray stats 解析结果
- `GET /api/health`
  - 返回服务和 V2Ray API 状态

## 3. 第二阶段功能

第二阶段加入历史记录。

V2Ray stats 通常是累计值，所以历史统计不能简单把每次结果相加。正确做法是：

1. 定时采样当前累计值
2. 和上一条采样比较
3. 得到这一小段时间的增量
4. 把增量写入 SQLite
5. 查询今日、本周、本月时，对增量求和

### SQLite 建议表结构

```sql
CREATE TABLE traffic_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    name TEXT NOT NULL,
    direction TEXT NOT NULL,
    value_bytes INTEGER NOT NULL,
    delta_bytes INTEGER NOT NULL,
    sampled_at TEXT NOT NULL
);

CREATE INDEX idx_traffic_samples_lookup
ON traffic_samples (scope, name, direction, sampled_at);
```

字段说明：

- `scope`: `user`、`inbound`、`outbound`
- `name`: 用户名或 tag
- `direction`: `uplink`、`downlink`
- `value_bytes`: V2Ray API 返回的累计值
- `delta_bytes`: 和上一条记录相比的增量
- `sampled_at`: ISO 时间字符串

## 4. 第三阶段功能

第三阶段加入配额和提醒。

### 配额配置

在 `config.toml` 里配置：

```toml
[quota]
yujl = 100
alice = 50
```

单位是 GB。

### 提醒逻辑

建议支持三个阈值：

- 80%：提醒即将接近
- 90%：提醒需要关注
- 100%：提醒已经超额

提醒渠道优先级：

1. Bark，适合 iPhone 自用
2. Telegram Bot，适合跨设备
3. 邮件，作为后备

为了避免刷屏，同一个用户同一个自然月同一个阈值只提醒一次。

## 5. 配置设计

配置文件使用 `config.toml`，默认可以从 `config.example.toml` 复制。

```toml
[server]
host = "0.0.0.0"
port = 8000

[v2ray]
api_address = "127.0.0.1:10085"
command = "v2ray"

[dashboard]
refresh_seconds = 2

[auth]
enabled = true
username = "admin"
password = "change-me"

[database]
path = "data/traffic.sqlite3"
```

## 6. 部署建议

生产环境建议使用 `systemd` 管理：

```ini
[Unit]
Description=V2Ray Monitor
After=network.target

[Service]
WorkingDirectory=/opt/v2ray-monitor
ExecStart=/opt/v2ray-monitor/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

如果面板需要公网访问，建议放在 Nginx 后面，并开启 HTTPS。

## 7. 开发顺序

建议按下面顺序做，比较稳：

1. 重构项目结构，让页面和 API 能正常运行
2. 给 V2Ray 命令调用加错误处理
3. 完成实时总览和排序
4. 加入 SQLite 采样
5. 做今日 / 本月统计
6. 加入配额配置
7. 加入提醒
8. 加入登录保护
9. 写 systemd 和 Nginx 部署说明

