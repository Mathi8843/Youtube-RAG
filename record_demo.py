"""
Screen recording script for YouTube RAG demo.
Captures full screen at 10 fps and saves as MP4 via ffmpeg.
"""
import subprocess
import time
import sys
import os

OUTPUT_PATH = r"c:\Users\MATHI\OneDrive\Desktop\Self Made\Youtube RAG\youtube_rag_demo.mp4"
DURATION = 240  # seconds to record (4 minutes max)
FPS = 10

print("=" * 60)
print("YouTube RAG Demo Screen Recorder")
print("=" * 60)
print(f"Output: {OUTPUT_PATH}")
print(f"Duration: up to {DURATION}s  |  FPS: {FPS}")
print()
print("INSTRUCTIONS:")
print("  1. Switch to your browser window (http://localhost:5173)")
print("  2. Perform the demo:")
print("     - Show landing page & scroll down features")
print("     - Click 'Build Knowledge Base'")
print("     - Add 'Deep Learning' video (click pill, then add)")
print("     - Wait for indexing (~15-30s)")
print("     - Add 'Neural Networks' video")
print("     - Click 'Start Chatting'")
print("     - Ask: 'What is a neural network?'")
print("     - Wait for answer with timestamps")
print("     - Ask another question")
print("     - Click 'Generate Notes'")
print("  3. Press Ctrl+C when done (or wait for auto-stop)")
print()
print("Recording starts in 5 seconds...")
for i in range(5, 0, -1):
    print(f"  {i}...")
    time.sleep(1)

print("\n[REC] RECORDING STARTED\n")

# Use ffmpeg gdigrab (Windows screen capture) directly
cmd = [
    "ffmpeg", "-y",
    "-f", "gdigrab",
    "-framerate", str(FPS),
    "-i", "desktop",
    "-vf", "scale=1280:720:flags=lanczos",
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "23",
    "-pix_fmt", "yuv420p",
    "-t", str(DURATION),
    OUTPUT_PATH
]

try:
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"Recording... (will auto-stop after {DURATION}s or press Ctrl+C)")
    
    start = time.time()
    while True:
        elapsed = int(time.time() - start)
        print(f"\r  >> {elapsed}s elapsed   ", end="", flush=True)
        
        if proc.poll() is not None:
            print(f"\n\nRecording finished (ffmpeg exited).")
            break
        
        time.sleep(1)
        
        if elapsed >= DURATION:
            print(f"\n\nMax duration reached, stopping...")
            break

except KeyboardInterrupt:
    print(f"\n\nStopping recording (Ctrl+C)...")

finally:
    if 'proc' in locals() and proc.poll() is None:
        proc.communicate(input=b'q')  # send 'q' to ffmpeg to stop gracefully
        proc.wait(timeout=10)

print(f"\nDone! Saved to: {OUTPUT_PATH}")

# check file size
if os.path.exists(OUTPUT_PATH):
    size_mb = os.path.getsize(OUTPUT_PATH) / (1024*1024)
    print(f"   File size: {size_mb:.1f} MB")
else:
    print("   WARNING: File not found - check ffmpeg output above for errors")
