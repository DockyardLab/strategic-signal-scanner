# Signal Strategic Scanner 开发与测试流程复盘

这份文档整理了我们在 `Strategic Signal Scanner` 上一步步做开发、测试、修正、上云和验证的过程。

它适合你后面上课时讲：

- 一个 AI 信息扫描器是怎么从本地原型走到云端稳定运行的
- 如何一步步验证抓取、评分、报告、归档、邮件通知
- 如何发现问题并把系统收紧到可维护状态

---

## 1. 项目目标

我们的目标不是“抓很多内容”，而是：

- 定期抓取高信号信息源
- 用模型给内容打分
- 生成每天的 HTML report
- 生成可回看的 archive
- 跑完自动发邮件

最后形成一个可以长期运行的 signal scanner。

---

## 2. 第一阶段：本地原型

### 2.1 先做最小可运行版本

先把系统拆成几个最小能力：

- `rss_capture.py`：抓取内容
- `score_raw_rss.py`：给内容打分
- `build_report.py`：生成当天 report
- `build_archive.py`：生成 archive 首页
- `signal_replay.py`：本地回放和验证

### 2.2 先验证流程，不急着上云

最早的思路是：

1. 先抓一批样本
2. 再对样本评分
3. 再看 report 是否可读
4. 再看 archive 是否能浏览

这一步的重点不是规模，而是**链路跑通**。

---

## 3. 第二阶段：把输出变成 report 和 archive

### 3.1 report

我们先做每天一页的 HTML report。

验证点：

- 页面能打开
- 高分内容能排到前面
- 内容不是纯列表，而是可读的编辑部式页面

### 3.2 archive

接着做 archive 首页。

目标是：

- 能按日期看历史 report
- 能回头查以前的内容
- 不要每次运行都像一次性快照

后来又把 archive 升级成：

- 按月分组
- 近三次置顶
- 每天都可点击回看

---

## 4. 第三阶段：把本地流程搬到 Cloud Run

### 4.1 新增 Cloud Run Job 入口

为了让它能自动跑，我们加了：

- `cloudrun_job.py`
- `Dockerfile`
- 对应的云端依赖

Cloud Run Job 的职责是：

1. capture
2. score
3. build report
4. rebuild archive
5. upload artifacts
6. send email

### 4.2 为什么选 Cloud Run Job

因为这是一个典型批处理流程：

- 不是常驻服务
- 不是对外 API
- 适合定时执行
- 每次跑完就结束

---

## 5. 第四阶段：模型和权限打通

### 5.1 先解决认证

一开始我们尝试过多种方式：

- service account key
- `credentials.json`
- ADC

最后因为组织策略限制，走的是：

- `gcloud auth application-default login`

### 5.2 启用 Vertex AI

Cloud Run 上最终用的是：

- Vertex AI + Gemini

这一步确认后，模型评分链路才真正跑通。

### 5.3 了解哪些环节调用模型

后来我们把整个流程分清楚了：

- **会调用模型的环节**
  - 评分
  - relevance 判断

- **不调用模型的环节**
  - 抓取
  - 去重
  - report HTML 模板渲染
  - archive 重建
  - SMTP 邮件发送

这个分层很重要，因为它帮助我们知道 token 消耗和故障点在哪里。

---

## 6. 第五阶段：解决“重复发”和“archive 重置”问题

### 6.1 最早的问题

最早跑 Cloud Run 时，我们发现：

- 每次 report 看起来很像
- archive 里会丢历史
- 旧内容会反复出现

### 6.2 问题原因

问题主要出在两件事：

1. state 没有持久化
2. archive 只基于当前输出目录重建

### 6.3 解决方法

后来我们做了几件事：

- 把 `state.json` 持久保存到 bucket
- 启动时先把上一次 state 拉回来
- 归档时把历史 `scored_*.json` 回灌回来
- 去重从只看 URL 升级到：
  - URL
  - title hash
  - content hash

这样就解决了：

- 重复推送
- archive 丢历史
- 每次像重新开始

---

## 7. 第六阶段：调 source groups，让日报更“有东西”

### 7.1 先试小组

我们不是一开始就把所有源混在一起，而是先试几组：

- `late`
- `fast`
- `upstream`

### 7.2 观察结果

测试中发现：

- `late` 偏思想型，容易空
- `fast` 更有信号，但偏快
- `upstream` 更偏 builder / 工程实践

### 7.3 最终得到平衡版

后来我们整理出：

- `balanced`
- `balanced_plus`

其中：

- `balanced` 成为 Cloud Run 默认日报组
- `balanced_plus` 在默认基础上增加一点产品 / 创业 / builder 信号

这一步让 report 既不会太空，也不会重复太多。

---

## 8. 第七阶段：做 Cloud Storage 归档和邮件通知

### 8.1 archive 落到 bucket

我们把这些文件持续写入 GCS：

- `raw_YYYY-MM-DD.json`
- `scored_YYYY-MM-DD.json`
- `report_YYYY-MM-DD.html`
- `archive_index.html`
- `state.json`

### 8.2 邮件发送

跑完后自动发邮件，验证路径是：

- Cloud Run Job 成功结束
