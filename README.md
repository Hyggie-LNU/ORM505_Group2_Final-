# LU DingTalk: A Locally Deployed Instant-Messaging Prototype

This repository contains a course project that pairs an MIT App Inventor mobile client with a Flask backend hosted on a local machine. User accounts and chat records reside on the host that runs the server, which supports an on-premises deployment model suitable for internal organisational use and classroom demonstration.

## Repository Layout

```
MTAgpFinal/
├── README.md
├── .gitignore
├── backend/
│   ├── app.py                 # Flask application: HTTP APIs and WebSocket endpoint (/ws)
│   └── requirements.txt       # Python dependencies
├── frontend/
│   ├── FinalVersion.aia       # Final MIT App Inventor project (import this file to build the app)
│   └── com.websocketext.aix   # WebSocket extension archive retained for reference only;
│                              # the extension is already embedded in FinalVersion.aia
└── Documents/
    ├── Briefing.md            # Project briefing (features and screen flow)
    ├── Report.pdf             # Final written report (to be added)
    ├── Slides                 # Oral presentation slides (to be added)
    └── demo.mp4               # Feature demonstration video (to be added)
```

## Prerequisites

- Python 3.10 or later
- A host computer that will run the backend
- An Android device on the **same local network** as the host
- Access to the MIT App Inventor web IDE

## Local Deployment

### 1. Clone the repository

In your preferred local working directory, run:

```bash
git clone https://github.com/Hyggie-LNU/ORM505_Group2_Final-.git
cd ORM505_Group2_Final-
```

### 2. Start the backend

Inside the `ORM505_Group2_Final-` folder, run:

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
# source venv/bin/activate

pip install -r requirements.txt
python app.py
```

When the server starts successfully, the console prints the listening addresses. Among them, use the **LAN address** (not `127.0.0.1`), for example:

```text
http://10.9.139.239:5000
```

Keep this process running while the mobile application is in use. On first launch, SQLite storage is created under `backend/instance/` (ignored by Git).

### 3. Configure and build the mobile client

1. Open the [MIT App Inventor](https://appinventor.mit.edu/) web IDE and **import** `frontend/FinalVersion.aia` only. A separate import of `com.websocketext.aix` is unnecessary for normal use; that file is kept in the repository solely as a reference copy of the embedded extension.
2. In the **Register** screen, open the **Blocks** editor and set the global variable `backendurl` to the LAN URL shown in the backend console (e.g. `http://10.9.139.239:5000`). Do **not** use `http://127.0.0.1:5000` or `localhost`: on the phone those addresses refer to the device itself, not the host running Flask.
3. Build the project as an **APK** and install it on the Android device.
4. Ensure the phone and the host remain on the same Wi-Fi (or equivalent LAN) and that `python app.py` continues to run.

### 4. Suggested verification path

1. Register and sign in on two devices (or two accounts).
2. Search by username, send a friend request, and accept it on the other account.
3. Open a chat from the friend list or the chat list and exchange messages to confirm real-time delivery.

## Notes

- This artefact is an educational prototype for local demonstration; it is not a production-grade security product.
- The default configuration uses HTTP on a local network and is intended for controlled classroom or intranet settings.
- Project documentation belongs under `Documents/`; the server under `backend/`; the App Inventor project under `frontend/`.

---

# 中文版

# LU DingTalk：可本地部署的即时通讯原型

本仓库为课程项目成果，包含 MIT App Inventor 手机客户端与运行于本地主机的 Flask 后端。用户账号与聊天记录保存在运行服务器的机器上，支持本地部署，适用于组织内部使用场景及课堂演示。

## 目录结构

```
MTAgpFinal/
├── README.md
├── .gitignore
├── backend/
│   ├── app.py                 # Flask 主程序：HTTP API 与 WebSocket 接口（/ws）
│   └── requirements.txt       # Python 依赖
├── frontend/
│   ├── FinalVersion.aia       # 最终 App Inventor 工程（导入此文件即可构建应用）
│   └── com.websocketext.aix   # WebSocket 扩展归档，仅作引用保留；
│                              # 该扩展已嵌入 FinalVersion.aia
└── Documents/
    ├── Briefing.md            # 项目 Briefing（功能与页面流程）
    ├── Report.pdf             # 期末书面报告（待补充）
    ├── Slides                 # 期末口头汇报幻灯片（待补充）
    └── demo.mp4               # 功能演示视频（待补充）
```

## 环境要求

- Python 3.10 或更高版本
- 一台用于运行后端的主机
- 与主机处于**同一局域网**的 Android 设备
- 可访问 MIT App Inventor 网页版 IDE

## 本地部署

### 1. 克隆仓库

在你的电脑工程目录下执行

```bash
git clone https://github.com/Hyggie-LNU/ORM505_Group2_Final-.git
cd ORM505_Group2_Final-
```

### 2. 启动后端

在ORM505_Group2_Final-文件夹中执行：

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
# source venv/bin/activate

pip install -r requirements.txt
python app.py
```

服务启动成功后，控制台会打印监听地址。请使用其中的**局域网地址**（不要使用 `127.0.0.1`），例如：

```text
http://10.9.139.239:5000
```

手机端使用期间请保持该进程持续运行。首次启动时，SQLite 数据库会自动生成于 `backend/instance/`（该目录已被 Git 忽略）。

### 3. 配置并打包手机端

1. 打开 [MIT App Inventor](https://appinventor.mit.edu/) 网页版 IDE，**仅导入** `frontend/FinalVersion.aia`。日常使用无需单独导入 `com.websocketext.aix`；该文件仅作为已嵌入扩展的引用副本保留在仓库中。
2. 进入 **Register** 屏幕，打开 **Blocks** 编辑器，将全局变量 `backendurl` 设为后端控制台显示的局域网地址（例如 `http://10.9.139.239:5000`）。**不要**使用 `http://127.0.0.1:5000` 或 `localhost`：在手机上，这些地址指向设备自身，而非运行 Flask 的主机。
3. 将工程打包为 **APK**，并安装到 Android 设备。
4. 确保手机与主机处于同一 Wi-Fi（或等效局域网），且 `python app.py` 持续运行。

### 4. 建议验证流程

1. 在两台设备（或两个账号）上分别注册并登录。
2. 按用户名搜索，发送好友申请，并在另一账号上同意。
3. 从好友列表或聊天列表进入会话，互发消息，确认可实时送达。

## 说明

- 本成果为用于本地演示的教学原型，并非生产级安全产品。
- 默认配置在局域网内使用 HTTP，适用于受控的课堂或内网环境。
- 文档置于 `Documents/`，服务端置于 `backend/`，App Inventor 工程置于 `frontend/`。
