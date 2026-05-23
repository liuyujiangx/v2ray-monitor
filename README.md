# V2Ray Monitor

一个自用的 V2Ray 流量监控面板，基于 FastAPI。目标是实时查看用户、入站、出站流量，并逐步支持历史统计、月度配额和提醒。

## 功能规划

- 实时读取 `v2ray api stats` 输出
- 用户 / inbound / outbound 流量表格
- 总上传、总下载、总流量概览
- 最后更新时间和 V2Ray API 状态
- SQLite 历史采样
- 今日 / 本月流量统计
- 用户月度配额和超额提醒
- 简单密码保护

## 项目结构

```text
v2ray-monitor/
  app/
    main.py                # FastAPI 入口
    config.py              # 配置加载
    models.py              # 数据结构
    services/
      v2ray.py             # V2Ray stats 读取与解析
      history.py           # SQLite 历史记录
      alerts.py            # 配额提醒预留
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

## V2Ray 要求

V2Ray 需要启用 stats API，并让本项目可以访问配置里的 API 地址，默认是：

```text
127.0.0.1:10085
```

