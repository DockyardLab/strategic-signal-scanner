# Follow Builders Upstream 接入表

这份表的目标很简单：把 `follow-builders` 当成我们的上游前沿探测器，
用它先帮我们“扫一遍 builders 世界”，再由 `Strategic Signal Scanner`
做第二层筛选、排序和报告。

## 1) 我们为什么要借鉴它

| 视角 | follow-builders 做得好的地方 | 对我们有什么价值 |
|---|---|---|
| 信息入口 | 维护 builders 白名单，直接聚焦 AI builders、官方博客、播客 | 省掉我们自己到处找源的时间 |
| 更新方式 | 批量生成 `feed-x.json` / `feed-blogs.json` / `feed-podcasts.json` | 适合做“上游雷达”，先帮我们看一轮 |
| 内容形态 | X、博客、播客都被统一整理成可订阅 feed | 我们不用为每个平台重做一套入口 |
| 节奏 | 定期批量更新，而不是临时到处爬 | 更适合高频 builders 圈层 |
| 体验 | 用户订阅它的 feed 就能直接拿到策展后的内容 | 我们可以把它当作一个外部内容供应商 |

## 2) 我们怎么借鉴它

| 动作 | follow-builders | 我们的做法 |
|---|---|---|
| 上游来源 | 先看 builders 白名单 | 先订阅它的三份 feed，再进入我们的筛选器 |
| X / 访谈 | 直接产出 `feed-x.json` | 接进我们的 `upstream` 组，走同样的评分流程 |
| 官方博客 | 直接产出 `feed-blogs.json` | 接进我们的 `upstream` 组，保留原文链接 |
| 播客 | 直接产出 `feed-podcasts.json` | 接进 `podcasts` 体系，但保留独立组别 |
| 过滤 | 它先做批量策展 | 我们再按 Rosy 的业务判断相关性 |
| 输出 | 给用户一个 digest | 给 Rosy 一个“高信号列表 + 报告 + 溯源链接” |

## 3) 接入策略

| feed | 订阅方式 | 建议组别 | 刷新频率 | 用途 |
|---|---|---|---|---|
| `feed-x.json` | 直接读 GitHub raw JSON | `upstream` | 12 小时 | builder 侧前沿动向，尤其是 X 上的观点和动作 |
| `feed-blogs.json` | 直接读 GitHub raw JSON | `upstream` | 24 小时 | Claude / Anthropic / 官方博客的产品与工程信号 |
| `feed-podcasts.json` | 直接读 GitHub raw JSON | `upstream` 或 `podcasts` | 84 小时 | 长对谈、方法论、Agent / 产品设计 / 组织变化 |

## 4) 对我们来说，优点和风险

| 项目 | 优点 | 风险 |
|---|---|---|
| follow-builders 上游 feed | 入口干净，builder 圈层聚焦，省去我们自己找源 | 白名单偏了会带来方向性偏差 |
| 我们的 scanner | 可以按 Rosy 业务做二次筛选，只展示 3 分以上 | 维护成本更高，需要持续调源和评分 |
| 组合使用 | 上游负责“广撒网”，我们负责“精过滤” | 需要定义好重复内容和优先级，不然会重叠 |

## 5) 我们的原则

1. follow-builders 负责“帮我们看 builder 世界发生了什么”。
2. Strategic Signal Scanner 负责“这件事对 Rosy 有没有用”。
3. 只有 `relevance_score >= 3` 的内容，才进主视野。
4. 低分内容可以落盘，但不要打扰日常阅读。

