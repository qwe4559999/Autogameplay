# AutoGamePlay — 开发交接文档

> 最后更新: 2026-03-24
> 本文档完整记录了项目从零到当前状态的全部开发历程，供接手人快速了解上下文。

---

## 一、项目概述

**AutoGamePlay** 是一个多游戏日常任务自动化统一平台，整合三款游戏自动化工具：

| 工具 | 游戏 | GitHub |
|------|------|--------|
| MAA (MaaAssistantArknights) | 明日方舟 | MaaAssistantArknights/MaaAssistantArknights |
| MaaEnd | 明日方舟:终末地 | MaaEnd/MaaEnd |
| OKWW (ok-wuthering-waves) | 鸣潮 | ok-oldking/ok-wuthering-waves |

**核心定位**: 进程编排器 — 不包含游戏自动化逻辑，仅启动/监控/调度外部工具。

**技术栈**: Python 3.10+ / PyQt6 + PyQt6-Fluent-Widgets (MSFluentWindow) / APScheduler / YAML

---

## 二、目录结构

```
autogameplay/
├── main.py                          # 入口：QApplication + 系统托盘 + 最小化到托盘
├── requirements.txt
├── config/
│   ├── hub.yaml                     # 全局配置（主题、托盘、工具路径）
│   └── schedules.yaml               # 定时任务（cron 表达式）
├── core/
│   ├── config_manager.py            # YAML 配置读写
│   ├── models.py                    # ScheduleEntry / RunHistory 数据模型
│   ├── plugin_manager.py            # 插件注册表 + 动态加载
│   ├── task_runner.py               # QObject 信号驱动的线程任务引擎
│   └── scheduler.py                 # APScheduler (QtScheduler) cron 封装
├── plugins/
│   ├── base.py                      # GamePlugin 抽象基类
│   ├── maa_arknights/adapter.py     # MAA 适配器 (394行，最复杂)
│   ├── maaend_endfield/adapter.py   # MaaEnd 适配器 (刚重写)
│   └── okww_wutheringwaves/adapter.py # OKWW 适配器 (131行，最简单)
├── ui/
│   ├── main_window.py               # MSFluentWindow 侧边栏主窗口
│   ├── dashboard_page.py            # 仪表盘：三游戏状态卡片 + 一键运行
│   ├── game_page.py                 # 单游戏页：路径配置 + 运行/停止 + 日志
│   ├── schedule_page.py             # 定时任务管理 (cron 表达式 + 预设)
│   ├── log_page.py                  # 全局日志查看器
│   └── settings_page.py             # 设置：主题、托盘、工具路径
└── logs/
    └── autogameplay.log
```

---

## 三、核心架构

### 插件系统

```
GamePlugin (ABC)        ← plugins/base.py
├── plugin_id / display_name / game_name / icon_name (抽象属性)
├── validate_installation() → (bool, str)
├── get_available_tasks() → list[TaskDefinition]
├── run_tasks(task_ids, callback) → TaskResult    ← 核心方法，在工作线程中执行
├── stop()
├── load_config(dict)
├── get_install_path() / get_executable()
└── get_game_path() / get_game_start_delay()     ← Round 6 新增
```

每个适配器模块必须导出 `get_plugin() -> GamePlugin` 工厂函数。

`PluginManager` 通过 `PLUGIN_REGISTRY` 字典动态 `importlib.import_module()` 加载。

### 线程模型

```
主线程 (Qt UI)
├── TaskRunner (QObject) ──── 信号: log_received / task_started / task_completed
│   ├── TaskWorker (QThread) ──── 调用 plugin.run_tasks() 在后台线程
│   └── SequentialRunner (QThread) ──── 多插件顺序执行（定时 "全部运行"）
└── MainWindow
    ├── 接收 log_received → 转发到 GamePage.append_log() + LogPage
    ├── 接收 task_started → 刷新 DashboardPage 状态
    └── 接收 task_completed → 刷新 Dashboard + GamePage 按钮状态
```

**关键**: `TaskWorker.log_message` 信号通过 `QueuedConnection` 跨线程安全更新 UI。最初的版本使用普通 Python 回调，导致线程不安全的 UI 更新（已在 Round 4 修复）。

### 配置流

```
hub.yaml
└── ConfigManager._hub_config
    └── PluginManager.load_all() → plugin.load_config(tool_config)
        └── 各适配器通过 self._config.get("install_path") 等访问

用户在 SettingsPage 修改路径 → config_saved 信号 → MainWindow 刷新所有 GamePage
```

---

## 四、各适配器集成方式

### MAA (明日方舟) — `plugins/maa_arknights/adapter.py`

**集成方式**: subprocess + gui.json 配置注入 + gui.log 日志监控

**完整流程**:
1. 读取 MAA 的 `config/gui.json`，备份 `Start.RunDirectly` 原始值
2. 设置 `Start.RunDirectly = "True"`（MAA 启动即自动执行已配置的任务）
3. `subprocess.Popen([MAA.exe])` 启动 MAA
4. 轮询监控 `debug/gui.log`（2秒间隔），从上次偏移量读取新增内容
5. 检测关键字：
   - `"任务已全部完成"` → 任务成功
   - `"TaskQueueViewModel" + "Error"` → 任务失败
   - `"restarting application"` → MAA 更新重启（见下文）
6. 恢复 gui.json 中 `Start.RunDirectly` 原始值
7. `taskkill` 关闭 MAA.exe + 模拟器进程

**MAA 更新重启处理** (Round 5):
- MAA 配置了 `AutoDownloadUpdatePackage: True` + `AutoInstallUpdatePackage: True`
- 更新时 MAA 进程退出并重启，gui.log 中出现 `"restarting application"`
- 适配器检测到重启信号后，不退出监控循环，而是通过 `tasklist` 查找新 MAA.exe 进程
- 找到新进程后继续监控 gui.log，最多等待 30 秒

**模拟器自动关闭**:
- 从 gui.json 的 `Connect.ConnectConfig` 字段判断模拟器类型
- 支持 MuMu12 / BlueStacks / LDPlayer / Nox 四种模拟器
- 通过 `taskkill /F /IM` 关闭对应进程

**用户工具路径** (当前配置):
```
C:\Users\hyr\Downloads\MAA-v5.16.4-win-x64\MAA.exe
```

### MaaEnd (终末地) — `plugins/maaend_endfield/adapter.py`

**集成方式**: UAC 提权启动 + mxu-MaaEnd.json 配置注入 + 双日志监控

**核心难点与解决方案**:

| 难点 | 原因 | 解决方案 |
|------|------|----------|
| UAC 提权 | interface.json 中所有 Win32 控制器声明 `permission_required: true` | `ctypes.windll.shell32.ShellExecuteW` + `"runas"` 动词 |
| 无法获取进程句柄 | ShellExecuteW 不返回 Popen 对象 | 通过 `tasklist /FI "IMAGENAME eq MaaEnd.exe"` 追踪进程 |
| 启动即运行 | 默认 `autoRunOnLaunch: false` | 配置注入，启动前改为 `true`，完成后恢复 |
| 游戏需提前启动 | MaaEnd 通过 Win32 API 查找 `UnityWndClass` 窗口名 `Endfield` | 支持配置 `game_path`，可选自动启动游戏并等待 |

**完整流程**:
1. （可选）通过 `os.startfile(game_path)` 启动终末地游戏
2. 等待 `game_start_delay` 秒（默认 30s）
3. 读取 `config/mxu-MaaEnd.json`，设置 `autoRunOnLaunch=true`
4. `ShellExecuteW("runas", MaaEnd.exe)` 启动（弹出 UAC 对话框）
5. 通过 `tasklist` 等待确认 MaaEnd.exe 进程出现（最多 15s）
6. 同时监控两个日志文件：
   - `debug/go-service.log`（JSON格式）: 检测 `"Agent server shutdown"` = **最终完成信号**
   - `debug/maa.log`: 检测 `Tasker.Task.Succeeded/Failed/Starting` = **任务进度**
7. 恢复 `autoRunOnLaunch` 原始值
8. `taskkill` 关闭 MaaEnd.exe + go-service.exe + cpp-algo.exe
9. 通过 `tasklist /FI "WINDOWTITLE eq Endfield"` 查找并关闭游戏进程

**注意**: `MaaTaskerPostStop` 在实际日志中**未出现**，不可作为完成检测依据。

**用户工具路径** (当前配置):
```
D:\迅雷下载\MaaEnd-win-x86_64-v1.16.0\MaaEnd.exe
```

### OKWW (鸣潮) — `plugins/okww_wutheringwaves/adapter.py`

**集成方式**: 最简单，直接 subprocess + CLI 参数 + stdout 捕获

**流程**:
1. `subprocess.Popen([ok-ww.exe, -t, N, -e])` — `-t` 指定任务编号，`-e` 自动退出
2. 逐行读取 stdout 转发到 UI
3. 检查返回码判断成功/失败

**可用任务**: daily (`-t 1 -e`) / farm (`-t 2 -e`)

**用户工具路径** (当前配置):
```
C:/Users/hyr/AppData/Local/ok-ww/ok-ww.exe
```

---

## 五、开发轮次详细记录

### Round 1 — 市场调研 + 项目初始化

**目标**: 调研是否有现成的整合方案

**结论**: 市面上没有整合 MAA + MaaEnd + OKWW 的开源项目，决定从零创建。

**产出**: 项目骨架、所有目录结构、requirements.txt、hub.yaml 初始配置。

### Round 2 — 基础 UI + 插件系统

**目标**: 搭建 PyQt6 界面和插件框架

**产出**:
- MSFluentWindow 主窗口 + 侧边栏导航
- DashboardPage (状态卡片) / GamePage (路径+运行+日志) / SchedulePage / LogPage / SettingsPage
- GamePlugin 抽象基类 + PluginManager 动态加载
- APScheduler 封装 (QtScheduler + CronTrigger)
- 系统托盘 + 最小化到托盘

### Round 3 — MAA 集成（Python bindings → subprocess）

**目标**: 集成 MAA 实现明日方舟日常自动化

**方案演变**:
1. **初始方案**: 直接 `subprocess.Popen([MAA.exe])` → 问题：MAA 启动后不会自动开始执行任务，需要手动点 "Link Start"
2. **尝试 Python bindings**: 加载 `MaaCore.dll` 通过 Python API 控制 → **失败**: `[WinError 1114]` DLL 初始化失败，因为 DirectML.dll / onnxruntime_maa.dll 等依赖链在外部 Python 进程中初始化不了
3. **最终方案**: subprocess + gui.json 配置注入 → 设置 `Start.RunDirectly=True` 让 MAA 启动即运行 + 监控 gui.log 检测完成

**教训**: 不要尝试加载第三方工具的 DLL，subprocess + 配置注入 + 日志监控是最稳定的集成方式。

### Round 4 — Bug 修复（仪表盘状态 + 自动关闭 + 线程安全 + 设置同步）

**修复的 Bug**:

| Bug | 原因 | 修复 |
|-----|------|------|
| 仪表盘不显示"运行中" | task_started 时没刷新 dashboard | 添加 `task_started = pyqtSignal(str)`，连接到 `dashboard.refresh_status()` |
| 线程不安全的 UI 更新 | TaskRunner 用普通 Python 回调跨线程更新 QTextEdit | TaskRunner 改为 QObject，回调改为 pyqtSignal（自动 QueuedConnection） |
| 任务完成后不关闭 MAA/模拟器 | 只监控完成但没有清理进程 | 添加 `_cleanup_processes()` 通过 taskkill 关闭 MAA + 模拟器 |
| 设置中路径不同步到游戏页 | GamePage.path_edit 只在构造时设置 | 添加 `refresh_config()` + `config_saved` 信号 |
| MAA 不自动开始执行 | 启动 MAA.exe 只打开 GUI 不执行 | gui.json 注入 `Start.RunDirectly=True` |

### Round 5 — MAA 更新重启处理

**目标**: MAA 启动时如遇更新（应用更新/资源更新），平台能自动等待更新完成后继续监控

**MAA 更新机制**:
- `gui.json` 中 `AutoDownloadUpdatePackage: True` + `AutoInstallUpdatePackage: True`
- 更新时进程退出重启，gui.log 输出 `"restarting application"`
- 资源更新在后台进行，不影响进程

**修改**: 在监控循环中检测进程退出时：
1. 最终读取 gui.log 检查是否有 `"restarting application"`
2. 如果检测到重启信号 → 通过 `tasklist` 查找新 MAA.exe 进程（排除旧 PID）→ 继续监控
3. 如果 30 秒内未找到新进程 → 报超时

新增方法: `_find_maa_process(exclude_pid)` / `_is_maa_alive()`

### Round 6 — MaaEnd 适配器重写

**目标**: 解决 MaaEnd 三个问题：UAC 提权、自动运行、自动关闭

**状态**: 适配器代码已重写完成，**尚未测试**。

**新增功能**:
- `base.py`: 新增 `get_game_path()` / `get_game_start_delay()` 方法
- MaaEnd 适配器完全重写（详见第四节）
- 支持可选的游戏路径配置（用户通过快捷方式启动终末地）

### Round 7 — MaaEnd UI 接线 + Run All 信号流修复

**目标**: 将 MaaEnd 适配器暴露的配置能力接到 UI，并修复 Dashboard 一键运行绕开 TaskRunner 导致的状态/日志不同步问题

**状态**: 已编码完成，**仅做过编译检查，尚未联调实测**。

**新增功能**:
- `ui/settings_page.py`: 为 MaaEnd 增加 `game_path` 和 `game_start_delay` 配置项
- `ui/game_page.py`: MaaEnd 页面增加游戏路径与启动等待配置，并将“打开工具配置”改为 UAC 提权启动
- `config/hub.yaml`: MaaEnd 配置增加 `game_path` 和 `game_start_delay` 默认字段
- `core/task_runner.py`: 为 `SequentialRunner` 增加统一的任务开始/日志/完成出口，补齐外部执行路径的运行态管理
- `ui/main_window.py`: `task_started` 时同步刷新 `DashboardPage` 和对应 `GamePage`
- `ui/dashboard_page.py`: “一键全部运行”改为通过 `TaskRunner` 信号链驱动日志和状态刷新

---

## 六、尚未完成的工作

### 已编码但未测试

- [x] MaaEnd 适配器重写 (Round 6)
  - UAC 提权启动 (`ShellExecuteW + runas`)
  - `autoRunOnLaunch` 配置注入
  - 双日志监控 (`go-service.log` + `maa.log`)
  - 游戏启动 + 自动关闭
- [x] MAA 更新重启处理 (Round 5)
  - `"restarting application"` 检测
  - 新进程查找 + 继续监控
- [x] MaaEnd UI 接线 + Run All 信号流修复 (Round 7)
  - Settings/GamePage 支持 `game_path` / `game_start_delay`
  - MaaEnd “打开工具配置”走 UAC 提权
  - `SequentialRunner` 接入 `TaskRunner` 信号链
  - Dashboard / GamePage / LogPage 在“一键全部运行”时保持同步

### 需要新增的 UI/配置

- [ ] 如果后续新增其他“需要先启动游戏”的插件，需要把 `ui/game_page.py` 中当前对 MaaEnd 的专门处理抽象成通用能力开关

### 功能缺失

- [ ] OKWW 适配器没有自动关闭游戏/工具的逻辑
- [ ] 没有 Git 初始提交（所有文件仍为 untracked）
- [ ] 没有图标资源（`ui/resources/` 为空，各游戏的 icon_name 引用了不存在的图标文件）
- [ ] 没有错误重试机制（任务失败后不会自动重试）
- [ ] “一键全部运行”位于 `DashboardPage`，不是 `SchedulePage`；当前虽然已接入 `TaskRunner` 信号链，但还没有自动化测试覆盖异常/停止场景
- [ ] 没有运行历史记录持久化（`RunHistory` 数据模型存在但未使用）
- [ ] 没有通知功能（任务完成后无推送通知）

### 已知风险

- **MAA gui.json 格式变更**: 如果 MAA 大版本更新改变了 gui.json 结构（特别是 `Start.RunDirectly` 字段），适配器会失效
- **MaaEnd 配置格式变更**: 同理，`mxu-MaaEnd.json` 的 `autoRunOnLaunch` 字段
- **编码问题**: MAA 和 MaaEnd 的 JSON 配置文件使用 `utf-8-sig`（BOM），读写时必须用 `encoding="utf-8-sig"`
- **tasklist 解析**: `_find_process()` 依赖 CSV 输出格式，不同 Windows 语言环境的输出格式可能不同
- **UAC 静默失败**: 如果用户取消 UAC 弹窗，`ShellExecuteW` 返回错误码但不抛异常，需要检查返回值 > 32

---

## 七、当前用户环境

| 项目 | 值 |
|------|-----|
| 操作系统 | Windows 11 Pro 10.0.26200 |
| MAA 路径 | `C:\Users\hyr\Downloads\MAA-v5.16.4-win-x64` |
| MAA 版本 | v5.16.4 (gui.json 中 VersionName) |
| MaaEnd 路径 | `D:\迅雷下载\MaaEnd-win-x86_64-v1.16.0` |
| MaaEnd 版本 | v1.16.0 → v2.1.0 (有过更新) |
| OKWW 路径 | `C:/Users/hyr/AppData/Local/ok-ww` |
| 模拟器 | MuMu Player 12 (`C:\Program Files\Netease\MuMu Player 12`) |
| 终末地启动 | 通过桌面快捷方式 |
| Python | 需要 3.10+ |

---

## 八、关键配置文件结构参考

### MAA gui.json (关键字段)

```json
{
  "Current": "Default",
  "Global": {
    "AutoDownloadUpdatePackage": "True",
    "AutoInstallUpdatePackage": "True",
    "StartupUpdateCheck": "True"
  },
  "Configurations": {
    "Default": {
      "Start.RunDirectly": "False",         // ← 我们注入为 "True"
      "Start.EmulatorPath": "C:\\Users\\hyr\\Desktop\\#0 MuMu安卓设备.lnk",
      "Connect.ConnectConfig": "MuMuEmulator12",
      "Connect.MuMu12EmulatorPath": "C:\\Program Files\\Netease\\MuMu Player 12",
      "MainFunction.PostActions": "0"
    }
  }
}
```

### MaaEnd mxu-MaaEnd.json (关键字段)

```json
{
  "autoRunOnLaunch": false,              // ← 我们注入为 true
  "minimizeToTray": false,
  "preActionConnectDelaySec": 5,
  "hotkeys": { "startTasks": "F10", "stopTasks": "F11" },
  "instances": [
    {
      "id": "qxityzx",
      "name": "全套日常",
      "tasks": ["FriendVisitMain", "DijiangRewards", ...]
    }
  ]
}
```

### MaaEnd interface.json (控制器定义)

```json
{
  "controller": [
    {
      "name": "Win32-Front",
      "type": "win32",
      "win32": {
        "class_regex": "UnityWndClass",
        "window_regex": "Endfield"
      },
      "permission_required": true          // ← 要求管理员权限
    }
  ]
}
```

---

## 九、日志关键字速查

### MAA (gui.log)

| 关键字 | 含义 |
|--------|------|
| `任务已全部完成` | 所有日常任务执行完成 |
| `TaskQueueViewModel` + `Error` | 任务队列出错 |
| `restarting application` | MAA 更新后自动重启 |
| `Pending update package` | 检测到待安装的更新包 |

### MaaEnd (go-service.log, JSON 格式)

| 关键字 | 含义 |
|--------|------|
| `"Agent server shutdown"` | 所有任务完成，agent 关闭（**最终信号**） |

### MaaEnd (maa.log, 文本格式)

| 关键字 | 含义 |
|--------|------|
| `Tasker.Task.Starting` | 开始执行某个任务 |
| `Tasker.Task.Succeeded` | 某个任务执行成功 |
| `Tasker.Task.Failed` | 某个任务执行失败 |

---

## 十、如何运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动
python main.py
```

首次启动后在"设置"页面配置三个工具的安装路径，然后在各游戏页面点击"立即运行"测试。

定时任务在"定时任务"页面配置 cron 表达式（如 `0 4 * * *` 表示每天凌晨 4 点执行）。
