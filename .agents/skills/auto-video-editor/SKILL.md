---
name: auto-video-editor
description: >-
  Automated video editing for teacher screen recordings, programming tutorials, and screencasts.
  Use this skill whenever the user asks to automatically edit, trim, remove silences/mistakes/repetitions,
  or generate synchronized subtitles for tutorial or instructional screen recording videos.
---

# Auto Video Editor (教學影片自動剪輯專家 v2.0)

專為教師與講師螢幕教學錄影設計的自動剪輯工作流。結合 **Faster-Whisper 領域提示語音辨識（350ms 細粒度 VAD + 單詞時間戳 + 物理聲學邊界校正）**、**紅框標註像素自動偵測 + 4×4 縮圖網格（Contact Sheet）視覺檢驗** 與 **FFmpeg 單管線幀級合成**，實現無縫剔除口誤、重錄段落、句中畫框長停頓與操作等待。

---

## 核心剪輯三大黃金法則（Golden Rules）

1. **標註即點選 + 句中畫框無縫跳接（Annotation Equals Click & Mid-Sentence Drawing Trim）**：
   * 教師在螢幕上以畫筆（如 ZoomIt）畫出**紅框、紅圈、箭頭或打勾**時，該標註完成且語音指引講畢之處，即代表該按鈕「已經被點選」。
   * **句中停頓畫框處理**：當教師講完上半句、停頓數秒畫紅框、再接著講下半句時，自動切除中間無聲畫框等待，讓紅框隨下半句開口瞬間俐落呈現。
   * **點擊與載入跳切**：在標註完畢的瞬間，**直接瞬切（Jump Cut）至下一個操作或載入完成的目標畫面**，不保留滑鼠游標移動、點擊等待與載入旋轉動畫。
2. **極速自然呼吸間隔（0.2 ~ 0.3s Pacing）**：
   * 語句與語句之間的時間間隔嚴格控制在 **0.2 ~ 0.3 秒**。
   * 既杜絕跳切吃字，又能維持教學影片明快、洗鍊、緊湊的現代化觀影節奏。
3. **多 Take 智慧篩選與紅框錨點判定（Retake Selection Logic）**：
   * 當講師同一操作重錄多次（或隔數十秒清理畫面後整段重講），嚴格剔除前次口誤、未完成或背景雜亂的瑕疵 Take。
   * 優先採用帶有**紅色視覺標註（`red_pixels >= 200`）**且語意完整的最終正式 Take。

---

## 核心流程 SOP

```
[原始教學影片 MP4]
       │
       ├─► 步驟 1: FFprobe 分析影片規格 (1080p, FPS, 聲軌)
       ├─► 步驟 2: transcribe.py (Faster-Whisper + 領域 Prompt + 350ms VAD + -30dB 聲學邊界自動對齊)
       ├─► 步驟 3: detect_silence.py 偵測 >0.8s 的所有靜音斷崖
       ├─► 步驟 4: sample_frames.py 自動偵測紅框像素 (R-G>100) 並輸出 4x4 縮圖網格 (grid_*.jpg)
       ├─► 步驟 5: 規劃 Keep Intervals (應用標註即點擊、句中畫框去空白、0.2~0.3s 呼吸間隔)
       ├─► 步驟 6: render_edit.py (FFmpeg filter_complex trim/atrim/concat) 一次性無損轉檔
       ├─► 步驟 7: retime_subtitles.py (支援跨切片單詞級自動拆分映射 + common_typos.json 校正)
       └─► 步驟 8: 自動清理中介切片與測試暫存，保持工作目錄乾淨
```

---

## 執行步驟說明

### 步驟 1：前置檢驗
使用 `ffprobe` 檢測輸入影片的長度、解析度與編碼：
```bash
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height -of json "input.mp4"
```

### 步驟 2：語音轉寫與物理聲學邊界對齊 (ASR + VAD + Acoustic Burst Alignment)
調用腳本 [transcribe.py](./scripts/transcribe.py) 進行毫秒級單詞時間戳轉寫：
* 內建教學領域 `initial_prompt`（預載 `Google AI Studio, API Key, OpenCode, AI Agent, Gemini 3.5 Flash, Token, Ctrl鍵加V` 等詞彙）。
* 內建 `350ms` 細粒度 VAD 切分與 `condition_on_previous_text=False`，防止句中停頓畫框時單字時間戳被拉長。
* 自動執行 `-30dB` 物理聲學偵測，為每個段落寫入 `acoustic_start`、`acoustic_end` 與 `acoustic_bursts`。
```bash
python scripts/transcribe.py "input.mp4" "transcript.json"
```

### 步驟 3：靜音與死寂偵測
調用腳本 [detect_silence.py](./scripts/detect_silence.py) 找出所有大於 0.8 秒的靜音區間：
```bash
python scripts/detect_silence.py "input.mp4"
```

### 步驟 4：紅框像素自動偵測與 4×4 縮圖網格視覺診斷
針對重錄區間或長靜音區間，調用 [sample_frames.py](./scripts/sample_frames.py) 抽取關鍵影格：
```bash
python scripts/sample_frames.py "input.mp4" "45,52,56.5,88,93,128,131.5" "frames"
```
* 腳本會自動計算每張影格的**紅色標註像素數（`red_pixels`）與座標框（`red_bbox`）**，並在終端機直接標示 `★ RED ANNOTATION`。
* 腳本會自動將抽樣影格打包成 `frames/grid_1.jpg`, `grid_2.jpg`（4×4 縮圖網格，附時間戳與紅框標記）。**請使用 `read_file` 讀取 `grid_*.jpg` 縮圖網格**，避免逐張讀取 1080p 原圖造成傳輸中斷。

### 步驟 5：規劃保留區間（Keep Intervals）
* 依據 `transcript.json` 中的 `acoustic_bursts` 與 `sample_frames.py` 的紅框標註時間點，規劃 `clips.json`。
* 貫徹「標註即點選」與「句中畫框去空白」法則，銜接間隔保持在 0.2 ~ 0.3 秒。

### 步驟 6 & 7：字幕時間重算、專有名詞校正與單管線影音硬字幕合成
1. 先調用 [retime_subtitles.py](./scripts/retime_subtitles.py) 生成同步校正後的 `.srt` 字幕：
```bash
python scripts/retime_subtitles.py "transcript.json" "clips.json" "output_edited.srt" "references/common_typos.json"
```
* 若某個語音段落因「句中停頓畫框」被拆分為兩個保留片段，`retime_subtitles.py` 會自動依單詞時間戳（`words`）將字幕拆分為兩條並精準對齊各自的新時間軸。
* 自動套用 [common_typos.json](./references/common_typos.json) 校正常見同音錯字。

2. 接著調用 [render_edit.py](./scripts/render_edit.py) 執行剪輯並**將 `.srt` 字幕直接烙印（Burn-in 硬字幕，微軟正黑體白字半透明黑底）進影片畫面**，確保任何播放器打開皆直接顯示字幕：
```bash
python scripts/render_edit.py "input.mp4" "clips.json" "output_edited.mp4" "output_edited.srt"
```

### 步驟 8：工作環境自動清理
渲染與字幕生成完成後，自動刪除臨時測試切片（`.wav`, `frames/`）與中介檔案，僅留存最終成品與設定檔。

---

## 參考手冊
* [教師螢幕錄影錄製 SOP 與最佳實踐](./references/recording_sop.md)：向教師提供錄製時的黃金準則。
