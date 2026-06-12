"""MYRA Setup — Montoo"""
import subprocess, sys

print("=" * 55)
print("  M.Y.R.A — My Responsive Assistant by Montoo")
print("=" * 55)

steps = [
    ([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], "Installing requirements"),
    ([sys.executable, "-m", "playwright", "install"], "Installing Playwright"),
]
for cmd, label in steps:
    print(f"\n[*] {label}...")
    subprocess.run(cmd, check=True)

print("\n[*] Verifying face_recognition...")
try:
    import face_recognition; print("  face_recognition OK ✓")
except ImportError:
    print("  Installing face_recognition (needs cmake + dlib)...")
    subprocess.run([sys.executable, "-m", "pip", "install", "cmake", "dlib", "face_recognition"], check=True)

print("""
✅ Setup complete!

  RUN:  python main.py

FIRST LAUNCH:
  • Boss ka face automatically data/boss_photo.jpg se enroll hoga
  • Camera hamesha on rahega from startup
  • MYRA aapko pehchan ke greet karegi
  • Agar aap chup rahe toh expression dekh ke MYRA khud baat karegi (Girlfriend Mode)

MANUALLY ENROLL:
  python -c "from face_watcher import enroll_live; enroll_live('Boss')"
""")
