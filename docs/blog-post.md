# 我自己做了一個桌面便利貼:Sticky Notes(支援 Google Drive 雲端同步)

Windows 內建的便利貼很堪用,但有幾件事一直讓我不太順手:想換字型不行、想自己挑底色不行、跨電腦同步要綁微軟帳號……於是我乾脆自己做了一個。

這篇紀錄一下這個小工具:它能做什麼、去哪拿、怎麼用。

> 專案位置(原始碼):**https://github.com/tim12332000/StickyNotes**

## 它長什麼樣、能做什麼

一句話:**像 Windows 便利貼,但更可自訂,而且能用 Google Drive 在多台電腦之間同步。**

- 無邊框、永遠置頂的小視窗;拖曳標題列移動,**四邊/四角都能像一般視窗縮放**。
- 多張獨立便利貼,沒有便利貼時自動幫你開一張。
- **標題列可換色**(黃/粉紅/藍/綠/紫/白),內文固定深色底 + 白字,看起來清爽。
- **字型可選、字級可調**(A− / A+,或 Ctrl+− / Ctrl+=)。
- 一鍵**收合**成只剩標題列、或**最小化**到工作列。
- 編輯停 0.5 秒就**自動存檔**;視窗位置/大小會記住。
- 刪除會先進**回收區**,可從系統匣選單復原(而且**刪除前會先問你一次**)。
- 系統匣常駐,可設定**開機自動啟動**。
- **Google Drive 雲端同步**:多台電腦共用同一份便利貼。

## 怎麼開始用

### 方式一:直接用(最簡單)

下載打包好的 **`StickyNotes.exe`**(單一檔、免安裝),雙擊就能跑,不需要先裝 Python。

- 從專案的 **Releases** 頁面下載,或自己打包(見方式二)。
- 第一次啟動會自動出現一張便利貼,圖示會待在右下角系統匣。

### 方式二:從原始碼跑(開發者)

需要 Python 3.12 以上:

```powershell
git clone https://github.com/tim12332000/StickyNotes.git
cd StickyNotes
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,drive]"
python -m app.main
```

自己打包成單一 exe:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller sticky-notes-onefile.spec --distpath dist/onefile --noconfirm
```

完成後 `dist\onefile\StickyNotes.exe` 就是免安裝的單一檔。

## 操作與快捷鍵

便利貼標題列上的按鈕(由左到右):**新增**、**換色**、**字型**、**縮小字**、**放大字** … **刪除**、**收合**、**最小化**、**隱藏**。

| 動作 | 快捷鍵 |
| --- | --- |
| 新增便利貼 | Ctrl + N |
| 放大 / 縮小字體 | Ctrl + = / Ctrl + − |
| 立即雲端同步 | Ctrl + S |
| 隱藏便利貼 | Ctrl + W |

系統匣圖示按右鍵:新增、顯示全部、雲端同步、控制台、復原已刪除、開機啟動、結束。

## Google Drive 雲端同步

便利貼內容平常存在本機(純文字 TXT,離線也能用),需要時再同步到你自己的 Google Drive。

- **手動同步**:系統匣「雲端同步」或按 **Ctrl + S**。
- **自動同步**:開啟時同步一次,之後編輯完約 8 秒自動同步。
- 標題列會有低調的狀態小圖示:🟠 有未同步變更 /(轉圈)同步中 / 已同步則不顯示。
- 兩台電腦同時改同一張,會**保留衝突副本**,不會默默蓋掉。
- 只使用 `drive.file` 權限,App 只看得到自己建立的檔案,碰不到你其他雲端資料。

第一次使用要做一次 Google 授權:點同步後會開瀏覽器登入並同意,之後就記住了。若你是自己從原始碼打包,需要先到 Google Cloud Console 建立一組 OAuth 用戶端(桌面應用程式類型)、下載 `credentials.json` 放到專案根目錄;打包好的 exe 已經內建,直接用即可。

## 檔案存在哪

預設位置:`%LOCALAPPDATA%\StickyNotes\data\`,裡面有便利貼內容、顏色與設定、回收區。**存檔位置可以在系統匣「控制台」裡自由更改**(可選擇把現有便利貼一起搬過去)。

## 技術

- 語言:Python 3.12
- 介面:PySide6(Qt)
- 雲端:Google Drive API(OAuth,`drive.file`)
- 打包:PyInstaller
- 測試:pytest(約 39 個測試)

## 小提醒

- 目前只支援 Windows。
- 視窗位置/大小屬於各台電腦自己的設定,不會跨裝置同步(故意的,免得不同螢幕亂跳)。
- 單一檔 exe 首次啟動會稍慢一點點(它會先解壓到暫存資料夾)。

## 結語

這是個「搔自己癢處」的小工具,做起來剛好把桌面 App、Qt、OAuth 同步都練了一輪。原始碼都在 GitHub,歡迎拿去用或改:

👉 **https://github.com/tim12332000/StickyNotes**
