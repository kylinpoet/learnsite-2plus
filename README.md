# LearnSite 2+

信息科技学生学习综合门户平台。

当前仓库已经完成从旧版单校 ASP.NET WebForms 教学站点向现代多学校门户的核心迁移骨架，当前技术栈为：

- 前端：Vue 3 + Vite + TypeScript + Element Plus
- 后端：FastAPI + SQLAlchemy + Alembic
- 开发数据库：SQLite

当前已打通的主链路：

- 学生登录、课堂主页、草稿保存、正式提交、提交历史、教师反馈查看
- 教师登录、开课、签到、课堂实时雷达、求助查看、作业批改、AI 草稿
- 管理员通过教师入口登录，在同一教师控制台中使用迁移兼容与治理能力
- 第二所学校演示数据与跨校治理上下文切换

## 目录结构

```text
.
├─ backend/                  FastAPI、SQLAlchemy、Alembic
│  ├─ app/
│  └─ alembic/
├─ frontend/                 Vue 3 + Vite 前端
├─ docs/                     设计文档、评审产物、设计预览
├─ DESIGN.md                 视觉与设计系统基线
├─ CLAUDE.md                 保留给 Codex / review workflow 的项目协作文档
└─ README.md
```

## 角色与测试账号

默认种子数据内置以下演示账号：

- 实验学校 A 学生：`240101 / 12345`
- 实验学校 A 教师：`kylin / 222221`
- 实验学校 A 管理员：`admin / 222221`
- 未来学校 B 学生：`250201 / 12345`
- 未来学校 B 教师：`linhua / 222221`
- 未来学校 B 管理员：`adminb / 222221`
- 平台管理员：`platform / 222221`

当前登录方式：

- 学生入口：`/`
- 教师 / 管理入口：`/teacher/login`

管理员不再使用独立后台首页，而是登录后直接进入教师控制台，并在同一页显示治理模块。

## 本地开发

推荐本地联调端口：

- 后端：`8001`
- 前端：`4174`

这样可以避开部分 Windows 环境中 `8000` 被打印服务占用的问题。

### 1. 启动后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

后端健康检查：

```powershell
Invoke-WebRequest http://127.0.0.1:8001/healthz
```

### 2. 启动前端

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev -- --host 127.0.0.1 --port 4174 --strictPort
```

前端默认访问地址：

- `http://127.0.0.1:4174`

## 环境变量

示例文件：

- `backend/.env.example`
- `frontend/.env.example`

关键变量：

- 后端：`LEARNSITE_SQLITE_URL`、`LEARNSITE_CORS_ORIGINS`
- 前端：`VITE_API_BASE_URL`

## 数据库与迁移

开发期默认使用 SQLite，本地数据库地址通过 `LEARNSITE_SQLITE_URL` 指定。

Alembic 常用命令：

```powershell
cd backend
python -m alembic upgrade head
python -m alembic downgrade -1
```

当前重要迁移：

- 初始结构
- 第二轮课堂工作流支持
- 第三轮批改历史与迁移修复支持

## 常用验证命令

### 后端语法校验

```powershell
python -m compileall backend/app
```

### 前端构建校验

```powershell
cd frontend
npm run build
```

## 当前实现说明

### 学生端

- 学生首页展示当前课堂、任务状态、提交版本、教师反馈、提交历史
- 支持保存草稿与正式提交
- 在“需要修改后重交”状态下允许继续编辑并重提

### 教师端

- 支持开课、签到、实时雷达、课堂求助队列
- 支持作业查看、批改反馈、AI 反馈草稿生成

### 管理能力

- 已合并进教师控制台
- 支持迁移预览问题修复、迁移执行、迁移回滚
- 平台管理员支持在同一治理面板中切换学校上下文
- 旧路由 `/admin/overview` 会自动回跳到 `/teacher/console`

## 视觉与前端说明

- 默认字体：`Noto Sans SC`
- 主题切换是风格切换，不是明暗模式切换
- 当前风格包含：
  - `Classroom Workshop`
  - `Material Design`
  - `Natural`

详细视觉基线请以 `DESIGN.md` 为准。

## 编码与终端

项目已补充：

- `.editorconfig`
- `.vscode/settings.json`

如果 PowerShell 中出现少量中文显示异常，优先怀疑终端编码显示问题，而不是源码本身损坏。

## 已知事项

- 本地开发数据库当前仍为 SQLite，仅适合开发验证
- 真实生产数据库选型尚未最终确定
- 本仓库仍处于高频迭代中，README 会随当前实现持续更新
