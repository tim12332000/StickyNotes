# Sticky Notes

Windows 桌面便箋工具。便箋內容以 TXT 明文保存在本機，後續透過 Google Drive API 同步，不依賴 Google Drive 電腦版。

## 目前狀態

本機桌面便箋功能已完成：

- PySide6 桌面視窗
- 新增、編輯、隱藏及刪除多張便箋
- 從系統匣復原已刪除便箋
- 啟動時載入本機便箋與各裝置的視窗位置、尺寸
- 沒有便箋時自動建立一張
- 編輯停止 500 毫秒後自動儲存
- 顏色、無邊框、拖曳、縮放及置頂
- 系統匣與選用的開機自動啟動
- TXT、metadata 與本機設定均使用暫存檔及原子取代
- PyInstaller Windows 發布設定

Google Drive OAuth 與同步依目前開發範圍暫不實作。完整規格見 [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)。

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

視窗頂端按鈕可新增便箋、切換顏色、刪除或隱藏便箋。關閉視窗只會隱藏；右鍵系統匣圖示可再次顯示、復原已刪除便箋、設定開機啟動或完整結束程式。

便箋預設保存在：

```text
%LOCALAPPDATA%\StickyNotes\data\notes\
```

`metadata.json` 保存便箋顏色與修改資訊；`local-settings.json` 保存目前裝置的視窗位置及尺寸；`trash` 目錄保存可復原的便箋。這些檔案都位於同一個 `data` 目錄。

開發或測試時可用環境變數覆寫資料位置：

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

完成後可執行檔位於 `dist\StickyNotes\StickyNotes.exe`，不需要另外安裝 Python。
