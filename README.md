# AutoGamePlay

AutoGamePlay 是一个 Windows 桌面端的多游戏日常自动化编排器。

它不包含游戏自动化逻辑本身，而是统一管理外部工具的启动、停止、日志转发和定时调度。目前集成了：

- `MAA` 用于明日方舟
- `MaaEnd` 用于明日方舟：终末地
- `OKWW` 用于鸣潮

## 特性

- 基于 `PyQt6` 的桌面界面
- 多游戏统一入口
- 单游戏即时运行与停止
- Dashboard 一键顺序运行
- 基于 `APScheduler` 的 Cron 定时任务
- 工具日志转发到应用内日志页
- MaaEnd 的 UAC 提权启动与可选游戏预启动

## 技术栈

- Python 3.10+
- PyQt6
- PyQt6-Fluent-Widgets
- APScheduler
- PyYAML

## 目录结构

```text
autogameplay/
├── main.py
├── config/
├── core/
├── plugins/
├── ui/
└── DEVELOPMENT_HANDOFF.md
```

## 安装

```powershell
pip install -r requirements.txt
```

## 运行

```powershell
python main.py
```

## 配置

首次使用时需要在应用的“设置”页面配置各工具安装路径。

仓库提供了示例配置文件：

- [`config/hub.example.yaml`](/D:/document/autogameplay/config/hub.example.yaml)

当前默认配置文件是：

- [`config/hub.yaml`](/D:/document/autogameplay/config/hub.yaml)

MaaEnd 额外支持：

- `game_path`：终末地启动快捷方式或可执行文件路径
- `game_start_delay`：启动游戏后等待 MaaEnd 接管的秒数

## 已知限制

- 仅面向 Windows 环境
- 强依赖外部自动化工具的安装目录和配置格式
- 暂无自动化测试
- 暂无运行历史持久化、通知和失败重试

## 开发说明

详细开发过程、架构说明和当前待办见：

- [`DEVELOPMENT_HANDOFF.md`](/D:/document/autogameplay/DEVELOPMENT_HANDOFF.md)

## License

MIT
