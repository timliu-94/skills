# URL 写入 Obsidian

## 功能说明

当用户要求将网页、文章、公众号链接或其他公开页面保存到 Obsidian 时，执行以下流程：

1. 调用本地 Python 脚本下载 URL 对应的HTML文件
2. 调用summarize skill 生成简明摘要保存为Markdown格式
3. 通过摘要内容判断主题，放入对应Obsidian目录中
4. 将原始下载的 HTML 文件归档到附件目录作为备份
5. 返回保存路径与分类结果

## 适用场景

当用户提出以下需求时使用本 skill：

- 把这个链接保存到我的 Obsidian
- 下载这篇文章并整理成笔记
- 抓取这个 URL，生成摘要并归档
- 根据内容主题放到合适的 Obsidian 文件夹

## 前置说明

- 已准备本地抓取HTML脚本
- Obsidian 仓库路径为：`/Users/liuchen/Desktop/tanliu`
- 执行本skill之前，使用obsidian skill 获取obsidian仓库的所有目录

## 脚本调用方式

默认调用方式如下：

```bash
bash "$PWD/url-to-obsidian/scripts/download_url_article.sh" "<URL>"
```

或等价的 Python 调用方式：

```bash
python download_url_article.py --url "<URL>"
```

## 执行流程

### 1. 下载网页
调用本地脚本抓取 URL 内容。

### 2. 校验结果
若下载失败，返回真实错误信息，不得伪造内容。

### 3. 生成摘要
summarize skill 生成标题和简明摘要。

### 4. 判断主题
判断主题分类，选择。

### 5. 写入笔记
按照固定模板生成 Markdown 文件，并写入对应 Obsidian 目录。

### 6. 归档 HTML
将下载得到的 HTML 文件移动到Obsidian附件目录。

### 7. 返回结果
反馈以下信息：

- 笔记标题
- 主题分类
- Markdown 保存路径
- HTML 保存路径

## 输出要求

- 必须保留原始 URL
- 优先使用抓取结果中的 `title` 作为笔记标题
- 输出 Markdown 必须合法
- 同名文件不得覆盖，应自动追加时间戳后缀
- 主题无法判断时，必须写入默认目录，不得中断流程

## 主题分类规则

分类逻辑：

- 根据正文、标题、摘要进行分类
- 分类的目录必须是obsidian的目录，不允许自行创建
- 若无明显命中，则归入 `00-NotReady/`

## 笔记模板

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

## 摘要
<摘要内容>

<对应 HTML 的 Obsidian 内部链接>
```

## 失败处理

### 抓取失败
若本地脚本执行失败：

- 返回真实报错信息
- 不生成伪造摘要
- 提示用户检查 URL、Python 环境或脚本配置

### 主题分类失败
若无法判断主题：

- 自动写入 `00-NotReady/`
- 不中断整体流程

## 返回示例

执行成功后，返回类似结果：

```text
已保存到 Obsidian：
- 标题：<文章标题>
- 分类：<主题分类>
- Markdown：<笔记路径>
- HTML：<附件路径>
```
