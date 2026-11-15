import sys
import os
import subprocess
import numpy as np
from PIL import Image, ImageDraw

def analyze_red_annotation(img_path):
    """
    Detect red annotation pixels (e.g., ZoomIt / screen pen red boxes, arrows, checkmarks).
    Returns (red_pixel_count, bbox_or_None).
    """
    arr = np.array(Image.open(img_path))
    if arr.ndim < 3:
        return 0, None
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    mask = (r > 180) & ((r - g) > 100) & ((r - b) > 100)
    count = int(np.sum(mask))
    if count < 50:
        return count, None
    ys, xs = np.where(mask)
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    return count, bbox

def build_contact_sheets(extracted_items, output_dir, batch_size=16, tile_w=400, tile_h=225):
    """
    Build 4x4 contact sheet grids with timestamp & red-annotation indicators
    so multimodal AI can inspect 16 frames at once without large payload interruptions.
    """
    grids = []
    cols = 4
    for b_idx in range(0, len(extracted_items), batch_size):
        batch = extracted_items[b_idx:b_idx + batch_size]
        rows = (len(batch) + cols - 1) // cols
        grid = Image.new("RGB", (cols * tile_w, rows * tile_h), (0, 0, 0))
        draw = ImageDraw.Draw(grid)
        for i, item in enumerate(batch):
            t = item["timestamp"]
            fpath = item["path"]
            red_px = item["red_pixels"]
            img = Image.open(fpath).resize((tile_w, tile_h), Image.Resampling.LANCZOS)
            r = i // cols
            c = i % cols
            x, y = c * tile_w, r * tile_h
            grid.paste(img, (x, y))
            banner_w = 175 if red_px >= 200 else 105
            draw.rectangle([x, y, x + banner_w, y + 24], fill=(0, 0, 0))
            label = f"t={t:.1f}s [RED:{red_px}]" if red_px >= 200 else f"t={t:.1f}s"
            color = (255, 80, 80) if red_px >= 200 else (255, 255, 0)
            draw.text((x + 5, y + 4), label, fill=color)
        grid_path = os.path.join(output_dir, f"grid_{b_idx // batch_size + 1}.jpg")
        grid.save(grid_path, quality=82)
        grids.append(grid_path)
    return grids

def sample_frames(video_path, timestamps, output_dir="frames"):
    os.makedirs(output_dir, exist_ok=True)
    extracted = []
    print(f"=== Sampling {len(timestamps)} frames from {video_path} ===")
    for t in timestamps:
        out_file = os.path.join(output_dir, f"frame_{t:.1f}s.jpg")
        cmd = [
            "ffmpeg", "-y", "-ss", str(t), "-i", video_path,
            "-vframes", "1", "-q:v", "2", out_file
        ]
        subprocess.run(cmd, capture_output=True)
        if os.path.exists(out_file):
            red_px, bbox = analyze_red_annotation(out_file)
            extracted.append({
                "timestamp": t,
                "path": out_file,
                "red_pixels": red_px,
                "red_bbox": bbox
            })
            flag = f"★ RED ANNOTATION ({red_px} px, bbox={bbox})" if red_px >= 200 else f"no red box ({red_px} px)"
            print(f"  t = {t:6.1f}s | {flag}")

    grids = build_contact_sheets(extracted, output_dir)
    print(f"Extracted {len(extracted)} frames and generated {len(grids)} contact sheet grids:")
    for g in grids:
        print(f"  -> {os.path.abspath(g)}")
    return extracted

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python sample_frames.py <video_path> <t1,t2,t3...> [output_dir]")
        sys.exit(1)
    vid = sys.argv[1]
    ts = [float(x.strip()) for x in sys.argv[2].split(",") if x.strip()]
    out_d = sys.argv[3] if len(sys.argv) > 3 else "frames"
    sample_frames(vid, ts, out_d)
