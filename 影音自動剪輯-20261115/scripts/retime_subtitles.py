import sys
import json
import os

def find_clip_for_time(t, clips, tol=0.20):
    """
    Find which clip index contains original timestamp `t` (with tolerance `tol`).
    Returns (clip_index, new_time_seconds) or (None, None).
    """
    accum = 0.0
    for idx, clip in enumerate(clips):
        start = clip[0]
        end = clip[1]
        if start - tol <= t <= end + tol:
            clamped = max(start, min(end, t))
            return idx, accum + (clamped - start)
        accum += (end - start)
    return None, None

def format_timestamp_srt(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        secs += 1
        millis = 0
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def apply_typos(text, typos):
    text = text.strip()
    for k, v in typos.items():
        text = text.replace(k, v)
    return text

def retime_subtitles(transcript_json, clips, output_srt, typo_dict_path=None):
    with open(transcript_json, "r", encoding="utf-8") as f:
        orig_segs = json.load(f)

    typos = {}
    if typo_dict_path and os.path.exists(typo_dict_path):
        with open(typo_dict_path, "r", encoding="utf-8") as f:
            typos = json.load(f)

    new_subtitles = []
    sub_id = 1

    for seg in orig_segs:
        s_start = seg.get("acoustic_start", seg["start"])
        s_end = seg.get("acoustic_end", seg["end"])
        c_idx_s, new_start = find_clip_for_time(s_start, clips)
        c_idx_e, new_end = find_clip_for_time(s_end, clips)

        if c_idx_s is not None and c_idx_e is not None and c_idx_s == c_idx_e:
            # Entire segment falls within a single clip
            text = apply_typos(seg["text"], typos)
            if len(text) > 0 and new_end > new_start + 0.05:
                new_subtitles.append({
                    "id": sub_id,
                    "start": new_start,
                    "end": new_end,
                    "text": text
                })
                sub_id += 1
        elif seg.get("words"):
            # Segment was split across multiple clips (e.g., mid-sentence pause for drawing a red box)
            # Group words by the clip they belong to
            grouped = {}
            for w in seg["words"]:
                w_mid = 0.5 * (w["start"] + w["end"])
                c_idx, _ = find_clip_for_time(w_mid, clips, tol=0.15)
                if c_idx is not None:
                    grouped.setdefault(c_idx, []).append(w)

            for c_idx in sorted(grouped.keys()):
                w_list = grouped[c_idx]
                _, w_new_start = find_clip_for_time(w_list[0]["start"], clips, tol=0.25)
                _, w_new_end = find_clip_for_time(w_list[-1]["end"], clips, tol=0.25)
                raw_text = "".join(w["word"] for w in w_list)
                text = apply_typos(raw_text, typos)
                if w_new_start is not None and w_new_end is not None and len(text) > 0 and w_new_end > w_new_start + 0.05:
                    new_subtitles.append({
                        "id": sub_id,
                        "start": w_new_start,
                        "end": w_new_end,
                        "text": text
                    })
                    sub_id += 1

    srt_lines = []
    for sub in new_subtitles:
        srt_lines.append(str(sub["id"]))
        srt_lines.append(f"{format_timestamp_srt(sub['start'])} --> {format_timestamp_srt(sub['end'])}")
        srt_lines.append(sub["text"])
        srt_lines.append("")

    with open(output_srt, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    print(f"Exported {len(new_subtitles)} synchronized subtitles to {output_srt}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python retime_subtitles.py <transcript_json> <clips_json> <output_srt> [typos_json]")
        sys.exit(1)
    t_json = sys.argv[1]
    with open(sys.argv[2], "r", encoding="utf-8") as f:
        c = json.load(f)
    out = sys.argv[3]
    t_dict = sys.argv[4] if len(sys.argv) > 4 else None
    retime_subtitles(t_json, c, out, t_dict)
