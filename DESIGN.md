# Design System — LearnSite 2+

## Product Context
- **What this is:** 一个面向初中信息科技课堂的多学校教学操作系统。它不是通用 LMS，而是把“备课、上课、签到、作品、迁移、治理”这一整套课堂工作流重新设计成现代 Web 应用。
- **Who it's for:** 学生、信息科技教师、学校管理员、平台管理员。
- **Space/industry:** K-12 教育软件、课堂管理平台、校内教学门户。
- **Project type:** Web app。学生端偏任务驱动，教师端偏工作台，管理端偏治理控制台。

## Design Summary
- **Aesthetic:** `Daylight Workshop`
- **Decoration:** `intentional`
- **Layout:** `hybrid`
- **Color:** `balanced`
- **Motion:** `intentional`

这个系统要同时满足三件事：
- 学生端要有进入感和参与感，但不能幼稚化。
- 教师端要像课堂驾驶舱，优先效率，不像营销后台。
- 管理端要有强信任感、强上下文、强风险提示。

## Safe Choices
- 教师端和管理端使用稳定、低饱和、可扫描的工作台布局。因为这是教育软件的基线，老师和管理员需要立刻理解，不需要重新学习视觉语言。
- 过滤器、表格、状态标签、批处理页面使用明确的结构和语义色。因为校内系统高频、重复、压力大，设计首先要服务于正确操作。
- 学生端首页把“当前课堂 / 当前任务”放在第一屏。因为对学生来说，最重要的不是探索，而是知道现在该做什么。

## Deliberate Risks
- **Risk 1: 学生端首屏做成“任务舞台”，不用通用功能卡片网格。**
  Gain: 产品一眼可辨，不像所有 AI 生成的教育 SaaS。
  Cost: 需要更强的构图和内容优先级控制。

- **Risk 2: 在学生端通过构图、色彩和模块比例建立识别度，而不是依赖特殊字体。**
  Gain: 保持实现稳定和字体兼容性，同时仍然让学生端有清晰个性。
  Cost: 需要更强的版式控制，不能靠“特别字体”偷懒。

- **Risk 3: 用暖纸面中性色替代冷白企业底色。**
  Gain: 更像真实课堂与学习材料，减少“冷后台”感。
  Cost: 需要更严格控制对比度和状态色，不然会显脏。

## Aesthetic Direction
- **Direction:** Daylight Workshop
- **Decoration level:** intentional
- **Mood:** 像阳光充足的计算机教室和一本被认真使用的学习手册。不是未来感炫技，不是企业冷后台，也不是低幼卡通。
- **Reference logic:** 学生端借鉴产品海报与任务舞台的构图思维；教师端和后台端借鉴专业工作台与轻工业仪表板的秩序感。

## Typography
- **Display/Hero:** `Noto Sans SC` — 使用更高字重和更大的字号承担标题角色，不使用特殊装饰字体。
- **Body:** `Noto Sans SC` — 中文覆盖完整，长时间阅读稳定，适合学生、教师、管理员三端统一正文。
- **UI/Labels:** `Noto Sans SC` — 表单、按钮、导航、状态标签统一使用。
- **Data/Tables:** `Noto Sans SC` for text + `IBM Plex Mono` for numeric emphasis — 管理端表格文本保持可读，数字列和运行状态用等宽字增加扫描效率。
- **Code:** `IBM Plex Mono`
- **Loading:** Google Fonts
  - `https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;900&family=IBM+Plex+Mono:wght@400;500;600&display=swap`
- **Scale:**
  - Hero XL: `56/64`
  - Hero L: `48/56`
  - H1: `40/48`
  - H2: `32/40`
  - H3: `24/32`
  - H4: `20/28`
  - Body L: `18/28`
  - Body: `16/24`
  - Small: `14/20`
  - Caption: `12/16`

### Typography Rules
- 全站默认标题与正文字体统一为 `Noto Sans SC`。
- 标题层级通过字重、字号、留白和色块建立，不依赖特殊展示字体。
- 后台端数字、批次状态、日志时间统一使用等宽数字表现。

## Color
- **Approach:** balanced
- **Primary:** `#1F6A5A` — 深青苔绿，代表专注、可信、课堂秩序。
- **Secondary:** `#F29A2E` — 温暖橙，代表行动、提醒、课堂活力。
- **Accent Blue:** `#2E7AD7` — 信息状态与链接。
- **Neutrals:**
  - Paper 0: `#FFFCF7`
  - Paper 1: `#FBF7EE`
  - Paper 2: `#F3EBDC`
  - Line: `#D8CCB8`
  - Quiet Text: `#7B7368`
  - Ink: `#1F262B`
- **Semantic:**
  - Success: `#2F9E6F`
  - Warning: `#D98A1F`
  - Error: `#C84B47`
  - Info: `#2E7AD7`
  - In Progress: `#0E9AA7`

## Theme Styles
本项目的“主题切换”不是亮色/暗色切换，而是**不同设计风格主题**。所有主题共享同一套信息架构、组件语义和可访问性要求，但在视觉语言上明显不同。

### Theme 1 — Material Design
- **Style keywords:** structured, clear, elevated, systemized
- **Primary:** `#1565C0`
- **Secondary:** `#26A69A`
- **Surface:** `#FAFBFC`
- **Line:** `#D9E0E6`
- **Feel:** 清晰、标准、稳定，适合学校希望“现代、熟悉、规范”的默认方案
- **Component traits:** 较强层次感、适度阴影、明确容器、规则圆角

### Theme 2 — Natural
- **Style keywords:** organic, warm, earthy, breathable
- **Primary:** `#506B2D`
- **Secondary:** `#C48B3A`
- **Surface:** `#F7F2E7`
- **Line:** `#D9CBB4`
- **Feel:** 自然和有机风格，采用大地色系和植物元素，展现自然温暖、有机视觉特性和环保色彩
- **Component traits:** 更柔和的底色、轻纹理、较少科技感、更多留白和缓和分隔

### Theme 3 — Classroom Workshop
- **Style keywords:** practical, editorial, warm, focused
- **Primary:** `#1F6A5A`
- **Secondary:** `#F29A2E`
- **Surface:** `#FBF7EE`
- **Line:** `#D8CCB8`
- **Feel:** 像计算机教室和学习手册的结合，是本项目当前推荐的默认主题
- **Component traits:** 暖纸面底色、明确任务区块、强工作台层级

## Spacing
- **Base unit:** `4px`
- **Density:** `comfortable`
- **Scale:** `2 / 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 80`

### Spacing Rules
- 学生端 Hero 与大模块优先使用 `24 / 32 / 48`
- 教师端主工作区优先使用 `16 / 24`
- 管理端表单与表格优先使用 `12 / 16 / 24`

## Layout
- **Approach:** hybrid
- **Grid:**
  - Desktop `>=1440`: 12 columns
  - Desktop `1024-1439`: 12 columns
  - Tablet `768-1023`: 8 columns
  - Mobile `390-767`: 4 columns
- **Max content width:** `1360px`
- **Border radius:**
  - xs: `8px`
  - sm: `12px`
  - md: `16px`
  - lg: `24px`
  - pill: `999px`

### Layout Rules
- 学生端首屏优先海报式构图，不做“卡片瀑布流”。
- 教师端关键页面优先三栏工作台：状态 / 主任务 / 智能辅助。
- 管理端高风险页面优先双栏或分区工作区，必须先看到上下文，再看到操作按钮。
- 不同风格主题只改变视觉表达，不改变核心布局骨架。

## Motion
- **Approach:** intentional
- **Easing:**
  - enter: `cubic-bezier(0.22, 1, 0.36, 1)`
  - exit: `cubic-bezier(0.4, 0, 1, 1)`
  - move: `cubic-bezier(0.4, 0, 0.2, 1)`
- **Duration:**
  - micro: `80ms`
  - short: `180ms`
  - medium: `280ms`
  - long: `420ms`

### Motion Rules
- 学生端允许轻微浮动、错位进入和任务完成反馈。
- 教师端和管理端动画只服务于状态变化和层级转换。
- 所有加载动画必须可中断，不得造成“等动画播完才能操作”。

## Screen-Specific Guidance

### Student
- 首屏第一屏只允许三个主区：当前课堂、今日待办、我的进度。
- 登录页必须像“进入课堂”，不是后台登录框。
- 作品提交成功要有明确完成反馈，不要只是 toast。

### Teacher
- 上课控制台不能像普通 dashboard，而要像“当前课次的操作台”。
- 课堂实时雷达必须长期可见，异常状态永远比普通状态优先。
- AI 副驾是右侧辅助区，不得盖过主课堂工作区。

### Admin
- 迁移兼容中心优先“预检 -> 预览 -> 执行 -> 回滚”的流程语言。
- 风险操作区必须用不同底色、不同标题语气、不同按钮层级区分。
- 任何批量操作都必须看到当前学校、当前学年、当前批次的上下文。

## Interaction States

### Required States
- loading
- empty
- error
- success
- partial success
- offline / reconnecting

### State Tone
- 学生端空状态要温和、有引导，不允许冷冰冰“暂无数据”。
- 教师端错误状态要清楚“发生了什么、现在能做什么”。
- 管理端 partial 状态必须给出错误行、失败原因、下一步动作。

## Accessibility
- Keyboard-first navigation on teacher/admin core pages
- Minimum touch target `44px`
- WCAG AA contrast minimum
- 状态信息不能只靠颜色表达
- 表格、图表、雷达状态都要有文本替代表达
- 教师端与后台端所有主操作必须有清晰焦点样式

## Component Guidance

### Cards
- 卡片只在“卡片本身就是信息单元”时使用。
- 学生端允许任务卡，但教师端和后台端禁止装饰性卡片墙。

### Tables
- 后台表格优先浅纸面 + 细分隔线，不用重边框表格。
- 数字列和批次状态列优先等宽数字。

### Charts
- 只在趋势和对比有意义时使用图表。
- 管理端图表必须能截图、能打印、能被灰度识别。

### Alerts
- 成功、警告、错误、信息四类状态都必须有统一图标、颜色、标题和正文结构。

## Anti-Patterns
- Purple / blue-purple gradient SaaS homepage
- 3-column feature grid as main visual
- Icon-in-circle marketing blocks
- Centered-everything layout
- Decorative blobs / waves / generic AI hero sections
- One giant left nav + one white content slab for every role
- 用“特殊字体”充当品牌识别的主要手段

## Implementation Notes
- 学生端优先实现风格主题切换，主题改变颜色、表面、边框、层次和装饰语气，但不改核心布局和组件结构。
- 教师端和后台端优先保证功能与可读性，视觉层不与学生端抢戏。
- AI 结果统一以 draft 呈现，设计语言上必须明显区别于“已发布内容”。

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-25 | Adopted "Daylight Workshop" design direction | Needed a system that feels educational and warm without becoming childish or generic SaaS |
| 2026-03-25 | Unified the default font system around Noto Sans SC | Avoid special decorative fonts and keep implementation stable in Codex |
| 2026-03-25 | Warm paper neutrals instead of cold enterprise white | Better matches classroom context and differentiates from generic admin dashboards |
| 2026-03-25 | Teacher console uses three-zone workbench layout | Supports classroom control, radar visibility, and AI assistance without page hopping |
| 2026-03-25 | AI copilot remains visually secondary and always draft-state | Preserves teacher trust and prevents AI from overpowering core workflows |
| 2026-03-25 | Theme switching means style families, not light/dark mode | The project needs different visual identities like Material and Natural, not simple brightness inversion |
