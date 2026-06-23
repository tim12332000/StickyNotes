# Sticky Notes

[English](README.en.md) · 繁體中文

Windows 桌面便箋工具,風格類似 Microsoft Sticky Notes。便箋內容以 TXT 明文保存在本機,可離線使用,並可選擇透過 **Google Drive API** 在多台裝置之間同步(不依賴 Google Drive 電腦版)。

## 功能

**便箋本體**

- 無邊框、置頂的便箋視窗;拖曳標題列可移動,**四邊/四角可像一般視窗縮放**。
- 多張獨立便箋;沒有便箋時自動建立一張。
- 標題列上色(黃/粉紅/藍/綠/紫/白),**內文固定為深色底 + 白字**,卷軸也套用深色細長樣式。
- **字型可選 + 大小可調**(A− / A+ 或 Ctrl+− / Ctrl+=,範圍 8–48pt),為全域設定、即時套用到所有便箋。
- **收合**成只剩標題列、**最小化**到工作列。
- 編輯停止 500 毫秒後自動儲存;視窗位置與尺寸各自保存(屬裝置本機設定,不會被同步覆蓋)。
- 刪除會先移到回收區,可從系統匣選單復原。
- 系統匣常駐、可選開機自動啟動。
- TXT、metadata 與本機設定皆使用暫存檔 + 原子取代,異常中止不會損壞已存檔的便箋。

**雲端同步(Google Drive)**

- 手動同步:系統匣「雲端同步」或在便箋上按 **Ctrl+S**。
- 自動同步:啟動時一次 + 編輯/新增/刪除後延遲約 8 秒(僅在已授權時;不會自動跳授權)。
- 標題列指示器顯示狀態:🟠 有未同步變更 /(轉圈)同步中 / 已同步則不顯示。
- 雙向同步:單邊新增/修改會傳播,兩邊都改會**保留衝突副本**(不靜默覆蓋),刪除會互相傳播。
- 使用 `drive.file` scope(只存取本 App 建立的檔案);每張便箋是一個 `.txt`,顏色/時間存在 Drive 的 `appProperties`。

**控制台**

- 系統匣「控制台…」可變更**便箋存檔位置**,可選擇把現有便箋一併複製過去,套用後即時切換並重載。

## 標題列按鈕

由左到右:新增便箋(Ctrl+N)、變更顏色、字型、縮小字體、放大字體 … 同步指示器、刪除、收合、最小化、隱藏(Ctrl+W)。

系統匣右鍵選單:新增便箋、顯示所有便箋、雲端同步(Ctrl+S)、控制台…、復原已刪除便箋、開機時自動啟動、結束。

## 開發環境

需求:Python 3.12 以上。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev,drive]"
```

`drive` 這組額外相依(Google API 用戶端)只有在要實際連 Google Drive 時才需要;只跑本機便箋與測試的話 `pip install -e ".[dev]"` 即可。

## 啟動

```powershell
python -m app.main
```

## Google Drive 同步設定

雲端同步需要一份 Google OAuth 用戶端憑證,**不會**被提交到 Git。

1. 到 [Google Cloud Console](https://console.cloud.google.com/) 建立專案,啟用 **Google Drive API**。
2. 設定「OAuth 同意畫面」:User type 選 **External**,並把自己加入**測試使用者**(或將應用程式發布為「正式」以免白名單)。
3. 建立 **OAuth 用戶端 ID**,類型選 **桌面應用程式**,下載 JSON。
4. 將檔案命名為 `credentials.json`,放在**專案根目錄**(從原始碼執行時)或**便箋資料夾**(打包後的 exe;見下方位置)。
5. 第一次按「雲端同步 / Ctrl+S」會開啟瀏覽器完成授權,之後會在便箋資料夾產生 `token.json` 重複使用。

> 使用 `drive.file` 這類非敏感 scope,個人使用通常免 Google 驗證;未驗證時授權頁可能顯示警告,點「進階 → 前往」即可。

## 存檔位置

預設保存在:

```text
%LOCALAPPDATA%\StickyNotes\data\
```

- `notes\<note-id>.txt` — 各便箋內容
- `metadata.json` — 便箋顏色與時間
- `local-settings.json` — 全域字型設定與各便箋的視窗位置/尺寸(裝置本機)
- `trash\` — 可復原的已刪除便箋
- `sync-state.json`、`token.json` — 同步狀態與 OAuth token(若有啟用同步)

位置可由系統匣「控制台…」變更;解析優先序為:環境變數 `STICKY_NOTES_DATA_DIR` > 控制台設定 > 預設位置。開發或測試時可用環境變數覆寫:

```powershell
$env:STICKY_NOTES_DATA_DIR = "$PWD\data"
python -m app.main
```

## 測試

```powershell
pytest
```

## Windows 打包

```powershell
pyinstaller --noconfirm --clean sticky-notes.spec
```

完成後免安裝的可執行檔位於 `dist\StickyNotes\StickyNotes.exe`(需連同整個資料夾一起散布),不需另外安裝 Python。spec 已將 Google Drive 用戶端套件一併打包。
