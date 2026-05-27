# GitHub Upload Guide

这份指南说明如何把这个仓库上传成一个公开的 GitHub repo。

## 1. 先确认要上传的内容

建议只上传公开版所需文件：

- `README.md`
- `README_PUBLIC.md`
- `cloudrun_group_guide.md`
- `cloudrun_group_overview.svg`
- `cloudrun_deploy.md`
- `cloudrun_job.py`
- `capture_and_score.py`
- `rss_capture.py`
- `score_raw_rss.py`
- `build_report.py`
- `build_archive.py`
- `fetcher.py`
- `sources.py`
- `state.py`
- `mailer.py`
- `system_instruction.md`
- `youtube_to_raw.py`
- `Dockerfile`
- `requirements.txt`
- `signal_scanner_dev_test_flow.md`
- 其它你想公开的 SVG / Markdown 说明文件

不要上传：

- `artifacts/`
- `Strategy_signal_scanner_agent/`
- `Signal_scanner_v0/`
- `CloudRun_四端教程.html`
- `.venv/`
- `__pycache__/`
- 私有日志和密钥

## 2. 初始化 Git 仓库

如果本地还没有初始化：

```bash
git init
git branch -M main
```

## 3. 关联 GitHub 仓库

把下面地址换成你自己的 GitHub 仓库：

```bash
git remote add origin https://github.com/USERNAME/youtube-transcript-skill.git
```

## 4. 检查状态

```bash
git status
```

确认没有意外把私有文件加进去。

## 5. 提交

```bash
git add .
git commit -m "Prepare public open-source release"
```

## 6. 推送

```bash
git push -u origin main
```

## 7. GitHub 上再检查一次

上传后打开仓库页面，确认：

- `README.md` 是公开版
- 没有个人邮箱、私有 bucket 名、私有 project id
- 没有本地调试文件
- `RUN_GROUP=cloudrun` 的默认说明清楚

## 8. 给 Agent 的最短使用说明

如果别的 Agent 只想先跑起来，可以直接看：

```bash
python3 capture_and_score.py --group balanced --items-per-feed 1 --max-articles 8 --score-mode mock
```

如果要看 AI Native Product 相关内容：

```bash
python3 capture_and_score.py --group ai_native_product --items-per-feed 1 --max-articles 12 --score-mode mock
```

