# Strategic Signal Scanner

一个面向 AI、创业、产品、研究和高信号思想层内容的轻量扫描器。

它的目标不是“抓很多”，而是“抓少但更有信号”：

- 定期抓取高价值来源
- 用模型对内容做相关性评分
- 生成可浏览的 HTML report
- 生成长期 archive
- 支持定时运行和邮件通知

## 这套仓库做什么

这套系统把流程拆成五层：

1. **抓取**
   - RSS / Atom / Web / YouTube 等来源
   - 支持去重和刷新窗口

2. **评分**
   - 通过 Gemini 对内容做相关性打分
   - 过滤噪声，留下真正值得看的信号

3. **报告**
   - 生成当日报告 HTML
   - 高信号内容会被高亮

4. **归档**
   - 生成可浏览的 archive index
   - 按月 / 按日回看历史结果

5. **通知**
   - 可选 SMTP 邮件通知
   - 方便每天自动收结果

## 适合谁用

- 想搭一个 AI 信息流的人
- 想做周报 / 日报 / 领域监控的人
- 想用 Cloud Run + Vertex AI 跑定时批处理的人
- 想把“抓取 -> 评分 -> 报告 -> 归档”做成可复用模板的 Agent

## 推荐的默认组

- `cloudrun`：Cloud Run 默认组，当前映射到 `balanced`
- `balanced`：稳定日读版
- `balanced_plus`：比 `balanced` 更丰富一点
- `ai_native_product`：Anthropic / Claude / Lenny / AI-native product 重点组

如果你只是第一次跑，建议从：

```bash
python3 capture_and_score.py --group balanced --items-per-feed 1 --max-articles 10 --score-mode mock
```

开始。

## 各组大概是什么

### `balanced`
稳定、均衡、适合每天看。

- Google DeepMind Blog
- Google AI Blog
- NVIDIA Blog
- a16z Enterprise x AI
- Sequoia Capital
- Stratechery
- Follow Builders X Feed
- Follow Builders Podcasts Feed
- Simon Willison
- Dwarkesh Patel
- Geoffrey Litt
- Sean Goedecke

### `balanced_plus`
在 `balanced` 上再加一点创业、产品、社区和播客信号。

- Hacker News
- YC Blog
- AI Builders
- Lex Fridman Podcast
- Lenny's Podcast
- Cat Wu
- Lulu Cheng Meservey

### `ai_native_product`
更聚焦 AI Native Product，尤其适合看：

- Anthropic / Claude 的官方更新
- Anthropic 核心人物
- Lenny 体系里的 AI-native 产品、工程和生产经验
- 可以迁移到工作流里的具体应用案例

主要包括：

- Anthropic News
- Anthropic Research
- Anthropic Engineering
- Claude Blog
- Amanda Askell
- Cat Wu
- Anthropic AI
- Dario Amodei
- Lenny's Podcast
- Lex Fridman Podcast
- Lenny's Newsletter

## Agent 快速使用

如果你是别的 Agent，建议按这个顺序使用：

### 1. 抓取并评分

```bash
python3 capture_and_score.py --group balanced --items-per-feed 1 --max-articles 10 --score-mode mock
```

或者：

```bash
python3 capture_and_score.py --group ai_native_product --items-per-feed 1 --max-articles 12 --score-mode mock
```

### 2. 只抓取，不评分

```bash
python3 rss_capture.py --group balanced --items-per-feed 1 --max-articles 8
```

### 3. 给已有 raw 文件评分

```bash
python3 score_raw_rss.py artifacts/rss/raw_YYYY-MM-DD.json --mode mock
```

### 4. 生成 HTML 报告

```bash
python3 build_report.py --scored-file artifacts/rss/scored_YYYY-MM-DD.json
```

### 5. 生成 archive

```bash
python3 build_archive.py --artifact-dir artifacts/rss --output artifacts/rss/archive_index.html
```

## Cloud Run 运行方式

Cloud Run Job 读取环境变量 `RUN_GROUP` 来决定跑哪一组源。

推荐默认值：

```bash
RUN_GROUP=cloudrun
SCORE_MODE=gemini
GEMINI_MODEL=gemini-3.1-flash-lite-preview
ITEMS_PER_FEED=1
MAX_ARTICLES=30
MAX_AGE_DAYS=180
REPORT_MAX_AGE_DAYS=180
OUTPUT_DIR=/tmp/artifacts/rss
ARCHIVE_BUCKET=your-bucket-name   # optional, for GCS upload
ARCHIVE_PREFIX=signal-archive     # optional, defaults to signal-archive
```

`cloudrun` 现在实际映射到 `balanced`，所以它适合作为公开仓库里的默认日报组。

如果你想更丰富一点，改成：

```bash
RUN_GROUP=balanced_plus
```

如果你想看 AI Native Product 重点组，改成：

```bash
RUN_GROUP=ai_native_product
```

## 本地 smoke test

```bash
SCORE_MODE=mock RUN_GROUP=cloudrun ITEMS_PER_FEED=1 MAX_ARTICLES=5 OUTPUT_DIR=/tmp/strategy-agent-cloudrun python3 cloudrun_job.py
```

## 部署思路

这套仓库适合部署成 **Cloud Run Job**：

1. 定时抓取
2. 用 Gemini 评分
3. 生成 report
4. 重建 archive
5. 上传到 Cloud Storage
6. 可选发送邮件

如果你要把它部署到自己的 GCP 项目，请把下面这些内容替换成你自己的值：

- `YOUR_PROJECT_ID`
- `YOUR_BUCKET_NAME`
- `YOUR_SERVICE_ACCOUNT`
- `YOUR_SMTP_PASSWORD`
- `YOUR_GEMINI_SECRET`

## 不要提交的内容

公共仓库里不要提交：

- API keys
- App Password
- Secret Manager 的真实 secret 值
- 个人邮箱地址
- 真实 Cloud Project ID
- 真实 Bucket 名称
- 真实 Service Account 邮箱
- 私有调试日志
- 私有样本数据

## 许可证建议

如果你准备公开发布，建议补一个：

- `LICENSE`

常见选择：

- MIT
- Apache 2.0

## 目录里最有用的文件

- `capture_and_score.py`
- `rss_capture.py`
- `score_raw_rss.py`
- `build_report.py`
- `build_archive.py`
- `cloudrun_job.py`
- `sources.py`
- `system_instruction.md`
- `Dockerfile`
- `requirements.txt`
- `cloudrun_group_guide.md`

## 这套仓库最适合讲的故事

- 一套从“抓取 -> 评分 -> 报告 -> 归档 -> 通知”的完整信息流
- 一个适合 Cloud Run + Vertex AI + Cloud Storage 的开源模板
- 一个可 fork、可替换 source group、可改成你自己领域的信号扫描器
