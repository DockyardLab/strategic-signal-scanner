# Cloud Run 日报组切换说明

这套 Strategic Signal Scanner 现在不是只有一个固定日报，而是可以通过 `RUN_GROUP` 切换不同的信息源组合。

## 怎么切换

Cloud Run Job 读取环境变量 `RUN_GROUP` 来决定跑哪一组源。

### 运行时默认值

- `cloudrun`：Cloud Run 默认组
- 代码里 `cloudrun` 目前映射到 `balanced`

### 本地运行示例

```bash
RUN_GROUP=balanced python3 cloudrun_job.py
RUN_GROUP=balanced_plus python3 cloudrun_job.py
RUN_GROUP=ai_native_product python3 cloudrun_job.py
```

### Cloud Run Job 更新示例

如果你要把线上 Job 的日报组切掉，可以直接更新环境变量：

```bash
gcloud run jobs update strategic-signal-scanner \
  --region asia-east1 \
  --set-env-vars RUN_GROUP=ai_native_product
```

切回默认组：

```bash
gcloud run jobs update strategic-signal-scanner \
  --region asia-east1 \
  --set-env-vars RUN_GROUP=cloudrun
```

因为 `cloudrun` 现在映射到 `balanced`，所以这条命令本质上就是切回更稳的默认日报。

## 当前有哪些日报组

| 组名 | 用途 | 大致内容 |
| --- | --- | --- |
| `cloudrun` | 线上默认日报 | 当前等同 `balanced`，适合定时推送 |
| `balanced` | 稳定日读版 | AI / infra / upstream / late 的平衡组合 |
| `balanced_plus` | 稍宽一点的日读版 | 在 `balanced` 基础上加一点 Hacker News、YC、AI Builders、播客和创始人信号 |
| `ai_native_product` | AI Native Product 重点组 | Anthropic / Claude / Lenny / AI 原生产品构建与应用 |
| `fast` | 快速高信号组 | Google / NVIDIA / a16z / Sequoia / HN 等高频源 |
| `upstream` | Follow Builders 上游组 | X / blog / podcast 的 upstream detector 输出 |
| `front` | 置顶组 | 用户最想先看的官方 / 人物源 |
| `youtube_front` | 置顶 YouTube 组 | 订阅的 YouTube 频道 |
| `podcasts_rss` | RSS 播客组 | 原生播客 RSS 源 |
| `podcasts_web` | 网页播客组 | 更适合网页抓取的播客 / 访谈页 |
| `slow` | 慢研究组 | 更慢但更厚的研究型源 |
| `late` | 思想领袖组 | 个人博客 / 观点 / 长文 / X 账号 |
| `all` | 全量组 | 所有源的合集，不建议作为常规日报 |

## 每组大概放了什么

### `cloudrun` / `balanced`
适合每天看一版，不要太吵，也不要太薄。

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
在 `balanced` 上多一点产品、创业和社区信号。

- Hacker News
- YC Blog
- AI Builders
- Lex Fridman Podcast
- Lenny's Podcast
- Cat Wu
- Lulu Cheng Meservey

### `ai_native_product`
这组是你现在最关心的“AI Native Product”主题组，重点看：

- Anthropic / Claude 的官方与人物输出
- Lenny 体系里的 AI-native 产品、工程、生产实践
- 能迁移到你们工作流里的具体案例

大致包括：

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

### `fast`
更像“快速扫一眼产业风向”。

- Google DeepMind / Google AI / NVIDIA
- a16z / Sequoia / YC
- HN / Stratechery

### `upstream`
Follow Builders 的上游 detector 输出。

- X feed
- Blog feed
- Podcast feed

### `front` / `youtube_front`
你最想先看到的人和官方频道。

- Paul Graham
- Google Labs
- Claude
- Amanda Askell
- Anthropic 相关官方源
- Andrej Karpathy
- Sequoia / Google DeepMind / Y Combinator / Claude YouTube

### `podcasts_rss` / `podcasts_web`
播客和长访谈组。

- Latent Space
- No Priors
- Lex Fridman Podcast
- Lenny's Podcast
- Training Data

### `slow`
更偏研究 / 长周期 / 厚内容。

- McKinsey
- AWS Machine Learning
- AI2 / MIRI / fast.ai / Berkeley AI Research
- Every / The Atlantic Tech / Lightspeed

### `late`
更偏个人观点、长文和作者型信号。

- Simon Willison
- Dwarkesh Patel
- Geoffrey Litt
- Mitchell Hashimoto
- Sean Goedecke
- Cat Wu
- Lulu Cheng Meservey

## 建议怎么用

- 日常自动日报：`cloudrun`
- 想更丰富一点：`balanced_plus`
- 想专门看 AI Native Product / Anthropic / Claude / Lenny：`ai_native_product`
- 想做快速市场扫描：`fast`
- 想做上游 detector 复盘：`upstream`

