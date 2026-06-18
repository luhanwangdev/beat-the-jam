# CLAUDE.md

國道車速查詢服務:使用者輸入起點/終點(走廊交流道)+ 時間窗,回傳該路段逐時段(bin)的小客車平均車速曲線,用來判斷「幾點出發進雪隧最不塞」。

## 資料來源(重要)

- **只用**高公局 TDCS M05A 公開歸檔,**不要用 TDX API**(僅即時快照、需 OAuth2、易 429,撈不到久遠歷史)。
- URL:`https://tisvcloud.freeway.gov.tw/history/TDCS/M05A/M05A_<YYYYMMDD>.tar.gz`(免認證)。
- 回溯下限 `2021-06-22` → 今天。每日檔解壓為 `YYYYMMDD/HH/TDCS_M05A_..._HHMMSS.csv`,288 檔/日(每 5 分鐘)。
- CSV 無表頭,6 欄:`時間, 起點門架, 迄點門架, 車種, 中位數車速(km/h), 流量`;時間格式 `YYYY/MM/DD HH:MM`。
- 車種固定小客車 `31`。車速 `0`/空 = 偵測器離線 = 缺值(**不可當塞到 0**)。
- 走廊門架對照:政府開放資料「國道計費門架座標及里程牌價表」(data.gov.tw dataset 21165)。

## 架構

走廊優先:寫死一條回家路線(國1 北向 → 國3 → 國5 南向 → 頭城)。方向與車種由系統推導,非使用者輸入。端點:`GET /speed`(逐 bin 瞬時車速曲線,named stops 輸入)、`GET /journey`(出發時間→實際行車時間曲線,gantry id 輸入,時間相依模擬,跨日多抓 2h 緩衝)、`GET /gantries`(列出走廊 11 個有序門架點,純資料、無下載/驗證,供呼叫者得知 `/journey` 可填的 origin/destination)。**不做快取**(每次即時下載當日檔)。

模組(扁平於 `src/`,無 `traffic_speed/` 子資料夾;模組間用扁平 import 如 `from corridor import ...`):
- `corridor.py` — `Segment`、`GantryPoint`、`CORRIDOR`、`STOPS`、`resolve_segments()`(named stops)、`resolve_segments_by_gantry()`(gantry id)、`corridor_gantries()`(有序門架點清單)(純資料)
- `parser.py` — `parse_row()` → `Record`(篩小客車+走廊門架)
- `archive.py` — `fetch_day_records()`(下載+解壓 tar.gz,無快取)
- `aggregate.py` — `compute_bins()`(跨午夜接續、bin 取中位數、缺值處理)、`summarize()`
- `journey.py` — `index_speeds()`、`speed_at()`、`compute_journey_times()`(時間相依行車模擬,離線沿用上一段車速)、`summarize_journeys()`
- `main.py` — FastAPI 路由、input 驗證、組 response

## 開發慣例

- **uv** 管理依賴與環境(`uv add`、`uv run pytest`、`uv run uvicorn main:app --app-dir src --reload`)。Python ≥ 3.12。專案為 uv application(`[tool.uv] package=false`、`[tool.pytest.ini_options] pythonpath=["src"]`),非可安裝套件。
- **TDD**:先寫失敗測試再實作。
- **git commit message 一律英文。**
- **`docs/superpowers/` 下的設計/計畫文件不進版控**,只 commit 程式碼。
- 設計與實作計畫:`docs/superpowers/specs/` 與 `docs/superpowers/plans/`(僅本機參考)。

## 輸入 / 輸出

- 輸入:`origin`、`destination`(走廊交流道)、`start`、`end`(可跨午夜)、`bin_minutes`(預設 30)。
- 驗證:日期需在 2021-06-22~今天;`end>start` 且跨度 ≤ 24h;起終點需在走廊且順序正確;否則 400。上游下載失敗 503。
- 輸出:JSON,`bins[]`(每 bin `avg_speed_kmh`/`sample_count`/`status`)+ `summary`(整體平均、最慢時段)。
