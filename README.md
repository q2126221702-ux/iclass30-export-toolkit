# C30 / iClass30 测验与作业导出工具

从 [C30 教育云平台](https://www.iclass30.com/)（iClass30）**已批阅、可查看答案**的作业/测验详情页，导出题目与答案为 Markdown / JSON。

本工具包为脱敏后的可分发版本：**不含**个人账号、课程名、导出结果或浏览器登录数据。

---

## 适用场景

- 你在 **px 学习平台** 里，通过 **学习空间 → 课程 → 作业考试** 打开已完成的测验/作业
- 详情页上能看到 **题干、选项、正确答案、你的作答**
- 需要将内容保存到本地复习（`output/` 目录）

**不适用：**

- 独立「智能作业」页（`homework-h5.iclass30.com`）若与课程内作业不同步，请优先走课程入口
- 未公布答案或未提交的试卷
- 绕过平台权限批量爬取他人数据

---

## 环境要求

- Windows 10/11（批处理与按键检测面向 Windows）
- Python 3.10+
- 可访问 `sso.iclass30.com`、`px.iclass30.com`

---

## 安装

```bash
cd iclass30-export-toolkit
pip install -r requirements.txt
playwright install chromium
```

---

## 快速开始（推荐）

1. 双击 **`run_export.bat`**
2. 若未登录，在浏览器中完成 SSO 登录
3. 手动导航：

   ```
   右上角头像 → 学习空间 → [你的课程] → 作业考试 → 测验（或作业）
   ```

4. **点进某一份详情页**（页面上要能看到题目和「正确答案」）
5. 点击左上角浮动面板中的绿色按钮 **「导出当前页」**
6. 导出成功后，左下角会提示「已导出: …」
7. 在 `output/` 查看 `.md` / `.json` 文件
8. 全部完成后，回到命令行窗口按 **Enter** 关闭

---

## 其他入口

| 文件 | 说明 |
|------|------|
| `run_export.bat` | **主流程**：打开浏览器 + 监听 API + 页面导出 |
| `run_login.bat` | 仅打开 SSO 登录页 |
| `run_portal.bat` | 打开 px 学习平台首页 |
| `scan_cache.bat` | 从浏览器缓存扫描已加载过的 `quesList` 并导出（离线补救） |

命令行等价：

```bash
python manual_export.py      # 主流程
python open_login.py         # 登录
python open_portal.py        # 打开平台
python export_all_cache.py   # 扫描缓存
```

---

## 正确入口说明

经实测，学生端作业/测验通常在 **课程内**，而不是单独的「智能作业」列表：

| 步骤 | 操作 |
|------|------|
| 1 | 登录 https://sso.iclass30.com/login |
| 2 | 进入 https://px.iclass30.com/portalC30/home |
| 3 | 右上角 **头像 → 学习空间** |
| 4 | 进入 **你的课程** |
| 5 | **作业考试 → 测验 / 作业** |
| 6 | 打开 **已批阅、可见答案** 的详情页 |

详情页 URL 通常包含 `previewHomework` 或类似路径。

---

## 导出原理

工具同时使用多种方式抓取数据（按优先级）：

1. **API 监听**：拦截含 `quesList` 的 JSON 响应（最完整）
2. **页面全文解析**：从可见文本解析 `1.[单选题]…正确答案：X`（适配测验页 DOM 结构）
3. **Vue / 内存状态**：尝试从页面 JS 状态读取
4. **缓存扫描**：从 Chromium 缓存文件中读取曾加载过的 JSON
5. **API 补请求**：根据 URL 中的 ID 尝试常见接口（需有效登录态）

---

## 目录结构

```
iclass30-export-toolkit/
├── manual_export.py      # 主程序：手动导航 + 自动导出
├── page_extract.py       # 页面/API 数据提取逻辑
├── export_homework.py    # 题目格式化（API → Markdown 字段）
├── export_all_cache.py   # 缓存扫描导出
├── browser_util.py       # 浏览器会话与启动
├── open_login.py         # 打开登录页
├── open_portal.py        # 打开学习平台
├── run_export.bat        # Windows 一键运行（推荐）
├── run_login.bat
├── run_portal.bat
├── scan_cache.bat
├── requirements.txt
├── output/               # 导出结果（运行时生成）
└── .browser_session/     # 登录会话（运行时生成，勿分享）
```

---

## 输出格式

每份测验/作业生成两个文件：

- `{标题}_{时间戳}.md` — 便于阅读
- `{标题}_{时间戳}.json` — 便于程序处理

Markdown 每题包含：题干、选项、正确答案、你的作答。

汇总清单：`output/manual_exports.json`

---

## 常见问题

### 点了「导出当前页」没反应

- 确认已在 **详情页**（不是列表页）
- 先应出现「收到点击，正在导出…」；若没有，关闭浏览器后重新运行 `run_export.bat`
- 刷新详情页（F5）后再点绿色按钮
- 查看 `output/export_debug.json`（导出失败时自动生成）

### 只导出了一份，其他的没有

- 每份都要 **单独点进详情页** 并触发导出
- 或每打开一份后点绿色按钮

### 浏览器空白

- 关闭所有由本工具打开的 Chrome 窗口
- 删除 `.browser_session` 后重新登录（会丢失登录态）

### 同时开了多个脚本

- 只保留 **一个** `manual_export.py` 实例，否则会话冲突

---

## 隐私与安全

- 登录 Cookie 保存在本地 `.browser_session/`，**不要**上传或分享该目录
- 导出文件可能含你的作答，请自行保管
- 本工具仅在本地运行，不向第三方发送数据
- 会话与缓存使用独立目录 `%TEMP%\\iclass30_export_toolkit_session`，不与旧版脚本共用

### 分享/上传本文件夹前请确认

打包或上传 `iclass30-export-toolkit` 前，请确认**未包含**以下运行时生成的内容：

| 路径 | 可能含隐私 |
|------|-----------|
| `output/` | 导出的题目、你的作答、测验名称 |
| `.browser_session/` | 登录 Cookie、浏览缓存 |
| `__pycache__/` | 一般无隐私，可删 |

本工具包源码本身**不应**包含姓名、学号、课程名或账号信息。若你曾在本目录运行过脚本，请先删除上述文件夹再分享。

---

## 许可与声明

仅供个人学习、复习已在平台上合法可见的内容。请遵守学校与平台使用规定。
