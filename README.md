# Netflix Auto-Verifier

自動驗證 Netflix 暫時存取碼的工具。透過 Gmail IMAP 監控收件匣，收到 Netflix 驗證信時自動點擊驗證連結。

## 功能

- 📧 每 30 秒檢查 Gmail 收件匣
- 🔗 自動點擊 Netflix 驗證連結
- 📝 記錄已處理的郵件，避免重複驗證
- 🕐 使用台灣時間 (UTC+8) 記錄 log

## 安裝

1. 確保有 Python 3.6+
2. Clone 這個 repo：
   ```bash
   git clone https://github.com/Lycosidai/netflix-auto-verifier.git
   cd netflix-auto-verifier
   ```

3. 設定 Gmail App Password：
   - 到 [Google 帳戶設定](https://myaccount.google.com/apppasswords) 產生應用程式密碼
   - 建立 `imap_config.json`：
     ```json
     {
       "email": "your-email@gmail.com",
       "app_password": "your-16-char-app-password"
     }
     ```

## 使用方式

### 單次檢查
```bash
python3 netflix_auto_verify.py
```

### 背景執行 (每 30 秒自動檢查)
```bash
nohup python3 netflix_daemon.py &
```

### 查看 Log
```bash
tail -f daemon.log
```

### 停止 Daemon
```bash
pkill -f netflix_daemon.py
```

## 檔案說明

| 檔案 | 說明 |
|------|------|
| `netflix_auto_verify.py` | 單次執行腳本 |
| `netflix_daemon.py` | 背景常駐程式 |
| `imap_config.json` | Gmail 設定 (需自行建立) |
| `processed_emails.json` | 已處理郵件記錄 (自動產生) |
| `daemon.log` | 執行記錄 (自動產生) |

## 注意事項

- 需要開啟 Gmail 的兩步驟驗證才能產生 App Password
- 驗證連結會被「訪問」，但不會真正登入 Netflix（需要有登入狀態才能完成驗證）
- 建議配合已登入 Netflix 的環境使用

## License

MIT
