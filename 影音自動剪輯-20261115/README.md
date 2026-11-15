# 🎬 影音自動剪輯懶人包 (Auto Video Editor v2.0)

> **專為教師與講師螢幕教學錄影設計的智慧型自動剪輯工作流**  
> 整合「AI 語音活動辨識 ＋ 物理聲學邊界對齊 ＋ 紅框視覺標註偵測 ＋ 單詞級字幕自動重算 ＋ FFmpeg 單管線幀級硬字幕合成」。

---

## 📖 目錄
1. [系統核心原理](#一核心剪輯原理)
2. [使用工具與環境需求](#二使用工具與環境需求)
3. [依賴套件程式清單](#三依賴套件程式清單)
4. [核心腳本架構與功能說明](#四核心腳本架構與功能說明)
5. [搭配技能與 SOP 規範](#五搭配技能與-sop-規範)
6. [快速上手指南 (Quick Start)](#六快速上手指南-quick-start)
7. [常見問題與最佳實踐](#七常見問題與最佳實踐)

---

## 一、核心剪輯原理

本系統擺脫傳統僅憑單純音量閥門粗暴切音的剪輯方式，深度結合 **聲學（Acoustics）**、**語意（Semantics）** 與 **電腦視覺（Computer Vision）** 三大維度：

### 1. 物理聲學邊界校正 (Acoustic Burst Alignment, -30dB)
* **痛點**：Whisper 等 ASR 模型在轉寫時，因上下文語意補齊機制，常將單詞的時間戳延伸跨過數秒的長停頓，導致傳統直接切字時會切進長靜音。
* **解法**：系統於前置階段透過 FFmpeg `silencedetect` 以 `-30dB`、`d=0.25s` 進行物理聲壓掃描，將真正的發音起訖點鎖定在 `acoustic_bursts`，並自動將 Whisper 的時間戳校正限制在真實聲學爆發範圍內。

### 2. 紅框視覺標註像素分析 (Red Annotation Detection, R-G > 100)
* **痛點**：講師在教學時經常使用 ZoomIt 或螢幕畫筆圈畫重點，但在多 Take 或反覆重錄時，僅靠聲音很難判斷講師最終採用了哪一個版本。
* **解法**：`sample_frames.py` 分析關鍵影格的 RGB 色彩通道，當滿足 `(R > 180) & (R - G > 100) & (R - B > 100)` 且像素數超過閾值（200px）時，自動標記為正式紅框標註 Take，並計算邊界座標 `bbox`。

### 3. 標註即點選 ＋ 句中畫框無縫跳接 (Annotation Equals Click & Mid-Sentence Jump Cut)
* **法則一（標註即點選）**：講師圈出「按鈕」並講完語音指引（例如「點選設定」）的瞬間，代表點選已完成，系統直接瞬切（Jump Cut）至下一個畫面，切除游標移動、點擊遲疑與網頁載入旋轉等待。
* **法則二（句中畫框去空白）**：講師講前半句、停頓數秒畫紅框、再講後半句時，系統精準識別 350ms 以上的句中停頓並自動移除無聲等待，讓成品呈現「前半句講完 ➔ 紅框瞬間俐落跳出 ➔ 緊接後半句開口」的明快效果。

### 4. 0.2 ~ 0.3s 極速自然呼吸間隔 (Pacing Control)
* 將段落與段落之間的間隔嚴格控制在 **0.2 ~ 0.3 秒**。杜絕切字吃音，同時保持緊湊洗鍊的現代教學觀影節奏。

### 5. 單詞級時間戳跨片段拆分重對齊 (Word-Level Retiming)
* 當一句完整的話因為「句中停頓畫框」被拆成多個時間片段時，`retime_subtitles.py` 會依據 `words` 單詞時間戳將文字與時間拆分至各個保留片段，並精準重算字幕新時間軸，徹底解決傳統字幕切片後時間軸錯亂的問題。

### 6. FFmpeg 單管線幀級合成與微軟正黑體硬字幕烙印
* 利用 FFmpeg `filter_complex` 的 `trim`、`atrim` 與 `concat` 濾鏡，在記憶體中一次性完成無損幀級影音拼接，避免多次編解碼產生降質或音訊不同步。
* 輸出時自動透過 `subtitles` 濾鏡烙印（Hardsubs）高對比度微軟正黑體（白字半透明黑底條），保證任何播放器、手機或網頁均能完美呈現清晰字幕。

---

## 二、使用工具與環境需求

| 工具名稱 | 版本需求 | 主要用途 |
| :--- | :--- | :--- |
| **Python** | 3.10 ~ 3.14+ | 核心腳本執行環境 |
| **FFmpeg** | 6.0 ~ 9.0+ | 音訊抽取、物理靜音掃描、關鍵影格採樣、單管線濾鏡合成、字幕烙印 |
| **FFprobe** | 隨附於 FFmpeg | 影片格式、時長、FPS、解析度、音軌中繼資料分析 |
| **Git / GitHub CLI (gh)** | 最新版 | 專案版本控制、懶人包發布與 GitHub Repo 託管 |

> ⚠️ 請確保 `ffmpeg` 與 `ffprobe` 已加入作業系統的 `PATH` 環境變數中。

---

## 三、依賴套件程式清單

本套件採用高效且輕量的深度學習與影像處理庫：

```text
faster-whisper>=1.0.0    # 基於 CTranslate2 打造的極速語音辨識引擎 (比原版 Whisper 快 4 倍且低顯存)
ctranslate2>=4.0.0       # 深度學習模型推論最佳化引擎 (支援 CPU int8 與 GPU 快速計算)
torch>=2.0.0             # PyTorch 底層計算張量支援
numpy>=1.24.0            # 快速陣列運算，用於影像色彩通道遮罩分析
pillow>=10.0.0           # 影格讀取、繪圖標註與 4x4 縮圖網格 (Contact Sheet) 合成
onnxruntime>=1.16.0      # Silero VAD (語音活動偵測) 高效推論執行期
tqdm>=4.65.0             # 終端進度條顯示
```

一鍵安裝方式：
```bash
pip install -r requirements.txt
```

---

## 四、核心腳本架構與功能說明

```
影音自動剪輯-20261115/
├── scripts/
│   ├── auto_pipeline.py     # 【一鍵整合主腳本】端到端全自動分析、切片、重算字幕與烙印渲染
│   ├── transcribe.py        # 【語音轉寫模組】Faster-Whisper + 350ms VAD + -30dB 物理聲學爆發對齊
│   ├── detect_silence.py    # 【靜音掃描模組】FFmpeg silencedetect 偵測 >0.8s 之長靜音斷崖
│   ├── sample_frames.py     # 【視覺分析模組】自動掃描紅框標註像素 (R-G>100) 並生成 4x4 縮圖網格
│   ├── retime_subtitles.py  # 【字幕重對齊模組】單詞時間戳跨片段拆分、新時間軸重算、同音錯字替換
│   └── render_edit.py       # 【影音合成模組】FFmpeg 單管線 trim/concat 幀級剪輯與硬字幕烙印
├── references/
│   ├── common_typos.json    # 【專有名詞校正表】常見 IT/AI 教學同音錯字對照表
│   └── recording_sop.md     # 【錄影實踐指南】給教學講師的螢幕錄影黃金習慣 SOP
├── requirements.txt         # Python 依賴套件清單
├── run_editor.bat           # Windows 拖曳一鍵執行批次檔
└── README.md                # 懶人包詳細說明手冊 (本文件)
```

---

## 五、搭配技能與 SOP 規範

### 1. `auto-video-editor` 專屬技能 (Skill)
* 規範 AI Agent 在處理教學錄影時的剪輯策略、參數設定與多模態檢驗標準。
* 注入 `initial_prompt` 提示詞（如 `Google AI Studio, API Key, OpenCode, Gemini 3.5 Flash, Token...`），大幅提高專有名詞首輪辨識準確率。

### 2. 教學同音錯字庫 (`common_typos.json`)
自動將常見 Whisper 辨識錯字校正為正式術語：
* `席池疊 / 西槽` ➔ `C槽`
* `珠池疊 / 低槽` ➔ `D槽`
* `AI n捲 / AI Engine` ➔ `AI Agent`
* `Component Java / Compure鍵加V` ➔ `Ctrl 鍵加 V`
* `專案一個inter件` ➔ `按下一個Enter鍵`
* `7000廚藝 / 7000處理` ➔ `7,000 除以`

### 3. 教師錄影黃金口訣
> **「開口滑鼠停 ➔ 畫框嘴巴閉 ➔ 講完再點擊 ➔ 講錯停兩秒整句重來」**

---

## 六、快速上手指南 (Quick Start)

### 方式 A：Windows 拖曳一鍵執行（最簡單）
1. 安裝環境：開啟終端機執行 `pip install -r requirements.txt`。
2. 直接將您的教學影片（如 `07.mp4`）用滑鼠拖曳到 `run_editor.bat` 上放開。
3. 程式將自動執行辨識、剪輯、字幕重算與硬字幕烙印，於同目錄產出 `*_auto_edited.mp4`！

---

### 方式 B：Python 一鍵自動剪輯指令
```bash
# 基本用法 (自動辨識 + 自動切除死寂等待 + 烙印字幕)
python scripts/auto_pipeline.py "教學錄影.mp4"

# 指定輸出檔名與 Whisper 模型 (可選: tiny, base, small, medium, large-v3)
python scripts/auto_pipeline.py "教學錄影.mp4" -o "成品_剪輯完成.mp4" -m small

# 僅剪輯影片不烙印硬字幕 (純淨版)
python scripts/auto_pipeline.py "教學錄影.mp4" --no-sub
```

---

### 方式 C：專業分步細緻剪輯流程 (SOP)

如果您希望人工介入或由 AI Agent 逐段微調剪輯區間：

#### 步驟 1：語音轉寫與聲學邊界偵測
```bash
python scripts/transcribe.py "input.mp4" "transcript.json"
```

#### 步驟 2：視覺紅框與關鍵影格抽樣
```bash
# 針對特定關鍵時間點抽樣影格並產出 4x4 縮圖網格
python scripts/sample_frames.py "input.mp4" "15.5,23.0,45.2,88.0" "frames"
```

#### 步驟 3：微調規劃保留區間 (`clips.json`)
依據 `transcript.json` 與紅框診斷結果，撰寫保留片段：
```json
[
  [12.50, 48.20, "步驟一：介紹登入畫面"],
  [52.10, 85.30, "步驟二：點選 Create API Key 並複製"]
]
```

#### 步驟 4：字幕時間軸重算
```bash
python scripts/retime_subtitles.py "transcript.json" "clips.json" "output.srt" "references/common_typos.json"
```

#### 步驟 5：FFmpeg 單管線幀級合成與字幕烙印
```bash
python scripts/render_edit.py "input.mp4" "clips.json" "final_output.mp4" "output.srt"
```

---

## 七、常見問題與最佳實踐

1. **Q: 為什麼不用傳統的音量閥（Silence Remove）？**  
   * **A**: 傳統音量閥無法理解「講話內容」，講師若口誤重講三遍，音量閥會保留三遍；講師若一邊畫紅框一邊微弱呼吸，音量閥會把畫面截得七零八落。本工作流以語意（Whisper）＋ 聲學（-30dB）＋ 視覺（紅框標註）作為決策中樞，精準保留最滿意的一次 Take。

2. **Q: 字幕字體可以更換嗎？**  
   * **A**: 可以，請開啟 `scripts/render_edit.py`，修改 `FontName=Microsoft JhengHei` 為您偏好的字型名稱（例如 `Noto Sans CJK TC`、`PingFang TC` 等）。

3. **Q: 如何提升專有名詞辨識精確度？**  
   * **A**: 可在 `scripts/transcribe.py` 中的 `DEFAULT_INITIAL_PROMPT` 增加您該堂課程的關鍵字，並在 `references/common_typos.json` 新增替換詞對。

---

🎉 **祝您錄製與自動剪輯教學影片順暢高效！**
