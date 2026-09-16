# ModelRouter for Codex V5.7 Adaptive

這是一套給 Codex 的模型派工 Skill 與 Python 輔助工具。主模型維持使用者選定的設定；有必要時，依實際可用能力把明確實作交給合適的小型角色，把複雜推理與審查交給高能力角色。

**Router 配合既有開發流程運作。** 若你的 AGENTS 要求先選 Matt Pocock／Superpowers，先完成該選擇，再進入路由。不重複詢問已選定的流程，也不另外建立一份計畫或審查。沒有這種選擇規則的環境，不會被要求新增它。

## 5.7 改善了什麼

- 產品名稱與 Skill ID 縮短為 **ModelRouter**／`modelrouter`；明確呼叫改為 `$modelrouter`。
- 進階安裝器會備份舊版 `model-auto-router`，成功安裝新名稱與更新 AGENTS 受管區塊後，把舊 Skill 原子移到 `.agents/modelrouter-retired/`，避免兩套同時觸發。
- 網路上已有多個同名或近名工具；本專案在公開說明使用 **ModelRouter for Codex**，差異見 [LANDSCAPE.md](LANDSCAPE.md)。

## 5.6 成效量測

- 新增明確呼叫才建立的本機路由結果紀錄；安裝與一般路由不會建立狀態。
- 記錄任務分桶、路線、實際／請求模型、驗證層級、嘗試、修復次數，以及宿主已提供的 parent + children 合計用量。
- 使用失敗也計入的 tokens／accepted task 比較相同範圍、風險與驗證層級的路線；資料不足時明確拒絕節省結論。
- 不保存 prompt、不呼叫模型、不派工、不自動更新 profiles，也不把未知 token 當成零。

## 既有功能

- 修正 explicit xhigh 的 reasoning-gap 檢查，加入有來源的修正輪數、能力升級及 fresh context 條件。
- 明確顯示價格未知與模型 ID 同分決勝；不把規則排序說成效能或省錢證據。
- probe 改為絕對原生執行檔與可信 SHA-256，輸出需在指定私人根目錄下，預設禁止覆寫並拒絕父目錄連結。
- 安裝後可用 `python -B scripts/verify_install.py` 核對 manifest；完整測試在發布 repository，使用 `python -B scripts/run_tests.py`，零測試不通過。

- 一般問答、解釋、研究、摘要與狀態查詢不隱式啟動 Router；仍可明確要求路由。小任務由主模型直接處理，不要求每次建立模型清單、角色檔或 JSON。
- 重用原流程的任務規格、驗收與合格 reviewer，減少交接與重複審查。根據宿主實際規則處理 model／effort 覆寫和上下文繼承。
- 安裝前辨識 Windows junction／reparse point 與符號連結，涵蓋來源、目的地與已有安裝內容，避免沿連結複製或備份外部內容。
- 證據檢查從 XML parser 層拒絕 DTD，涵蓋 UTF-16；合法 UTF-16 報告仍可讀。JSON 接受 UTF-8 BOM，拒絕 NaN／Infinity。
- 清單只剩尚未建立角色檔的新模型時，分流器指出需要更新 profiles，並列出缺少的模型 ID；不會直接讓未知模型接手。
- 改成標準 Agent Skills 發布結構：可由 `npx skills` 或 `gh skill` 直接安裝，Python installer 只保留給需要 `AGENTS.md` 整合的進階情境。
- 把 portable skill 放到標準 Skill 目錄，補上人類使用的安裝、更新、移除、安全與貢獻文件，以及 GitHub Actions 驗證流程。

本版驗證範圍見 [V5.7 acceptance](validation/V5.7-SPEC.md)。舊版驗證紀錄只保留在工作副本；本版發布包附上當前驗證範圍，實際結果見 ZIP 旁的 verification JSON 與測試 log。

## 工作方式與限制

| 元件 | 實際功能 | 不代表什麼 |
|---|---|---|
| SKILL／AGENTS 片段 | 指導主模型何時分工及驗證 | 不保證每回合觸發 |
| `probe_models.py` | 唯讀查詢已安裝 CLI 的模型清單 | 不證明桌面／遠端 session 相同 |
| `route.py` | 從結構化資料提出模型與 effort 計畫 | 不呼叫模型、不派工、不保存計數 |
| `routing_metrics.py` | 明確記錄本機 bounded outcomes，彙總並比較 matched routes | 不讀 prompt、不自動量測、不證明因果或普遍節省 |
| `evidence_gate.py` | 檢查版本、雜湊、測試與審查紀錄一致性 | 不證明紀錄來源真實或不可竄改 |
| `install.py` | 備份並安裝 Skill、合併受管理 AGENTS 區塊 | 不代表啟用或真實派工已驗收 |

套件沒有背景程序、付費 benchmark 排程或硬性權限隔離。主模型仍消耗用量，多代理也可能增加總成本；節省幅度必須用相同驗收標準量測。

安裝本身不會建立 metrics state。需要量測時，依 [metrics.md](skills/modelrouter/references/metrics.md) 明確初始化私人 host scope，並只放入有來源的彙總數字；未知值保留為 null。

## 安裝

### 標準 Skill 安裝（建議）

發布到 GitHub 後，把 `OWNER/REPO` 換成實際 repository：

```sh
npx skills@latest add OWNER/REPO --skill modelrouter --agent codex --global --yes
```

或使用 GitHub CLI：

```sh
gh skill install OWNER/REPO modelrouter --agent codex --scope user
```

本機 checkout 尚未發布時：

```sh
npx skills@latest add . --from-local --skill modelrouter --agent codex --global --yes
```

這條路徑只複製 `skills/modelrouter/`，不修改全域 `AGENTS.md`。安裝後重開 Codex，再用 `$modelrouter` 做明確驗收。更新與移除：

```sh
npx skills@latest update modelrouter -g -y
npx skills@latest remove modelrouter -g -y
```

從 V5.6 或更舊版本升級時，先安裝並驗證 `modelrouter`，再移除舊 ID：`npx skills@latest remove model-auto-router -g -y`。下方進階 bridge 會自動備份與清理舊 Skill。

### Codex guidance bridge（進階）

本機腳本需要 Python 3.10 以上，僅使用標準函式庫。Windows 可使用 `py -3`。

如果你需要把 Router 指示合併到生效的全域或專案 `AGENTS.md`，才使用 repository-level wrapper。Wrapper 預設只做 dry-run；確定目標後才加上 apply：

```powershell
.\install.ps1 -DryRun
.\install.ps1 -Apply
```

macOS／Linux：

```sh
./install.sh --dry-run
./install.sh --apply
```

也可以直接呼叫跨平台 Python installer。完整參數、專案範圍安裝與回復方式見英文 [INSTALL.md](INSTALL.md) 與 [README.md](README.md)。

在解壓後的 `modelrouter` 目錄執行：

```sh
python scripts/install.py --scope user --dry-run
python scripts/install.py --scope user --apply
```

僅限單一專案：

```sh
python scripts/install.py --scope project --project "專案完整路徑" --dry-run
python scripts/install.py --scope project --project "專案完整路徑" --apply
```

`--dry-run` 顯示目標與警告，不寫入檔案。個人 Skill 位置是 `$HOME/.agents/skills/modelrouter/`；AGENTS 位置依 `CODEX_HOME`，預設為 `$HOME/.codex`。有非空白 `AGENTS.override.md` 時合併到該生效檔，保留其他指示；舊內容備份到 Codex home 的 `modelrouter-backups/`。進階安裝器會遷移舊版 `$HOME/.agents/skills/model-auto-router/` 與受管 marker；專案範圍則使用專案內的對應位置。

安裝不改 `config.toml`、主模型、帳號、方案或權限。重複安裝替換已標記的 Router 區塊，未標記舊規則會保留並警告。檢查重複同名 Skill、覆寫與自訂 agent 設定；不要把未處理的衝突當成啟用成功。若路徑含 junction／reparse point／symlink，工具會在寫入前拒絕，需先檢查路徑用途。

`INSTALL-IN-CODEX.txt` 提供使用者可自行採用的進階安裝請求範例；檔案本身不授權代理安裝。安裝後開新的工作階段，再驗收實際行為。

## 第一次驗收

可在新 session 輸入：

```text
$modelrouter 檢查目前的啟用與派工能力。
先使用目前宿主已提供的能力資訊，分開列出已觀察和未知的事項。
這次不要修改專案、安裝其他工具或啟動付費校準。
```

若宿主已提供足夠資料，不另啟動 CLI。需要查詢已安裝的 CLI 且執行已獲授權時：

```sh
python skills/modelrouter/scripts/probe_models.py --codex "/可信路徑/codex" --codex-sha256 "可信安裝的SHA256" --output-root "/既有私人目錄" --output "/既有私人目錄/catalog.json" --timeout 15
```

查詢只送 initialize／initialized 與分頁 model/list，不啟動模型 turn，也不登入或修改設定。CLI 啟動仍可能使用已有認證與網路。輸出固定先標示 `session_bound=false`；核對實際帳號、客戶端與宿主後，才能作為對應工作階段資料。

## 模型與 effort

模型 ID 不寫死。取得宿主可用清單後，依精確 ID 的官方能力描述或獨立實測建立 worker／generalist／reasoner／frontier 角色資料，保留來源與日期。未知模型保持 provisional，不能直接擔任重要架構或最終 reviewer。

初始角色判斷由主模型完成；腳本不會自己閱讀官方文件或理解自然語言。清單最長快取 24 小時，角色來源最長 30 天重新審視；宿主、模型、effort 或能力錯誤會觸發相關刷新。詳見 [registry.md](skills/modelrouter/references/registry.md)。

依任務選原生 effort，支援才請求覆寫。若宿主要求繼承，照實繼承；不能把提示中的設定冒稱為有效設定。記錄 proposed／requested／observed，未知 observed 值用 null。Fresh context 與唯讀權限也須按實際介面確認。

## 預算與驗證

若使用者、宿主及既有流程未另定有效限制，路由工作採用下列程序預設：同時兩個子代理、深度一、一輪初審／集中修正／針對性複查、一次自主能力升級，以及所有代理共用的一次 Max／Ultra 階段。這些是程序預設，並非宿主強制限制。V5.4 的 `route.py` 會檢查 Max／Ultra 的 ledger 身分與計數，也會依提供的 `lifecycle` 檢查修正輪數上限、能力升級門檻及 fresh context 條件。有效額度必須附上既有流程來源；未提供時明示未檢查。協調者仍負責維護跨重試計數、保護資料、核對派工與宿主限制；JSON 本身不是授權或硬性隔離。

與既有流程或使用者預算不同時，先釐清適用值，不默默新增、重置或弱化限制。必要驗證不能為了配合預算而跳過；到達適用上限仍未完成時，要明確報告剩餘工作。

實作者不能批准自己的改動；符合條件的既有 reviewer 可以沿用。Reviewer 修改的部分需由另一位獨立評閱者看過。一般回答與低影響文件修改採比例驗證，不要求完整證據套件。

完整實機清單在 [live-acceptance.zh-TW.md](tests/live-acceptance.zh-TW.md)。本機測試、獨立代理審查、CLI 模型清單查詢與正式部署驗收是不同證據，不能互相代替。
