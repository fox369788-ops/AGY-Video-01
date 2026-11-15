import sys
import os
import json
import argparse
import time

# Add current scripts directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

from transcribe import transcribe
from detect_silence import detect_silence
from retime_subtitles import retime_subtitles
from render_edit import render_edit

def generate_default_clips(transcript_data, max_gap=0.35, pad_start=0.15, pad_end=0.20):
    """
    Generate initial keep intervals based on acoustic bursts & segment timestamps.
    Merges nearby bursts with natural breathing pause (<= 0.35s).
    """
    raw_spans = []
    for seg in transcript_data:
        bursts = seg.get("acoustic_bursts", [])
        if bursts:
            for b_start, b_end in bursts:
                raw_spans.append((max(0.0, b_start - pad_start), b_end + pad_end, seg.get("text", "")))
        else:
            s_start = seg.get("acoustic_start", seg["start"])
            s_end = seg.get("acoustic_end", seg["end"])
            raw_spans.append((max(0.0, s_start - pad_start), s_end + pad_end, seg.get("text", "")))

    if not raw_spans:
        return []

    # Sort spans by start time
    raw_spans.sort(key=lambda x: x[0])

    merged = []
    cur_start, cur_end, cur_label = raw_spans[0]

    for next_start, next_end, next_label in raw_spans[1:]:
        if next_start <= cur_end + max_gap:
            # Overlapping or within breathing pause, merge
            cur_end = max(cur_end, next_end)
            if next_label and next_label not in cur_label:
                cur_label = f"{cur_label} / {next_label}"
        else:
            merged.append([round(cur_start, 2), round(cur_end, 2), cur_label[:60]])
            cur_start, cur_end, cur_label = next_start, next_end, next_label

    merged.append([round(cur_start, 2), round(cur_end, 2), cur_label[:60]])
    return merged

def run_pipeline(video_path, output_mp4=None, model_size="small", burn_sub=True, typo_path=None):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    base_name = os.path.splitext(video_path)[0]
    if output_mp4 is None:
        output_mp4 = f"{base_name}_auto_edited.mp4"

    transcript_json = f"{base_name}_transcript.json"
    clips_json = f"{base_name}_clips.json"
    srt_path = f"{base_name}_subtitles.srt"

    if typo_path is None:
        default_typo = os.path.join(os.path.dirname(SCRIPT_DIR), "references", "common_typos.json")
        if os.path.exists(default_typo):
            typo_path = default_typo

    print("=" * 60)
    print("【影音自動剪輯工作流 - 自動化執行】")
    print(f"輸入影片: {video_path}")
    print(f"輸出影片: {output_mp4}")
    print("=" * 60)

    # 1. 語音辨識與聲學邊界偵測
    print("\n>>> 步驟 1: 執行 Faster-Whisper 轉寫與物理聲學邊界偵測...")
    t0 = time.time()
    transcript_data = transcribe(video_path, transcript_json, model_size=model_size)
    print(f"轉寫完成，耗時 {time.time()-t0:.1f} 秒，共偵測到 {len(transcript_data)} 個語音片段。")

    # 2. 自動分析保留區間 (Keep Intervals)
    print("\n>>> 步驟 2: 計算保留區間 (Keep Intervals，去除靜音與死寂等待)...")
    clips = generate_default_clips(transcript_data)
    with open(clips_json, "w", encoding="utf-8") as f:
        json.dump(clips, f, ensure_ascii=False, indent=2)
    print(f"已生成 {len(clips)} 個保留切片，儲存於: {clips_json}")

    # 3. 字幕時間軸重算與錯字校正
    print("\n>>> 步驟 3: 重新計算字幕時間軸並套用專有名詞校正...")
    retime_subtitles(transcript_json, clips, srt_path, typo_dict_path=typo_path)

    # 4. FFmpeg 單管線幀級剪輯與硬字幕烙印
    print("\n>>> 步驟 4: FFmpeg 高效剪輯合成與字幕烙印...")
    render_edit(video_path, clips, output_mp4, srt_path=srt_path if burn_sub else None)

    print("\n" + "=" * 60)
    print(f"🎉 剪輯完成！成品影片: {os.path.abspath(output_mp4)}")
    print(f"📄 剪輯資訊檔: {os.path.abspath(clips_json)}")
    print(f"💬 字幕檔: {os.path.abspath(srt_path)}")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto Video Editor 一鍵自動剪輯工具")
    parser.add_argument("video", help="輸入待剪輯影片路徑 (.mp4)")
    parser.add_argument("-o", "--output", help="輸出剪輯後影片路徑 (.mp4)", default=None)
    parser.add_argument("-m", "--model", help="Faster-Whisper 模型大小 (tiny, base, small, medium, large-v3)", default="small")
    parser.add_argument("--no-sub", action="store_true", help="不烙印硬字幕")
    parser.add_argument("--typos", help="自訂同音錯字校正字典 (.json)", default=None)

    args = parser.parse_args()
    run_pipeline(
        video_path=args.video,
        output_mp4=args.output,
        model_size=args.model,
        burn_sub=not args.no_sub,
        typo_path=args.typos
    )
