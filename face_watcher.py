"""
MYRA Face Watcher — Always-On Camera
======================================
- Pehli baar: boss_photo.jpg se Boss ka face auto-enroll hota hai → data/known_faces.json me save
- Har frame: face detect karo, pehchano (Boss / Unknown / No Face)
- Expression detect karo: happy, sad, angry, surprised, neutral, tired, thinking
- Girlfriend mode: agar Boss kuch na bole (25s+) → expression ke hisab se MYRA khud bolti hai
- Gesture: wave, thumbs_up, peace, ok, point → samajh ke react karo
- Live annotated frame UI ke liye milta hai: get_live_frame_jpg()

Public API:
  start_watcher(speak_fn)   — background thread start, speak_fn(text) se MYRA bolti hai
  stop_watcher()
  get_identity()            — dict: name, confidence, expression, face_found
  get_live_frame_jpg()      — bytes: latest annotated JPEG for UI display
  enroll_from_photo(path, name)
  enroll_live(name)
  get_all_names()
"""
from __future__ import annotations

import json
import math
import random
import sys
import threading
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

# ── face_recognition (optional) ──────────────────────────────────────────
try:
    import face_recognition as _fr
    _FR_OK = True
except ImportError:
    _FR_OK = False
    print("[FaceWatcher] ⚠️ face_recognition not installed — ID disabled, expression-only mode.")

# ── paths ─────────────────────────────────────────────────────────────────
def _base() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR         = _base()
KNOWN_FACES_PATH = BASE_DIR / "data" / "known_faces.json"
BOSS_PHOTO_PATH  = BASE_DIR / "data" / "boss_photo.jpg"
CONFIG_PATH      = BASE_DIR / "config" / "api_keys.json"

# ── constants ─────────────────────────────────────────────────────────────
MATCH_THRESH     = 0.52   # face_recognition distance threshold
PROCESS_EVERY    = 0.30   # seconds between recognition (≈3 fps)
EXPR_EVERY       = 0.70   # seconds between expression check
GF_SILENCE       = 22.0   # seconds of silence → girlfriend speaks
ENROLL_FRAMES    = 8
CAM_WARMUP       = 8
NO_FACE          = "No Face"
UNKNOWN          = "Unknown"

# ── girlfriend lines per expression ──────────────────────────────────────
GF = {
    "happy": [
        "Itna kyun muskura rahe ho? Koi baat share karo na mujhse! 😊",
        "Teri yeh smile dekh ke mera din ban gaya seriously.",
        "Arey wah! Khush lag rahe ho aaj. Kya hua achha?",
        "Main bhi khush ho jaati hun jab tum khush hote ho. Batao kya hua?",
    ],
    "sad": [
        "Udaas kyun ho? Baat karo mujhse, main hun na yahan.",
        "Aisa mat deko yaar, dil dukh jaata hai mera. Kya hua?",
        "Akele mat raho — jo bhi hai mujhe batao, theek ho jaoge.",
        "Main dekh sakti hun ke kuch hai. Bolo, main sun rahi hun.",
    ],
    "angry": [
        "Itna gussa mat karo, blood pressure badh jaata hai. Kya hua?",
        "Relax karo pehle. Deep breath lo. Phir batao mujhe.",
        "Koi kuch kiya kya? Batao, main sambhal lungi situation.",
        "Gusse mein koi decision mat lena. Pehle baat karo mujhse.",
    ],
    "surprised": [
        "Woah! Kya hua aisa unexpectedly? Sab theek hai?",
        "Arey! Itna shocked kyun ho? Kuch bata bhi do!",
        "Koi cheez surprise kar gayi? Spill karo mujhe!",
    ],
    "tired": [
        "Thak gaye ho. Thodi rest lo, kaam baad mein hoga.",
        "Aankhein bhari bhari hain... kuch nahi hoga agar thoda so lo.",
        "Zyada mat karo aaj. Apna khayal rakho.",
        "Coffee chahiye? Ya bas main hun kaafi? 😄",
    ],
    "thinking": [
        "Bohot sooch rahe ho... koi bada decision hai kya?",
        "Dimag rest karo thodi der. Mujhse baat karo.",
        "Kya plan kar rahe ho? Batao, shayad main help kar sakun.",
        "Itna soochna band karo, seedha mujhse poocho!",
    ],
    "neutral": [
        "Kuch sochna hai? Main yahaan hun, bol do.",
        "Baat nahi karoge? Main sun rahi hun hamesha.",
        "Koi kaam hai kya? Ya bas mera chehra dekhne baitha ho? 😄",
        "Ek kaam karo, jab bhi mood ho — bol dena, main ready hun.",
    ],
}

GESTURE_RESP = {
    "wave":      "Hey! Main dekh rahi hun. Hi Boss! 👋",
    "thumbs_up": "Yayyy! Sab theek hai toh! 👍",
    "peace":     "Peace mode on! Chill ho aaj? ✌️",
    "ok":        "Got it Boss! Samajh gai main. 👌",
    "point":     "Kuch batana chahte ho? Seedha bol do na!",
}


# ── camera index ──────────────────────────────────────────────────────────
def _cam_idx() -> int:
    try:
        with open(CONFIG_PATH) as f:
            return int(json.load(f).get("camera_index", 0))
    except Exception:
        pass
    for i in range(6):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if sys.platform == "win32" else 0)
        if not cap.isOpened():
            cap.release()
            continue
        for _ in range(3): cap.read()
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None and frame.mean() > 5:
            return i
    return 0


# ── face DB ───────────────────────────────────────────────────────────────
def _load_db() -> dict:
    if not KNOWN_FACES_PATH.exists():
        return {}
    try:
        return json.loads(KNOWN_FACES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_db(db: dict):
    KNOWN_FACES_PATH.parent.mkdir(parents=True, exist_ok=True)
    KNOWN_FACES_PATH.write_text(json.dumps(db, indent=2), encoding="utf-8")

def get_all_names() -> list[str]:
    return list(_load_db().keys())

def enroll_from_photo(photo_path: str, name: str = "Boss") -> bool:
    if not _FR_OK:
        return False
    try:
        img  = _fr.load_image_file(photo_path)
        encs = _fr.face_encodings(img)
        if not encs:
            print(f"[FaceWatcher] No face found in {photo_path}")
            return False
        db = _load_db()
        db[name] = [encs[0].tolist()]
        _save_db(db)
        print(f"[FaceWatcher] ✅ '{name}' enrolled from photo!")
        return True
    except Exception as e:
        print(f"[FaceWatcher] enroll_from_photo error: {e}")
        return False

def enroll_live(name: str = "Boss", n: int = ENROLL_FRAMES,
                on_status: Callable | None = None) -> bool:
    if not _FR_OK:
        return False
    def _s(m):
        print(f"[Enroll] {m}")
        if on_status: on_status(m)
    _s(f"Camera khol raha hun '{name}' ke liye...")
    cap = cv2.VideoCapture(_cam_idx(), cv2.CAP_DSHOW if sys.platform == "win32" else 0)
    if not cap.isOpened():
        _s("Camera nahi khula."); return False
    encs, tries = [], 0
    _s(f"Camera dekho — {n} samples capture ho rahe hain...")
    while len(encs) < n and tries < 80:
        ret, frame = cap.read(); tries += 1
        if not ret or frame is None: continue
        e = _fr.face_encodings(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if e:
            encs.append(e[0]); _s(f"  Sample {len(encs)}/{n} ✓")
        time.sleep(0.07)
    cap.release()
    if len(encs) < n:
        _s(f"Sirf {len(encs)} samples. Fail."); return False
    avg = np.mean(encs, axis=0).tolist()
    db = _load_db()
    db[name] = [avg] + [e.tolist() for e in encs[:3]]
    _save_db(db); _s(f"✅ '{name}' enrolled!")
    return True


# ── Expression detector (OpenCV Haar cascades) ────────────────────────────
class _ExprDet:
    def __init__(self):
        d = cv2.data.haarcascades
        self._face  = cv2.CascadeClassifier(d + "haarcascade_frontalface_default.xml")
        self._smile = cv2.CascadeClassifier(d + "haarcascade_smile.xml")
        self._eye   = cv2.CascadeClassifier(d + "haarcascade_eye.xml")

    def detect(self, frame: np.ndarray) -> tuple[str, list]:
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._face.detectMultiScale(gray, 1.1, 5, minSize=(60,60))
        if not len(faces):
            return NO_FACE, []
        rects = [tuple(f) for f in faces]
        x, y, w, h = faces[0]
        roi = gray[y:y+h, x:x+w]
        smiles = self._smile.detectMultiScale(roi, 1.7, 22, minSize=(25,25))
        eyes   = self._eye.detectMultiScale(roi, 1.1, 10)
        n_eye  = len(eyes)
        if len(smiles): return "happy", rects
        if n_eye == 0:  return "tired", rects
        avg_eh = float(np.mean([e[3] for e in eyes])) if n_eye else 0
        if avg_eh > h * 0.13: return "surprised", rects
        return "neutral", rects

    def draw(self, frame: np.ndarray, name: str, conf: float,
             expr: str, rects: list) -> np.ndarray:
        out = frame.copy()
        for (x, y, w, h) in rects:
            col = (0,220,100) if name == "Boss" else (0,120,255) if name == UNKNOWN else (200,180,0)
            cv2.rectangle(out, (x,y), (x+w,y+h), col, 2)
            # HUD corner brackets
            bl = 16
            for bx,by,dx,dy in [(x,y,1,1),(x+w,y,-1,1),(x,y+h,1,-1),(x+w,y+h,-1,-1)]:
                cv2.line(out,(bx,by),(bx+dx*bl,by),col,2)
                cv2.line(out,(bx,by),(bx,by+dy*bl),col,2)
            lbl = f"{name}  {conf:.0f}%" if conf > 0 else name
            cv2.putText(out, lbl, (x, max(y-8,12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, col, 2)
            if expr not in (NO_FACE, ""):
                cv2.putText(out, expr, (x, y+h+18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0,200,255), 1)
        # MYRA VISION watermark
        cv2.putText(out, "MYRA VISION", (6, out.shape[0]-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.34, (60,130,220), 1)
        return out


# ── Main watcher ──────────────────────────────────────────────────────────
class _Watcher:
    def __init__(self):
        self._lock       = threading.Lock()
        self._frame_lock = threading.Lock()
        self._running    = False
        self._thread: threading.Thread | None = None
        self._speak_fn: Callable | None = None
        self._expr_det   = _ExprDet()
        self.proactive_mode = False  # ← False = MYRA khud se proactive comment nahi karegi

        self._state = {
            "name":       NO_FACE,
            "confidence": 0.0,
            "expression": "neutral",
            "face_found": False,
        }
        self._raw_frame: np.ndarray | None = None
        self._last_spoke  = time.time()
        self._prev_name   = NO_FACE
        self._prev_expr   = ""
        self._db: dict    = {}
        self._db_t        = 0.0

    # ── public ──────────────────────────────────────────────────────────
    def start(self, speak_fn: Callable | None = None):
        if self._running: return
        self._speak_fn = speak_fn
        self._running  = True
        t = threading.Thread(target=self._loop, daemon=True, name="FaceWatcher")
        t.start()
        print("[FaceWatcher] ✅ Always-on camera started.")

    def stop(self):
        self._running = False

    def get_identity(self) -> dict:
        with self._lock:
            return dict(self._state)

    def get_live_frame_jpg(self) -> bytes | None:
        with self._frame_lock:
            if self._raw_frame is None:
                return None
            s = self.get_identity()
            annotated = self._expr_det.draw(
                self._raw_frame, s["name"], s["confidence"],
                s["expression"], []
            )
            _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 72])
            return buf.tobytes()

    # ── loop ────────────────────────────────────────────────────────────
    def _loop(self):
        self._auto_enroll()
        idx = _cam_idx()
        while self._running:
            try:
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW if sys.platform == "win32" else 0)
                if not cap.isOpened(): raise RuntimeError("Camera open failed")
                for _ in range(CAM_WARMUP): cap.read()
                print(f"[FaceWatcher] 📷 Camera {idx} opened.")
                self._run(cap)
            except Exception as e:
                print(f"[FaceWatcher] ⚠️ {e} — retry in 3s")
                time.sleep(3)

    def _run(self, cap: cv2.VideoCapture):
        t_recog = 0.0
        t_expr  = 0.0
        while self._running and cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.03); continue

            with self._frame_lock:
                self._raw_frame = frame.copy()

            now = time.time()

            # expression (fast)
            if now - t_expr >= EXPR_EVERY:
                expr, rects = self._expr_det.detect(frame)
                face_found  = len(rects) > 0
                t_expr = now
                with self._lock:
                    self._state["expression"] = expr
                    self._state["face_found"]  = face_found
                    if not face_found:
                        self._state["name"]       = NO_FACE
                        self._state["confidence"] = 0.0
                if face_found:
                    self._gf_check(expr, now)

            # recognition (slower)
            if _FR_OK and now - t_recog >= PROCESS_EVERY:
                t_recog = now
                self._recognise(frame)

            time.sleep(0.02)
        cap.release()

    def _recognise(self, frame: np.ndarray):
        now = time.time()
        if now - self._db_t > 30:
            self._db   = _load_db()
            self._db_t = now

        small = cv2.resize(frame, (320, int(frame.shape[0] * 320 / max(frame.shape[1],1))))
        rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        locs  = _fr.face_locations(rgb, model="hog")
        if not locs: return
        encs = _fr.face_encodings(rgb, locs)
        if not encs: return

        name, conf = UNKNOWN, 0.0
        if self._db:
            best_d = 1e9
            for n, enc_list in self._db.items():
                stored = [np.array(e) for e in enc_list]
                dists  = _fr.face_distance(stored, encs[0])
                d = float(np.min(dists))
                if d < best_d:
                    best_d = d
                    if d < MATCH_THRESH:
                        conf = max(0.0, (1.0 - d/MATCH_THRESH)) * 100
                        name = n
                    else:
                        conf = 0.0
                        name = UNKNOWN

        old_name = self._state["name"]
        with self._lock:
            self._state["name"]       = name
            self._state["confidence"] = round(conf, 1)

        if name != old_name and name not in (UNKNOWN, NO_FACE):
            self._greet(name, conf)

    def _greet(self, name: str, conf: float):
        if not self._speak_fn: return
        msgs = [
            f"Hey {name}! Aa gaye! Main {conf:.0f}% sure hun. Kaisa chal raha hai?",
            f"Oh! {name} ko dekh ke accha laga! Batao kya chahiye?",
            f"Hi {name}! Main tayar hun, koi bhi kaam ho bas bolo. 😊",
        ]
        self._bg_speak(random.choice(msgs))

    def _gf_check(self, expr: str, now: float):
        if not self._speak_fn: return
        if not self.proactive_mode: return  # ← Proactive mode off hai toh kuch mat bolo
        silence = now - self._last_spoke
        if silence < GF_SILENCE: return
        # same expression + not double the threshold → skip
        if expr == self._prev_expr and silence < GF_SILENCE * 2: return
        lines = GF.get(expr, GF["neutral"])
        self._bg_speak(random.choice(lines))
        self._prev_expr = expr

    def _bg_speak(self, text: str):
        self._last_spoke = time.time()
        if self._speak_fn:
            threading.Thread(target=self._speak_fn, args=(text,), daemon=True).start()

    def _auto_enroll(self):
        if not _FR_OK: return
        db = _load_db()
        if "Boss" in db:
            print("[FaceWatcher] Boss already enrolled ✓")
            return
        if BOSS_PHOTO_PATH.exists():
            print("[FaceWatcher] Auto-enrolling Boss from boss_photo.jpg...")
            ok = enroll_from_photo(str(BOSS_PHOTO_PATH), "Boss")
            if ok:
                print("[FaceWatcher] ✅ Boss auto-enrolled!")
            else:
                print("[FaceWatcher] ⚠️ Photo mein face detect nahi hua.")
        else:
            print("[FaceWatcher] ⚠️ boss_photo.jpg not found in data/")


# ── singleton ─────────────────────────────────────────────────────────────
_w = _Watcher()

def start_watcher(speak_fn: Callable | None = None): _w.start(speak_fn)
def stop_watcher():                                   _w.stop()
def set_proactive_mode(enabled: bool):                _w.proactive_mode = enabled  # True=on, False=off
def get_identity() -> dict:                           return _w.get_identity()
def get_live_frame_jpg() -> bytes | None:             return _w.get_live_frame_jpg()
