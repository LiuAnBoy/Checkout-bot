# rayyatreats 搶購 Bot

自動搶購 [rayyatreats.com](https://www.rayyatreats.com) 每週四 12:30 開賣的巧克力商品。

## 環境需求

- Python 3.11+
- [agent-browser](https://github.com/anthropics/agent-browser) CLI（用於結帳瀏覽器自動化）

## 安裝

```bash
cd rayyatreats
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 設定 `.env`

在 `rayyatreats/` 目錄下建立 `.env`：

```env
RAYYA_EMAIL=你的帳號信箱
RAYYA_PASSWORD=你的密碼

CC_HOLDER=CHEN LU AN        # 信用卡持卡人英文姓名
CC_NUMBER=1234567890123456  # 卡號（不含空格）
CC_EXPIRY=1230              # 到期日 MMYY 格式，例如 2030/12 → 1230
CC_CVV=123
```

## 執行

```bash
source .venv/bin/activate
python3 bot.py
```

## 操作流程

1. **登入** — 自動登入，session 會快取於 `.session.json`，下次免重新登入
2. **選商品** — 互動式選單，操作方式：
   - `↑` `↓` 移動游標
   - `空白鍵` 選取 / 取消
   - `←` `→` 調整數量（1–2 件）
   - `Enter` 確認
3. **確認清單** — 顯示選購清單與預估金額，`Enter` 開始等待
4. **輪詢上架** — 每秒輪詢 collection 頁，等待商品於 12:30 上架
5. **加入購物車** — 商品上架後立即加入，並驗證購物車內容
6. **自動結帳** — 開啟瀏覽器，自動：
   - 切換至宅配
   - 選擇黑貓冷凍宅配
   - 填入信用卡資訊
   - 點擊立即結帳
7. **3D 驗證** — 跳出 3D 驗證頁面後程式關閉，**需手動完成驗證**
   - 前往 [訂單查詢](https://www.rayyatreats.com/account/orders) 點擊「前往付款」

## 注意事項

- 每筆訂單最多購買 2 件
- 每週商品 URL 會更新，bot 會自動從 collection 頁抓取最新連結
- 結帳後的 3D 驗證必須手動完成，bot 不處理
- `.env` 與 `.session.json` 已加入 `.gitignore`，不會進入版控
