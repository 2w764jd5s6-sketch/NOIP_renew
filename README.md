# No-IP 自动续期

通过 GitHub Actions 定期自动续期 No-IP 免费域名。

## 设置步骤

1. 在仓库的 **Settings → Secrets and variables → Actions** 中添加以下 Secrets：
   - `NOIP_USERNAME`：No-IP 登录邮箱
   - `NOIP_PASSWORD`：No-IP 登录密码
   - `NOIP_TOTP_SECRET`：两步验证密钥（如果没有 TOTP，可留空，但需要修改脚本跳过 OTP）

2. 每周一 9:00 UTC 自动运行，也可手动触发 Actions。

3. 运行日志和截图可在 Actions 的 Artifacts 中下载。

## 本地调试

```bash
pip install -r requirements.txt
python noip-renew.py -u "user" -p "pass" -s "secret" -d

---

## 🚀 部署步骤

1. **在 GitHub 创建新仓库**（或使用现有仓库）。
2. **将上述所有文件**按目录结构添加到仓库中。
3. **添加 Secrets**（如 README 所述）。
4. **推送代码**到 GitHub，Actions 会自动运行（或手动触发）。

---

## ⚠️ 注意事项

- 脚本使用 `webdriver_manager` 自动下载 ChromeDriver，无需手动配置。
- 由于启用了无头模式，浏览器不会显示界面，适合服务器环境。
- 如登录遇到验证码，脚本会尝试自动点击登录按钮；若失败，可能需增加验证码识别功能（当前未集成）。
- 每周运行一次足够满足 30 天续期要求，也可根据需求调整 `cron` 表达式。

---

现在，您可以直接将以上所有文件提交到您的 GitHub 仓库，即可实现全自动续期。如果遇到问题，可在 Actions 日志中查看详细输出。祝使用顺利！ 🎉