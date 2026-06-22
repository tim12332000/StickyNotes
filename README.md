# Sticky Notes

Windows 桌面便箋工具。便箋內容以 TXT 明文保存在本機，後續透過 Google Drive API 同步，不依賴 Google Drive 電腦版。

## 目前狀態

專案已完成第一個可執行版本的骨架：

- PySide6 桌面視窗
- 啟動時載入本機便箋
- 沒有便箋時自動建立一張
- 編輯停止 500 毫秒後自動儲存
- 使用暫存檔與原子取代，降低寫入中斷造成的損壞風險
- 本機儲存測試

Google Drive OAuth 與同步尚未實作。完整規格見 [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)。

## 開發環境

需求：Python 3.12 以上。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## 啟動

```powershell
python -m app.main
```

便箋預設保存在：

```text
%LOCALAPPDATA%\StickyNotes\data\notes\
```

開發或測試時可用環境變數覆寫資料位置：

```powershell
$env:STICKY_NOTES_DATA_DIR = "$PWD\data"
python -m app.main
```

## 測試

```powershell
pytest
```
