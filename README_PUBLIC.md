# Strategic Signal Scanner

一个面向 AI / 创业 / 产品 / 研究信号的轻量扫描器。

它的目标不是“抓很多”，而是“抓少但更有信号”：

- 定期抓取高价值来源
- 用模型对内容做相关性评分
- 生成可浏览的 HTML report
- 生成长期 archive
- 支持定时运行和邮件通知

## 核心思路

这套系统把流程拆成四层：

1. **模型调用**
   - 本地原型可以直接走 Gemini API
   - 云上生产建议走 Vertex AI

2. **后端执行**
   - Cloud Run Job 负责批处理
   - 每次运行包含抓取、评分、生成报告、归档、通知

3. **存储**
   - Cloud Storage 保存 report 和 archive
   - archive 首页可以公开访问，便于浏览

4. **调度**
   - Cloud Scheduler 负责定时触发
   - 推荐周二 / 周五各跑一次

## 这套仓库里通常包含什么

- 抓取与清洗逻辑
- 内容评分逻辑
- HTML 报告生成器
- HTML archive 生成器
- Cloud Run Job 入口
- Dockerfile 和依赖文件
- 一些可视化结构图

## 典型工作流

1. 抓取 RSS / Atom / Web / YouTube 等来源
2. 过滤、去重、标准化
3. 用模型给每条内容打分
4. 生成当日报告
5. 更新 archive 索引页
6. 上传到云端存储
7. 发送摘要邮件

## 推荐的部署方式

### 本地

适合：

- 调试抓取逻辑
- 验证 prompt 和评分结果
- 做最小 smoke test

### Cloud Run Job

适合：

- 定时批处理
- 需要稳定执行和日志
- 需要把生成结果写到云端存储

### Vertex AI

适合：

- 生产环境
- IAM 权限控制
- 项目级治理
- 和 Cloud Run / Scheduler / Storage 组合

## 本地示例

```bash
python3 capture_and_score.py --group cloudrun --items-per-feed 1 --max-articles 10 --score-mode mock
```

## 公共版建议保留的文件

- `capture_and_score.py`
- `rss_capture.py`
- `score_raw_rss.py`
- `build_report.py`
- `build_archive.py`
- `cloudrun_job.py`
- `Dockerfile`
- `requirements.txt`
- `system_instruction.md`
- `README_PUBLIC.md`

## 不要公开的内容

以下内容建议保留在私有仓库或用占位符替换：

- API keys
- App Password
- Secret Manager 的真实 secret 值
- 个人邮箱地址
- Cloud Project ID
- Service Account 的真实邮箱
- GCS bucket 的真实名称
- 私有 report 链接
- 个人工作路径
- 内部调试日志
- 不想公开的样本数据

## 建议的公开写法

把敏感信息替换成占位符：

```text
YOUR_PROJECT_ID
YOUR_BUCKET_NAME
YOUR_SERVICE_ACCOUNT
YOUR_GEMINI_API_KEY
YOUR_SMTP_APP_PASSWORD
```

## 安全建议

- 密钥只放 Secret Manager
- 不把真实邮箱和 bucket 名写进公开 README
- 不把生产日志、内部注释、排障过程原样公开
- 如果要开源，先检查示例数据是否包含敏感来源

## 适合公开讲的价值

- 一套从“抓取 -> 评分 -> 报告 -> 归档 -> 通知”的完整 AI 信息流
- 适合 Cloud Run + Vertex AI + Cloud Storage 的实践参考
- 可以作为一个“高信号信息扫描器”的开源模板

## 许可证建议

如果你准备公开 GitHub 仓库，建议再补一个：

- `LICENSE`

常见可选项：

- MIT
- Apache 2.0

## 下一步

- 整理公共版目录
- 替换所有私密信息为占位符
- 保留最小可运行示例
- 再决定是否补一份更详细的部署文档
