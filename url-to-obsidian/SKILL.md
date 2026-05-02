# URL 写入 Obsidian

## 功能说明

当用户要求将网页、文章、公众号链接、知乎链接、B 站视频或其他公开页面保存到 Obsidian 时，先判断 URL 类型，再调用对应下载器：

- 非知乎 URL：调用 `scripts/download_url/` 中的下载逻辑，保存原始 HTML 文件。
- 知乎 URL：调用 `scripts/download_zhihu/` 中的下载逻辑，保存 Markdown 文件。
- B 站视频 URL：调用 `scripts/download_bilibili/bili_subtitle_playwright.py` 下载官方 AI 字幕 TXT，再整理为 Markdown。

不要对各类 URL 混用下载器。知乎链接不保存为 HTML；B 站视频不走普通网页或知乎解析器；非知乎、非 B 站视频链接不走知乎 Markdown 解析器。

## 适用场景

当用户提出以下需求时使用本 skill：

- 把这个链接保存到我的 Obsidian
- 下载这篇文章并整理到 Obsidian
- 抓取这个 URL 并归档
- 保存知乎回答、知乎文章、知乎专栏或知乎视频
- 保存 B 站视频、哔哩哔哩视频或 bilibili 视频
- 下载 B 站 AI 字幕并整理到 Obsidian
- 保存公众号文章或普通网页

## 前置说明

- Obsidian 仓库路径为：`/Users/liuchen/Desktop/tanliu`
- 执行本 skill 之前，使用 obsidian skill 获取 Obsidian 仓库的所有目录
- 分类目录必须从现有 Obsidian 目录中选择，不允许自行新建主题目录
- 无法判断主题时，默认放入 `00-NotReady/`
- 附件目录使用 Obsidian 仓库中的 `attachment/` 目录；若实际目录名已有大小写或复数形式差异，以仓库现有目录为准，不自行新建平行附件目录。
- B 站字幕下载必须使用 Python：`/Users/liuchen/anaconda3/envs/coffe/bin/python`

## URL 类型判断

将以下域名视为知乎链接：

- `zhihu.com`
- `www.zhihu.com`
- `zhuanlan.zhihu.com`

将以下域名视为 B 站视频链接：

- `bilibili.com`
- `www.bilibili.com`
- `m.bilibili.com`
- `b23.tv`

判断时应解析 URL 的 `netloc`，只匹配真实域名及其子域名，避免把无关域名中的字符串误判为知乎或 B 站。匹配 B 站域名时，还应确认 URL 是视频页或短链视频入口，例如路径包含 `/video/`、BV 号、av 号，或 `b23.tv` 短链。匹配知乎域名时，调用 `download_zhihu` 保存 Markdown。匹配 B 站视频时，调用 `download_bilibili` 保存字幕 TXT。其他 URL，调用 `download_url` 保存 HTML。

## 脚本调用方式

### 非知乎 URL：保存 HTML

调用 `download_url` 下载 HTML 文件。当前脚本没有命令行参数入口时，使用导入函数的方式传入 URL：

```bash
python3 -c 'import sys; from scripts.download_url.download_url_article import save_wechat_article; print(save_wechat_article(sys.argv[1]))' "<URL>"
```

下载成功后，将生成的 `.html` 文件移动到 Obsidian 附件目录，作为原始网页归档。

### 知乎 URL：保存 Markdown

调用 `download_zhihu` 下载 Markdown 文件。当前脚本没有命令行参数入口时，使用导入解析器的方式传入 URL：

```bash
PYTHONPATH="scripts/download_zhihu" python3 -c 'import os, sys; from download_zhihu_article import ZhihuParser, read_cookies_from_file; cookies = read_cookies_from_file(os.path.join("scripts/download_zhihu", "cookies.txt")); parser = ZhihuParser(cookies); result = parser.judge_type(sys.argv[1]); print(result if str(result).endswith(".md") else str(result) + ".md")' "<URL>"
```

知乎下载依赖 `scripts/download_zhihu/cookies.txt`。如果下载失败并提示 Cookie、403、验证页或登录问题，返回真实错误信息，并提示用户更新知乎 Cookie。

### B 站视频 URL：保存 AI 字幕 TXT

调用 `download_bilibili` 下载用户给定视频 URL 的 B 站官方 AI 字幕文件。必须使用指定 Python 环境：

```bash
/Users/liuchen/anaconda3/envs/coffe/bin/python scripts/download_bilibili/bili_subtitle_playwright.py "<URL>" -o "<临时字幕目录>" --headless
```

脚本会输出字幕 TXT 文件路径。下载成功后，校验该 TXT 文件存在且非空，再进入字幕整理流程。下载失败时返回脚本真实错误，不生成伪造字幕、摘要或笔记。

## 执行流程

### 1. 判断 URL 类型

先检查 URL 域名：

- B 站视频域名：进入“B 站视频字幕流程”
- 知乎域名：进入“知乎 Markdown 流程”
- 其他域名：进入“普通 HTML 流程”

### 2. 普通 HTML 流程

1. 调用 `download_url` 下载 URL 对应 HTML。
2. 校验脚本返回的 HTML 文件路径是否存在。
3. 根据标题、URL 和可读内容判断主题分类。
4. 将 HTML 文件归档到 Obsidian 附件目录。
5. 可按需创建一条简短索引笔记，索引笔记必须包含原始 URL 和 HTML 内部链接。

### 3. 知乎 Markdown 流程

1. 调用 `download_zhihu` 下载知乎内容为 Markdown。
2. 校验脚本返回的 Markdown 文件或目录是否存在。
3. 根据标题、正文和 URL 判断主题分类。
4. 将 Markdown 文件移动到对应 Obsidian 目录。
5. 如果下载结果是知乎专栏目录，保持目录内 Markdown 与资源文件的相对路径完整，再移动到对应 Obsidian 目录。

### 4. B 站视频字幕流程

1. 调用 `scripts/download_bilibili/bili_subtitle_playwright.py` 下载用户给的视频 URL 的 AI 字幕 TXT。
2. 校验脚本返回的字幕 TXT 路径存在且内容非空。
3. 读取字幕 TXT，将逐行字幕合并为连续文本：
   - 去除字幕换行造成的断句，但保留自然段落。
   - 修复明显的语音识别、标点、重复词和语法错误。
   - 尽可能保证原文含义。
   - 不允许擅自增加原字幕中没有的信息、观点、例子或结论。
   - 不确定的内容保持原样或做最小修正，不做猜测性补写。
4. 将连续文本写入 Markdown 文件，保存到 Obsidian 附件目录 `attachment/`，作为字幕原文归档。
5. 根据连续文本的主题、标题和 URL，判断它属于 Obsidian 现有目录中的哪一个主题。
6. 对连续文本做摘要，生成主题笔记并保存到对应主题目录。主题笔记必须引用原始 URL，并链接附件目录中的连续文本 Markdown。

B 站连续文本 Markdown 模板：

```markdown
---
title: <视频标题或字幕文件名>
url: <原始链接>
source: bilibili
type: transcript
---

# <视频标题或字幕文件名>

原始 URL: <原始链接>

## 连续文本

<由字幕整理得到的连续文本>
```

B 站主题摘要笔记模板：

```markdown
---
title: <视频标题或字幕文件名>
url: <原始链接>
topic: <主题分类>
source: bilibili
tags:
  - bilibili
  - video
  - transcript
  - <主题分类>
---

## 来源

URL: <原始链接>

连续文本：<附件 Markdown 的 Obsidian 内部链接>

## 摘要

<基于连续文本总结，不添加原文没有的信息>
```

### 5. 主题分类

根据标题、正文、摘要或 URL 判断主题，选择本地 Obsidian 已有目录。无法判断时写入 `00-NotReady/`，不得中断流程。

### 6. 返回结果

执行成功后反馈：

- URL 类型：知乎 / B 站视频 / 非知乎
- 标题或文件名
- 主题分类
- Markdown 保存路径，知乎 URL、B 站摘要笔记或创建索引笔记时返回
- 连续文本附件路径，仅 B 站视频 URL 返回
- HTML 保存路径，仅非知乎 URL 返回

## 输出要求

- 必须保留原始 URL。
- 下载失败时返回真实错误，不得伪造内容或路径。
- 同名文件不得覆盖，应自动追加序号或时间戳后缀。
- Markdown 必须合法。
- 非知乎 URL 的主要归档产物是 HTML 文件。
- 知乎 URL 的主要归档产物是 Markdown 文件。
- B 站视频 URL 必须保存两个 Markdown 产物：一个是 attachment 目录中的连续文本，一个是主题目录中的摘要笔记。
- B 站连续文本只能来自字幕文件清洗，不得凭空扩写。

## 普通 HTML 索引笔记模板

生成索引笔记，使用以下模板：

```markdown
---
title: <标题>
url: <原始链接>
topic: <主题分类>
tags:
  - web
  - clipping
  - <主题分类>
---

## 原文

URL: <原始链接>

源文件归档：<对应 HTML 或 Markdown 的 Obsidian 内部链接>
```

## 失败处理

### 普通 URL 抓取失败

- 返回 `download_url` 的真实报错信息。
- 不生成伪造 HTML、摘要或索引笔记。
- 提示用户检查 URL、网络、Python 环境或脚本依赖。

### 知乎抓取失败

- 返回 `download_zhihu` 的真实报错信息。
- 如果错误与 Cookie、403、验证页或登录有关，提示用户更新 `scripts/download_zhihu/cookies.txt`。
- 不生成伪造 Markdown。

### B 站字幕抓取失败

- 返回 `bili_subtitle_playwright.py` 的真实报错信息。
- 如果错误与 Cookie、登录、无字幕、字幕按钮或 Playwright 自动化环境有关，直接说明对应原因。
- 不生成伪造字幕、连续文本、摘要或 Markdown。

### 主题分类失败

- 自动写入 `00-NotReady/`。
- 不中断整体流程。

## 返回示例

非知乎 URL：

```text
已保存到 Obsidian：
- URL 类型：非知乎
- 标题：<文章标题>
- 分类：<主题分类>
- HTML：<附件路径>
```

知乎 URL：

```text
已保存到 Obsidian：
- URL 类型：知乎
- 标题：<文章标题>
- 分类：<主题分类>
- Markdown：<笔记路径>
```

B 站视频 URL：

```text
已保存到 Obsidian：
- URL 类型：B 站视频
- 标题：<视频标题或字幕文件名>
- 分类：<主题分类>
- Markdown：<摘要笔记路径>
- 连续文本：<附件 Markdown 路径>
```
