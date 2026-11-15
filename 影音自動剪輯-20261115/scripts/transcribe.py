import sys
import os
import re
import json
import subprocess
import time
from faster_whisper import WhisperModel

DEFAULT_INITIAL_PROMPT = (
    "以下是繁體中文資訊科技與AI程式教學錄影，包含專有名詞："
    "Google AI Studio, API Key, Copy key, Create API key, "
    "OpenCode, OpenCode Console, AI Agent, Gemini 3.5 Flash, Gemini, Flash系列, "
    "Token, 上下文限制, 工作階段, Ctrl鍵加V, C槽, D槽, 資料夾, 剪貼簿。"
)

def extract_audio(video_path, wav_path):
    print(f"Extracting 16kHz mono WAV from {video_path}...")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        wav_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

def detect_acoustic_bursts(wav_path, noise_db="-30dB", min_silence=0.25):
    """Detect physical speech bursts from WAV using FFmpeg silencedetect."""
    cmd = [
        "ffmpeg", "-i", wav_path,
        "-af", f"silencedetect=noise={noise_db}:d={min_silence}",
        "-f", "null", "-"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    lines = res.stderr.splitlines()

    silences = []
    cur_start = None
    total_dur = 99999.0
    for line in lines:
        if "Duration:" in line:
            m_d = re.search(r"Duration:\s*(\d+):(\d+):([0-9.]+)", line)
            if m_d:
                total_dur = int(m_d.group(1)) * 3600 + int(m_d.group(2)) * 60 + float(m_d.group(3))
        if "silence_start:" in line:
            m = re.search(r"silence_start:\s*([0-9.]+)", line)
            if m:
                cur_start = float(m.group(1))
        elif "silence_end:" in line:
            m_end = re.search(r"silence_end:\s*([0-9.]+)", line)
            if m_end and cur_start is not None:
                silences.append((cur_start, float(m_end.group(1))))
                cur_start = None

    bursts = []
    prev_end = 0.0
    for s_start, s_end in silences:
        if s_start > prev_end + 0.05:
            bursts.append((round(prev_end, 3), round(s_start, 3)))
        prev_end = s_end
    if prev_end < total_dur - 0.05:
        bursts.append((round(prev_end, 3), round(total_dur, 3)))
    return bursts

def transcribe(video_path, output_json="transcript.json", model_size="small"):
    wav_path = os.path.splitext(video_path)[0] + "_temp16k.wav"
    try:
        extract_audio(video_path, wav_path)
        print("Detecting physical acoustic speech bursts (-30dB, >=0.25s silence)...")
        bursts = detect_acoustic_bursts(wav_path, noise_db="-30dB", min_silence=0.25)
        print(f"Detected {len(bursts)} acoustic speech bursts.")

        print(f"Loading faster-whisper model '{model_size}' (CPU, int8)...")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")

        print("Transcribing with domain prompt, word timestamps, and 350ms VAD split...")
        t0 = time.time()
        segments, info = model.transcribe(
            wav_path,
            language="zh",
            beam_size=5,
            initial_prompt=DEFAULT_INITIAL_PROMPT,
            condition_on_previous_text=False,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=350, speech_pad_ms=150)
        )
        print(f"Detected language: {info.language} (prob: {info.language_probability:.2f})")

        results = []
        for seg in segments:
            words = [
                {
                    "word": w.word,
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "prob": round(w.probability, 3)
                }
                for w in (seg.words or [])
            ]
            s_start = round(seg.start, 3)
            s_end = round(seg.end, 3)
            overlapping_bursts = [
                [b[0], b[1]] for b in bursts
                if b[1] > s_start - 0.2 and b[0] < s_end + 0.2
            ]
            # Clamp start/end to actual acoustic speech if Whisper stretched across silence
            acoustic_start = overlapping_bursts[0][0] if overlapping_bursts else s_start
            acoustic_end = overlapping_bursts[-1][1] if overlapping_bursts else s_end

            results.append({
                "id": seg.id,
                "start": s_start,
                "end": s_end,
                "acoustic_start": round(max(s_start - 0.2, acoustic_start), 3),
                "acoustic_end": round(min(s_end + 0.2, acoustic_end), 3),
                "acoustic_bursts": overlapping_bursts,
                "text": seg.text.strip(),
                "words": words
            })

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Done! {len(results)} segments written to {output_json} in {time.time()-t0:.1f}s")
        return results
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <video_path> [output_json]")
        sys.exit(1)
    vid = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "transcript.json"
    transcribe(vid, out)
