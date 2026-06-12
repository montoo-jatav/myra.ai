"""
M.Y.R.A — Multi-Intelligence Responsive AI
UI Module — Designed by Montoo Jatav
Clean Claude-style interface with MYRA logo
"""

from __future__ import annotations
import json, math, os, platform, random, subprocess, sys, threading, time
from pathlib import Path
import psutil
from PyQt6.QtCore import (
    QPointF, QRectF, Qt,
    QTimer, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFont,
    QKeySequence, QPainter, QPen, QPixmap, QImage,
    QShortcut, QLinearGradient,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMainWindow, QPushButton, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget,
)

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"
_OS = platform.system()

# ─── FONT HELPER — Claude-style clean fonts ───────────────────────────────
def _SF(size: int, bold: bool = False) -> QFont:
    """Returns a clean sans-serif font similar to Claude AI's UI style."""
    for name in ["Segoe UI", "Inter", "SF Pro Display", "Helvetica Neue", "Arial"]:
        f = QFont(name, size, QFont.Weight.Bold if bold else QFont.Weight.Normal)
        if QFont(name).exactMatch() or name in ["Segoe UI", "Arial"]:
            return f
    return QFont("Arial", size, QFont.Weight.Bold if bold else QFont.Weight.Normal)

# ─── COLOR PALETTE ────────────────────────────────────────────────────────
class C:
    BG        = "#0a0a0f"
    BG2       = "#0d0d14"
    DARK      = "#06060a"
    PANEL     = "#111520"
    PANEL2    = "#161b28"
    PANEL3    = "#1a2035"
    RED       = "#cc2200"
    RED_B     = "#ff3300"
    RED_DIM   = "#881500"
    RED_GHO   = "#1a0500"
    RED_GLOW  = "#ff4422"
    ORANGE    = "#ff6622"
    BLUE      = "#2d8cf0"
    BLUE_LT   = "#5aabff"
    WHITE     = "#ffffff"
    TEXT      = "#d4d8e8"
    TEXT_DIM  = "#6a7490"
    TEXT_MED  = "#9aa0b8"
    GREEN     = "#22cc66"
    YELLOW    = "#ffaa00"
    BORDER    = "#1e2a40"
    BORDER_DIM= "#1a2030"
    BORDER_LT = "#2a3a55"

def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c

# ─── SYSTEM METRICS ───────────────────────────────────────────────────────
class _SysMetrics:
    def __init__(self):
        self.cpu = 0.0; self.mem = 0.0; self.gpu = -1.0
        self.net_mb = 0.0; self.disk = 0.0
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running:
            try: self._update()
            except: pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        nc = psutil.net_io_counters(); now = time.time()
        dt = now - self._last_net_t
        net = ((nc.bytes_sent - self._last_net.bytes_sent) +
               (nc.bytes_recv - self._last_net.bytes_recv)) / max(dt, 0.1) / 1024 / 1024
        self._last_net = nc; self._last_net_t = now
        gpu = self._get_gpu()
        with self._lock:
            self.cpu = cpu; self.mem = mem; self.gpu = gpu
            self.net_mb = net; self.disk = disk

    def _get_gpu(self) -> float:
        try:
            r = subprocess.run(["nvidia-smi","--query-gpu=utilization.gpu","--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                vals = [float(v.strip()) for v in r.stdout.strip().split('\n') if v.strip()]
                if vals: return sum(vals)/len(vals)
        except: pass
        return -1.0

    def snapshot(self):
        with self._lock:
            return dict(cpu=self.cpu, mem=self.mem, gpu=self.gpu, net=self.net_mb, disk=self.disk)

_metrics = _SysMetrics()


# ─── CAMERA PANEL — Always-On Live Feed ──────────────────────────────────
class CameraPanel(QWidget):
    """
    Right panel mein live camera feed dikhata hai.
    face_watcher se annotated JPEG frames pull karta hai har 200ms.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(262, 186)
        self._px: QPixmap | None = None
        self._name = "Scanning…"
        self._expr = ""
        self._conf = 0.0
        self.setStyleSheet(
            f"background:{C.PANEL2};"
            f"border:1px solid {C.BORDER};"
            f"border-radius:8px;"
        )
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._pull)
        self._tmr.start(200)   # 5 fps display

    def _pull(self):
        try:
            from face_watcher import get_live_frame_jpg, get_identity
            jpg   = get_live_frame_jpg()
            ident = get_identity()
            self._name = ident.get("name", "Scanning…")
            self._expr = ident.get("expression", "")
            self._conf = ident.get("confidence", 0.0)
            if jpg:
                px = QPixmap()
                px.loadFromData(jpg, "JPEG")
                if not px.isNull():
                    self._px = px.scaled(
                        262, 186,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
        except Exception:
            pass
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        if self._px and not self._px.isNull():
            p.drawPixmap(0, 0, self._px)
        else:
            p.fillRect(self.rect(), qcol(C.PANEL2))
            p.setPen(QPen(qcol(C.TEXT_DIM)))
            p.setFont(_SF(8))
            p.drawText(
                QRectF(0, 0, W, H),
                Qt.AlignmentFlag.AlignCenter,
                "📷  Camera initialising…",
            )
            return

        # Bottom info bar (semi-transparent)
        bar_h = 26
        p.fillRect(QRectF(0, H - bar_h, W, bar_h), qcol(C.DARK, 195))

        # Name + confidence
        if self._name == "Boss":
            ncol = C.GREEN
        elif self._name in (NO_FACE_LABEL, "Scanning…"):
            ncol = C.TEXT_DIM
        else:
            ncol = C.YELLOW

        p.setFont(_SF(8, bold=True))
        p.setPen(QPen(qcol(ncol)))
        lbl = self._name + (f"  {self._conf:.0f}%" if self._conf > 0 else "")
        p.drawText(QRectF(6, H - bar_h, W // 2, bar_h),
                   Qt.AlignmentFlag.AlignVCenter, lbl)

        # Expression
        if self._expr and self._expr not in ("No Face",):
            p.setFont(_SF(7))
            p.setPen(QPen(qcol(C.BLUE_LT)))
            p.drawText(
                QRectF(W // 2, H - bar_h, W // 2 - 4, bar_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                self._expr,
            )

# sentinel used in CameraPanel
NO_FACE_LABEL = "No Face"

# ─── HUD CANVAS ───────────────────────────────────────────────────────────
class HudCanvas(QWidget):
    def __init__(self, face_path: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(260, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.muted = False; self.speaking = False; self.state = "INITIALISING"
        self._tick = 0; self._scale = 1.0; self._tgt_scale = 1.0
        self._halo = 55.0; self._tgt_halo = 55.0
        self._last_t = time.time(); self._scan = 0.0; self._scan2 = 180.0
        self._rings = [0.0, 120.0, 240.0]
        self._pulses: list[float] = [0.0, 50.0, 100.0]
        self._blink = True; self._blink_tick = 0
        self._particles: list[list[float]] = []
        self._face_px: QPixmap | None = None
        self._logo_px: QPixmap | None = None
        self._load_face(face_path)
        self._load_logo()
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _load_face(self, path: str):
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(path).convert("RGBA")
            sz = min(img.size); img = img.resize((sz, sz), Image.LANCZOS)
            mk = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz-2, sz-2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO(); img.save(buf, format="PNG")
            px = QPixmap(); px.loadFromData(buf.getvalue())
            self._face_px = px
        except: self._face_px = None

    def _load_logo(self):
        logo_path = BASE_DIR / "myra_logo.png"
        if logo_path.exists():
            px = QPixmap(str(logo_path))
            if not px.isNull():
                self._logo_px = px

    def _step(self):
        self._tick += 1
        now = time.time()
        if now - self._last_t > (0.10 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = random.uniform(1.06, 1.13)
                self._tgt_halo = random.uniform(150, 200)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo = random.uniform(15, 28)
            else:
                self._tgt_scale = random.uniform(1.001, 1.008)
                self._tgt_halo = random.uniform(48, 68)
            self._last_t = now
        sp = 0.38 if self.speaking else 0.15
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp
        speeds = [1.5, -1.0, 2.2] if self.speaking else [0.6, -0.4, 1.0]
        for i, spd in enumerate(speeds):
            self._rings[i] = (self._rings[i] + spd) % 360
        self._scan  = (self._scan  + (3.5 if self.speaking else 1.5)) % 360
        self._scan2 = (self._scan2 + (-2.2 if self.speaking else -0.8)) % 360
        fw = min(self.width(), self.height())
        lim = fw * 0.74
        spd2 = 4.5 if self.speaking else 2.2
        self._pulses = [r + spd2 for r in self._pulses if r + spd2 < lim]
        if len(self._pulses) < 3 and random.random() < (0.09 if self.speaking else 0.03):
            self._pulses.append(0.0)
        if self.speaking and random.random() < 0.3:
            cx, cy = self.width()/2, self.height()/2
            ang = random.uniform(0, 2*math.pi); r_s = fw*0.28
            self._particles.append([
                cx+math.cos(ang)*r_s, cy+math.sin(ang)*r_s,
                math.cos(ang)*random.uniform(1.0, 2.5),
                math.sin(ang)*random.uniform(1.0, 2.5)-0.4, 1.0
            ])
        self._particles = [[p[0]+p[2], p[1]+p[3], p[2]*0.97, p[3]*0.97, p[4]-0.028]
                           for p in self._particles if p[4] > 0]
        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink; self._blink_tick = 0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))
        W, H = self.width(), self.height()
        cx, cy = W/2, H/2; fw = min(W, H)
        # Grid dots
        p.setPen(QPen(qcol("#10121a"), 1))
        for x in range(0, W, 44):
            for y in range(0, H, 44):
                p.drawPoint(x, y)
        r_face = fw * 0.30
        # Blue halo glow rings
        for i in range(12):
            r = r_face * (2.2 - i*0.10)
            frc = 1.0 - i/12
            a = max(0, min(255, int(self._halo * 0.09 * frc)))
            col = qcol(C.BORDER_DIM if self.muted else C.BLUE, a)
            p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))
        # Pulse rings
        for pr in self._pulses:
            a = max(0, int(220*(1.0 - pr/(fw*0.74))))
            col = qcol(C.BORDER if self.muted else C.BLUE_LT, a)
            p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx-pr, cy-pr, pr*2, pr*2))
        # Spinning arc rings
        for idx, (r_frac, w_r, arc_l, gap) in enumerate(
            [(0.47, 3, 110, 75), (0.39, 2, 75, 52), (0.31, 1, 54, 38)]
        ):
            ring_r = fw*r_frac; base = self._rings[idx]
            a_val = max(0, min(255, int(self._halo*(1.0-idx*0.18))))
            col = qcol(C.BORDER if self.muted else C.BLUE, a_val)
            p.setPen(QPen(col, w_r)); p.setBrush(Qt.BrushStyle.NoBrush)
            angle = base
            rect = QRectF(cx-ring_r, cy-ring_r, ring_r*2, ring_r*2)
            while angle < base+360:
                p.drawArc(rect, int(angle*16), int(arc_l*16)); angle += arc_l+gap
        # Scanners
        sr = fw*0.49; sa = min(255, int(self._halo*1.5)); ex = 80 if self.speaking else 46
        p.setPen(QPen(qcol(C.BORDER if self.muted else C.BLUE_LT, sa), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        srect = QRectF(cx-sr, cy-sr, sr*2, sr*2)
        p.drawArc(srect, int(self._scan*16), int(ex*16))
        p.setPen(QPen(qcol(C.BLUE, sa//2), 1.5))
        p.drawArc(srect, int(self._scan2*16), int(ex*16))
        # Tick marks
        t_out, t_in = fw*0.496, fw*0.473
        p.setPen(QPen(qcol(C.BORDER, 130), 1))
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            inn = t_in if deg % 30 == 0 else t_in+6
            p.drawLine(
                QPointF(cx+t_out*math.cos(rad), cy-t_out*math.sin(rad)),
                QPointF(cx+inn*math.cos(rad),   cy-inn*math.sin(rad))
            )
        # Crosshair
        ch_r, gap_h = fw*0.50, fw*0.16
        p.setPen(QPen(qcol(C.BLUE, int(self._halo*0.5)), 1))
        p.drawLine(QPointF(cx-ch_r, cy), QPointF(cx-gap_h, cy))
        p.drawLine(QPointF(cx+gap_h, cy), QPointF(cx+ch_r, cy))
        p.drawLine(QPointF(cx, cy-ch_r), QPointF(cx, cy-gap_h))
        p.drawLine(QPointF(cx, cy+gap_h), QPointF(cx, cy+ch_r))
        # Corner brackets
        bl = 22; bc = qcol(C.BLUE_LT, 200)
        hl, hr = cx-fw//2, cx+fw//2; ht, hb = cy-fw//2, cy+fw//2
        p.setPen(QPen(bc, 2))
        for bx, by, dx, dy in [(hl,ht,1,1),(hr,ht,-1,1),(hl,hb,1,-1),(hr,hb,-1,-1)]:
            p.drawLine(QPointF(bx,by), QPointF(bx+dx*bl,by))
            p.drawLine(QPointF(bx,by), QPointF(bx,by+dy*bl))
        # Face image
        if self._face_px:
            fsz = int(fw*0.60*self._scale)
            scaled = self._face_px.scaled(fsz, fsz,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(int(cx-fsz/2), int(cy-fsz/2), scaled)
        else:
            orb_r = int(fw*0.26*self._scale)
            for i in range(8, 0, -1):
                r2 = int(orb_r*i/8); frc = i/8
                a = max(0, min(255, int(self._halo*1.1*frc)))
                p.setBrush(QBrush(QColor(0, int(60*frc), int(150*frc), a)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(cx-r2, cy-r2, r2*2, r2*2))
            p.setPen(QPen(qcol(C.BLUE_LT, min(255, int(self._halo*2))), 1))
            p.setFont(_SF(13, bold=True))
            p.drawText(QRectF(cx-60, cy-14, 120, 28), Qt.AlignmentFlag.AlignCenter, "M.Y.R.A")
        # Particles
        for pt in self._particles:
            a = max(0, min(255, int(pt[4]*255)))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(qcol(C.BLUE_LT, a)))
            p.drawEllipse(QPointF(pt[0], pt[1]), 2.5, 2.5)
        # Status text
        sy = cy+fw*0.40
        if self.muted:         txt, col = "⊘  MUTED",      qcol(C.TEXT_DIM)
        elif self.speaking:    txt, col = "●  SPEAKING",   qcol(C.GREEN)
        elif self.state=="THINKING":   sym="◈" if self._blink else "◇"; txt,col=f"{sym}  THINKING",  qcol(C.YELLOW)
        elif self.state=="PROCESSING": sym="▷" if self._blink else "▶"; txt,col=f"{sym}  PROCESSING",qcol(C.YELLOW)
        elif self.state=="LISTENING":  sym="●" if self._blink else "○"; txt,col=f"{sym}  LISTENING", qcol(C.GREEN)
        else:                  sym="●" if self._blink else "○"; txt,col=f"{sym}  {self.state}",qcol(C.BLUE)
        p.setPen(QPen(col, 1)); p.setFont(_SF(9, bold=True))
        p.drawText(QRectF(0, sy, W, 26), Qt.AlignmentFlag.AlignCenter, txt)
        # Waveform
        wy = sy+30; N, bw = 36, 8; wx0 = (W-N*bw)/2
        for i in range(N):
            if self.muted:     hgt, cl = 2, qcol(C.TEXT_DIM)
            elif self.speaking: hgt=random.randint(3,22); cl=qcol(C.BLUE_LT) if hgt>12 else qcol(C.BLUE)
            else:              hgt=int(3+2*math.sin(self._tick*0.09+i*0.6)); cl=qcol(C.BORDER)
            p.fillRect(QRectF(wx0+i*bw, wy+22-hgt, bw-1, hgt), cl)


# ─── PROGRESS BAR METRIC ──────────────────────────────────────────────────
class MetricBar(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label = label; self._value = 0.0; self._text = "--"
        self.setFixedHeight(22); self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct)); self._text = text; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setBrush(QBrush(qcol(C.PANEL2))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, W, H), 3, 3)
        bw = int((W-100)*self._value/100)
        bar_col = qcol(C.RED_B) if self._value>85 else qcol(C.YELLOW) if self._value>65 else qcol(C.BLUE)
        p.setBrush(QBrush(qcol(C.BORDER_DIM))); p.drawRoundedRect(QRectF(68, 6, W-104, 10), 3, 3)
        if bw > 0: p.setBrush(QBrush(bar_col)); p.drawRoundedRect(QRectF(68, 6, bw, 10), 3, 3)
        p.setFont(_SF(7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(4, 0, 62, H), Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft, self._label)
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.setFont(_SF(7, bold=True))
        p.drawText(QRectF(W-34, 0, 30, H), Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignRight, self._text)


# ─── LOG WIDGET ───────────────────────────────────────────────────────────
class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(_SF(8))
        self.setStyleSheet(f"""
            QTextEdit{{background:{C.PANEL};color:{C.TEXT};border:1px solid {C.BORDER_DIM};
                       border-radius:6px;padding:6px;}}
            QScrollBar:vertical{{background:{C.BG};width:5px;border:none;}}
            QScrollBar::handle:vertical{{background:{C.BORDER_LT};border-radius:3px;min-height:16px;}}
        """)
        self._queue: list[str] = []; self._typing = False
        self._text = ""; self._pos = 0; self._tag = "sys"
        self._tmr = QTimer(self); self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str): self._sig.emit(text)
    def _enqueue(self, text: str):
        self._queue.append(text)
        if not self._typing: self._next()

    def _next(self):
        if not self._queue: self._typing = False; return
        self._typing = True; self._text = self._queue.pop(0); self._pos = 0
        tl = self._text.lower()
        if   tl.startswith("you:"):  self._tag = "you"
        elif tl.startswith("myra:"): self._tag = "ai"
        elif tl.startswith("file:"): self._tag = "file"
        elif "err" in tl:            self._tag = "err"
        else:                         self._tag = "sys"
        self._tmr.start(5)

    def _step(self):
        if self._pos < len(self._text):
            ch = self._text[self._pos]
            cur = self.textCursor(); fmt = cur.charFormat()
            col = {"you": qcol(C.BLUE_LT), "ai": qcol(C.GREEN), "err": qcol("#ff4444"),
                   "file": qcol(C.YELLOW), "sys": qcol(C.TEXT_MED)}.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End); cur.insertText(ch, fmt)
            self.setTextCursor(cur); self.ensureCursorVisible(); self._pos += 1
        else:
            self._tmr.stop(); cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End); cur.insertText("\n")
            self.setTextCursor(cur); self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)


# ─── QUICK ACTION BUTTON ──────────────────────────────────────────────────
class QuickBtn(QPushButton):
    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(88, 72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon = icon; self._label = label; self._hover = False
        self.setFlat(True)

    def enterEvent(self, e): self._hover = True; self.update()
    def leaveEvent(self, e): self._hover = False; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        bg = qcol(C.PANEL3 if self._hover else C.PANEL2)
        border = qcol(C.BLUE if self._hover else C.BORDER_DIM)
        p.setBrush(QBrush(bg)); p.setPen(QPen(border, 1))
        p.drawRoundedRect(QRectF(1, 1, W-2, H-2), 8, 8)
        p.setFont(QFont("Segoe UI Emoji" if _OS == "Windows" else "Arial", 18))
        p.setPen(QPen(qcol(C.BLUE_LT if self._hover else C.BLUE), 1))
        p.drawText(QRectF(0, 4, W, 36), Qt.AlignmentFlag.AlignCenter, self._icon)
        p.setFont(_SF(7, bold=True))
        p.setPen(QPen(qcol(C.TEXT if self._hover else C.TEXT_MED), 1))
        p.drawText(QRectF(0, 42, W, 22), Qt.AlignmentFlag.AlignCenter, self._label)


# ─── FILE DROP ZONE ───────────────────────────────────────────────────────
class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent); self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(48); self._current_file = None
        self.setStyleSheet(f"""
            QWidget{{background:{C.PANEL2};border:1px dashed {C.BORDER_LT};border-radius:6px;}}
            QWidget:hover{{border:1px dashed {C.BLUE};background:{C.PANEL3};}}
        """)
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 8, 12, 8)
        self._lbl = QLabel("📂  Drop file here or click to browse")
        self._lbl.setFont(_SF(8))
        self._lbl.setStyleSheet(f"color:{C.TEXT_DIM};border:none;background:transparent;")
        lay.addWidget(self._lbl)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file(): self._set_file(path)
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            path, _ = QFileDialog.getOpenFileName(self, "Select file", str(Path.home()), "All Files (*.*)")
            if path: self._set_file(path)
    def _set_file(self, path: str):
        self._current_file = path
        self._lbl.setText(f"📄  {Path(path).name}")
        self._lbl.setStyleSheet(f"color:{C.GREEN};border:none;background:transparent;")
        self.file_selected.emit(path)
    def current_file(self): return self._current_file
    def clear_file(self):
        self._current_file = None
        self._lbl.setText("📂  Drop file or click to browse")
        self._lbl.setStyleSheet(f"color:{C.TEXT_DIM};border:none;background:transparent;")


# ─── SETUP OVERLAY ────────────────────────────────────────────────────────
class SetupOverlay(QWidget):
    done = pyqtSignal(str, str, str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("SetupOverlay")
        self.setStyleSheet(f"#SetupOverlay{{background:rgba(6,6,14,252);border:1px solid {C.BORDER_LT};border-radius:12px;}}")
        detected = {"darwin": "mac", "windows": "windows"}.get(_OS.lower(), "linux")
        self._sel_os = detected
        lay = QVBoxLayout(self); lay.setContentsMargins(32, 28, 32, 28); lay.setSpacing(12)

        def _lbl(txt, sz=9, bold=False, col=C.TEXT, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(_SF(sz, bold=bold))
            w.setStyleSheet(f"color:{col};background:transparent;"); return w

        # Logo
        logo_lbl = QLabel()
        logo_path = BASE_DIR / "myra_logo.png"
        if logo_path.exists():
            px = QPixmap(str(logo_path))
            if not px.isNull():
                logo_lbl.setPixmap(px.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(logo_lbl)

        lay.addWidget(_lbl("Myra 1.0", 16, bold=True, col=C.WHITE))
        lay.addWidget(_lbl("Enter your API keys to activate MYRA.", 9, col=C.TEXT_DIM))

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{C.BORDER};max-height:1px;"); lay.addWidget(sep)

        lay.addWidget(_lbl("Gemini API Key", 8, bold=True, col=C.TEXT_MED, align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit(); self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…"); self._key_input.setFont(_SF(10))
        self._key_input.setFixedHeight(36)
        self._key_input.setStyleSheet(f"QLineEdit{{background:{C.PANEL};color:{C.TEXT};border:1px solid {C.BORDER};border-radius:6px;padding:4px 10px;}} QLineEdit:focus{{border:1px solid {C.BLUE_LT};}}")
        lay.addWidget(self._key_input)

        lay.addWidget(_lbl("OpenRouter API Key", 8, bold=True, col=C.TEXT_MED, align=Qt.AlignmentFlag.AlignLeft))
        self._or_input = QLineEdit(); self._or_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._or_input.setPlaceholderText("sk-or-…"); self._or_input.setFont(_SF(10))
        self._or_input.setFixedHeight(36)
        self._or_input.setStyleSheet(self._key_input.styleSheet())
        lay.addWidget(self._or_input)

        lay.addWidget(_lbl("Operating System", 8, bold=True, col=C.TEXT_MED, align=Qt.AlignmentFlag.AlignLeft))
        os_row = QHBoxLayout(); os_row.setSpacing(6); self._os_btns = {}
        for key, label in [("windows", "Windows"), ("mac", "macOS"), ("linux", "Linux")]:
            btn = QPushButton(label); btn.setFont(_SF(9))
            btn.setFixedHeight(32); btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn); self._os_btns[key] = btn
        lay.addLayout(os_row); self._sel(detected)

        init_btn = QPushButton("Activate Myra 1.0")
        init_btn.setFont(_SF(10, bold=True))
        init_btn.setFixedHeight(42); init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"QPushButton{{background:{C.BLUE};color:{C.WHITE};border:none;border-radius:8px;}} QPushButton:hover{{background:{C.BLUE_LT};}}")
        init_btn.clicked.connect(self._submit); lay.addWidget(init_btn)

        self._err_lbl = _lbl("", 8, col="#ff4444")
        lay.addWidget(self._err_lbl)

    def _sel(self, key: str):
        self._sel_os = key
        for k, btn in self._os_btns.items():
            if k == key:
                btn.setStyleSheet(f"QPushButton{{background:{C.BLUE};color:{C.WHITE};border:none;border-radius:5px;}}")
            else:
                btn.setStyleSheet(f"QPushButton{{background:{C.PANEL};color:{C.TEXT_MED};border:1px solid {C.BORDER};border-radius:5px;}} QPushButton:hover{{color:{C.TEXT};}}")

    def _submit(self):
        key = self._key_input.text().strip()
        or_key = self._or_input.text().strip()
        if not key:
            self._err_lbl.setText("Gemini API key is required.")
            return
        self._err_lbl.setText("")
        self.done.emit(key, or_key, self._sel_os)


# ─── STATUS DOT ───────────────────────────────────────────────────────────
def _dot(color=C.GREEN, size=8):
    lbl = QLabel(); lbl.setFixedSize(size, size)
    lbl.setStyleSheet(f"background:{color};border-radius:{size//2}px;"); return lbl


# ─── MAIN WINDOW ──────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    _log_sig   = pyqtSignal(str)
    _state_sig = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("Myra 1.0 — Neural Core")
        self.setMinimumSize(1100, 680)
        self.resize(1280, 760)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width()-1280)//2, (screen.height()-760)//2)
        self.on_text_command = None; self._muted = False; self._current_file = None

        central = QWidget(); central.setStyleSheet(f"background:{C.BG};"); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(self._build_header())
        body = QHBoxLayout(); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(0)
        body.addWidget(self._build_left_panel(),   stretch=0)
        body.addWidget(self._build_center_panel(), stretch=1)
        body.addWidget(self._build_right_panel(),  stretch=0)
        root.addLayout(body, stretch=1)

        self._clock_tmr  = QTimer(self); self._clock_tmr.timeout.connect(self._tick_clock);   self._clock_tmr.start(1000);  self._tick_clock()
        self._metric_tmr = QTimer(self); self._metric_tmr.timeout.connect(self._update_metrics); self._metric_tmr.start(2000); self._update_metrics()
        self._weather_tmr = QTimer(self); self._weather_tmr.timeout.connect(self._refresh_weather); self._weather_tmr.start(600000)
        self._log_sig.connect(self._log.append_log)
        self._state_sig.connect(self._apply_state)
        self._overlay = None
        self._ready = self._check_config()
        if not self._ready: self._show_setup()
        else: threading.Thread(target=self._refresh_weather, daemon=True).start()
        QShortcut(QKeySequence("F4"),  self).activated.connect(self._toggle_mute)
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_fullscreen)

    def _toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._overlay and self._overlay.isVisible():
            cw = self.centralWidget(); ow, oh = 460, 480
            self._overlay.setGeometry((cw.width()-ow)//2, (cw.height()-oh)//2, ow, oh)

    # ── HEADER ──────────────────────────────────────────────────────────────
    def _build_header(self) -> QWidget:
        w = QWidget(); w.setFixedHeight(56)
        w.setStyleSheet(f"background:{C.DARK};border-bottom:1px solid {C.BORDER};")
        lay = QHBoxLayout(w); lay.setContentsMargins(18, 0, 18, 0); lay.setSpacing(12)

        # Logo + name
        logo_lbl = QLabel()
        logo_path = BASE_DIR / "myra_logo.png"
        if logo_path.exists():
            px = QPixmap(str(logo_path))
            if not px.isNull():
                logo_lbl.setPixmap(px.scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
        logo_lbl.setFixedSize(36, 36)
        lay.addWidget(logo_lbl)

        name_col = QVBoxLayout(); name_col.setSpacing(1)
        t = QLabel("Myra 1.0"); t.setFont(_SF(13, bold=True))
        t.setStyleSheet(f"color:{C.WHITE};background:transparent;")
        s = QLabel("Neural Core Active"); s.setFont(_SF(8))
        s.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;")
        name_col.addWidget(t); name_col.addWidget(s)
        lay.addLayout(name_col)
        lay.addStretch()

        # Center clock
        time_col = QVBoxLayout(); time_col.setSpacing(1); time_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._clock_lbl = QLabel("00:00 PM"); self._clock_lbl.setFont(_SF(15, bold=True))
        self._clock_lbl.setStyleSheet(f"color:{C.WHITE};background:transparent;"); self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._date_lbl = QLabel(""); self._date_lbl.setFont(_SF(8))
        self._date_lbl.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;"); self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_col.addWidget(self._clock_lbl); time_col.addWidget(self._date_lbl)
        lay.addLayout(time_col)
        lay.addStretch()

        # Chat button
        chat_btn = QPushButton("💬  Chat"); chat_btn.setFixedHeight(32)
        chat_btn.setFont(_SF(9)); chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        chat_btn.setStyleSheet(f"QPushButton{{background:{C.PANEL2};color:{C.BLUE_LT};border:1px solid {C.BORDER_LT};border-radius:7px;padding:0 14px;}} QPushButton:hover{{background:{C.PANEL3};border-color:{C.BLUE};}}")
        chat_btn.clicked.connect(self._open_chat); lay.addWidget(chat_btn)

        # Exit button
        exit_btn = QPushButton("✕"); exit_btn.setFixedSize(32, 32)
        exit_btn.setFont(_SF(11)); exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_btn.setToolTip("Exit"); exit_btn.clicked.connect(self.close)
        exit_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{C.TEXT_DIM};border:1px solid {C.BORDER};border-radius:5px;}} QPushButton:hover{{color:#ff4444;border-color:#ff4444;}}")
        lay.addWidget(exit_btn)
        return w

    def _open_chat(self):
        try:
            from chat_window import ChatWindow
            if not hasattr(self, '_chat_win') or not self._chat_win.isVisible():
                self._chat_win = ChatWindow(self)
                self._chat_win.resize(1200, 760)
            self._chat_win.show(); self._chat_win.raise_(); self._chat_win.activateWindow()
        except Exception as e:
            self._log_sig.emit(f"ERR: Chat — {e}")

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%I:%M %p"))
        self._date_lbl.setText(time.strftime("%A, %d %B %Y"))

    # ── LEFT PANEL ──────────────────────────────────────────────────────────
    def _build_left_panel(self) -> QWidget:
        w = QWidget(); w.setFixedWidth(280)
        w.setStyleSheet(f"background:{C.BG2};border-right:1px solid {C.BORDER};")
        lay = QVBoxLayout(w); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(12)

        # Greeting
        hl = QLabel("Hello, Boss 👋"); hl.setFont(_SF(14, bold=True))
        hl.setStyleSheet(f"color:{C.WHITE};background:transparent;"); lay.addWidget(hl)
        hs = QLabel("How can I help you today?"); hs.setFont(_SF(9))
        hs.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;"); lay.addWidget(hs)

        # System Overview
        lay.addWidget(self._section_header("System Overview"))
        so = self._panel(); sol = QVBoxLayout(so); sol.setContentsMargins(12, 10, 12, 10); sol.setSpacing(5)
        self._bar_cpu  = MetricBar("CPU");     sol.addWidget(self._bar_cpu)
        self._bar_mem  = MetricBar("RAM");     sol.addWidget(self._bar_mem)
        self._bar_gpu  = MetricBar("GPU");     sol.addWidget(self._bar_gpu)
        self._bar_disk = MetricBar("Storage"); sol.addWidget(self._bar_disk)
        lay.addWidget(so)

        # System Info
        lay.addWidget(self._section_header("System Info"))
        si = self._panel(); sil = QVBoxLayout(si); sil.setContentsMargins(12, 10, 12, 10); sil.setSpacing(4)
        self._sys_labels = {}
        for key, default in [("OS","Windows 11"),("CPU","Intel CPU"),("RAM","-- GB"),("Uptime","--")]:
            row = QHBoxLayout(); row.setSpacing(4)
            k = QLabel(key); k.setFont(_SF(8)); k.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;"); k.setFixedWidth(54)
            v = QLabel(default); v.setFont(_SF(8, bold=True)); v.setStyleSheet(f"color:{C.TEXT};background:transparent;"); v.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(k); row.addWidget(v, 1); sil.addLayout(row)
            self._sys_labels[key] = v
        lay.addWidget(si)

        # AI Status
        lay.addWidget(self._section_header("AI Status"))
        ai = self._panel(); ail = QVBoxLayout(ai); ail.setContentsMargins(12, 10, 12, 10); ail.setSpacing(5)
        self._status_rows = {}
        for name, status, color in [
            ("Myra AI",    "Online",     C.GREEN),
            ("Gemini API", "Connecting", C.YELLOW),
            ("OpenRouter", "Connecting", C.YELLOW),
            ("Voice",      "Active",     C.GREEN),
        ]:
            row = QHBoxLayout(); row.setSpacing(6)
            nl = QLabel(name); nl.setFont(_SF(8)); nl.setStyleSheet(f"color:{C.TEXT_MED};background:transparent;")
            d = _dot(color); sl = QLabel(status); sl.setFont(_SF(8, bold=True))
            sl.setStyleSheet(f"color:{color};background:transparent;")
            row.addWidget(nl, 1); row.addWidget(d); row.addWidget(sl)
            ail.addLayout(row); self._status_rows[name] = (d, sl)
        lay.addWidget(ai)

        # Conversation History
        lay.addWidget(self._section_header("Recent Chats"))
        self._hist_list = QListWidget()
        self._hist_list.setMaximumHeight(110)
        self._hist_list.setFont(_SF(8))
        self._hist_list.setStyleSheet(f"""
            QListWidget{{background:transparent;border:none;color:{C.TEXT};}}
            QListWidget::item{{padding:5px 4px;border-radius:4px;border-bottom:1px solid {C.BORDER_DIM};}}
            QListWidget::item:hover{{background:{C.PANEL2};}}
            QListWidget::item:selected{{background:{C.PANEL3};}}
        """)
        lay.addWidget(self._hist_list)
        lay.addStretch()
        return w

    # ── CENTER PANEL ────────────────────────────────────────────────────────
    def _build_center_panel(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background:{C.BG};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        self.hud = HudCanvas(str(BASE_DIR / "myra_face.png"))
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self.hud, stretch=1)

        # Chat input bar
        chat_w = QWidget(); chat_w.setFixedHeight(110)
        chat_w.setStyleSheet(f"background:{C.BG2};border-top:1px solid {C.BORDER};")
        cl = QVBoxLayout(chat_w); cl.setContentsMargins(18, 12, 18, 12); cl.setSpacing(8)

        hdr = QLabel("Chat with Myra"); hdr.setFont(_SF(9, bold=True))
        hdr.setStyleSheet(f"color:{C.TEXT_MED};background:transparent;"); cl.addWidget(hdr)

        input_row = QHBoxLayout(); input_row.setSpacing(8)
        self._input = QLineEdit(); self._input.setPlaceholderText("Ask me anything…")
        self._input.setFont(_SF(10)); self._input.setFixedHeight(38)
        self._input.setStyleSheet(f"""
            QLineEdit{{background:{C.PANEL};color:{C.WHITE};border:1px solid {C.BORDER};
                       border-radius:8px;padding:4px 12px;}}
            QLineEdit:focus{{border:1px solid {C.BLUE_LT};}}
        """)
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input)

        send_btn = QPushButton("↑"); send_btn.setFixedSize(38, 38)
        send_btn.setFont(_SF(14, bold=True)); send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet(f"QPushButton{{background:{C.BLUE};color:{C.WHITE};border:none;border-radius:8px;}} QPushButton:hover{{background:{C.BLUE_LT};}}")
        send_btn.clicked.connect(self._send); input_row.addWidget(send_btn)
        cl.addLayout(input_row)

        # Mic toggle
        icon_row = QHBoxLayout(); icon_row.setSpacing(10)
        self._mic_btn = QPushButton("🎤  Mic"); self._mic_btn.setFixedHeight(26)
        self._mic_btn.setFont(_SF(8)); self._mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mic_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{C.TEXT_DIM};border:none;}} QPushButton:hover{{color:{C.BLUE_LT};}}")
        self._mic_btn.clicked.connect(self._toggle_mute); icon_row.addWidget(self._mic_btn)
        icon_row.addStretch(); cl.addLayout(icon_row)
        lay.addWidget(chat_w)
        return w

    # ── RIGHT PANEL ─────────────────────────────────────────────────────────
    def _build_right_panel(self) -> QWidget:
        w = QWidget(); w.setFixedWidth(290)
        w.setStyleSheet(f"background:{C.BG2};border-left:1px solid {C.BORDER};")
        lay = QVBoxLayout(w); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(12)

        # ── MYRA Vision — Always-On Camera ────────────────────────────
        lay.addWidget(self._section_header("MYRA Vision  👁"))
        self._cam_panel = CameraPanel()
        _cw = QHBoxLayout(); _cw.addWidget(self._cam_panel)
        lay.addLayout(_cw)

        # Identity status row below camera
        _ir = QHBoxLayout(); _ir.setSpacing(6)
        self._face_name_lbl = QLabel("Scanning…")
        self._face_name_lbl.setFont(_SF(8, bold=True))
        self._face_name_lbl.setStyleSheet(f"color:{C.BLUE_LT};background:transparent;")
        self._face_expr_lbl = QLabel("")
        self._face_expr_lbl.setFont(_SF(8))
        self._face_expr_lbl.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;")
        self._face_expr_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        _ir.addWidget(self._face_name_lbl); _ir.addWidget(self._face_expr_lbl, 1)
        lay.addLayout(_ir)

        # refresh identity labels every 600ms
        self._face_lbl_tmr = QTimer(self)
        self._face_lbl_tmr.timeout.connect(self._refresh_face_labels)
        self._face_lbl_tmr.start(600)

        # Voice status
        lay.addWidget(self._section_header("Voice Assistant"))
        va = self._panel(); val = QVBoxLayout(va); val.setContentsMargins(12, 10, 12, 10); val.setSpacing(6)
        self._wave_lbl = QLabel("▁▂▃▄▅▃▂▁  Standby"); self._wave_lbl.setFont(_SF(9))
        self._wave_lbl.setStyleSheet(f"color:{C.BLUE_LT};background:transparent;"); self._wave_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.addWidget(self._wave_lbl)
        self._voice_status = QLabel("Listening…"); self._voice_status.setFont(_SF(10, bold=True))
        self._voice_status.setStyleSheet(f"color:{C.GREEN};background:transparent;"); val.addWidget(self._voice_status)
        lay.addWidget(va)

        # Weather
        lay.addWidget(self._section_header("Weather"))
        ww = self._panel(); wwl = QVBoxLayout(ww); wwl.setContentsMargins(12, 10, 12, 10); wwl.setSpacing(4)
        w_row = QHBoxLayout()
        self._weather_icon = QLabel("⛅"); self._weather_icon.setFont(QFont("Segoe UI Emoji" if _OS == "Windows" else "Arial", 28))
        self._weather_icon.setStyleSheet("background:transparent;"); w_row.addWidget(self._weather_icon)
        w_info = QVBoxLayout(); w_info.setSpacing(2)
        self._weather_temp = QLabel("--°C"); self._weather_temp.setFont(_SF(20, bold=True))
        self._weather_temp.setStyleSheet(f"color:{C.WHITE};background:transparent;"); w_info.addWidget(self._weather_temp)
        self._weather_city = QLabel("Indore, Madhya Pradesh"); self._weather_city.setFont(_SF(8))
        self._weather_city.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;"); w_info.addWidget(self._weather_city)
        self._weather_desc = QLabel("Fetching…"); self._weather_desc.setFont(_SF(8))
        self._weather_desc.setStyleSheet(f"color:{C.TEXT_MED};background:transparent;"); w_info.addWidget(self._weather_desc)
        w_row.addLayout(w_info); wwl.addLayout(w_row)
        lay.addWidget(ww)

        # Quick Actions
        lay.addWidget(self._section_header("Quick Actions"))
        qa = self._panel(); qal = QVBoxLayout(qa); qal.setContentsMargins(8, 8, 8, 8); qal.setSpacing(6)
        actions_def = [
            ("🌐","Browser",  "open_browser", "browser"),
            ("📁","Files",    "file_controller","explorer"),
            ("📷","Screenshot","computer_settings","screenshot"),
            ("🔒","Lock PC",  "computer_settings","lock"),
            ("⏻","Shutdown",  "computer_settings","shutdown"),
            ("🔄","Restart",  "computer_settings","restart"),
        ]
        for row_start in range(0, len(actions_def), 3):
            row = QHBoxLayout(); row.setSpacing(6)
            for icon, label, tool, action in actions_def[row_start:row_start+3]:
                btn = QuickBtn(icon, label)
                btn.clicked.connect(lambda _, t=tool, a=action, lb=label: self._quick_action(t, a, lb))
                row.addWidget(btn)
            qal.addLayout(row)
        lay.addWidget(qa)

        # Activity Log
        lay.addWidget(self._section_header("Activity Log"))
        self._log = LogWidget(); self._log.setMaximumHeight(76)
        lay.addWidget(self._log)

        # File drop
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)
        lay.addStretch()
        return w

    # ── FACE LABEL REFRESH ──────────────────────────────────────────────────
    def _refresh_face_labels(self):
        try:
            from face_watcher import get_identity
            s    = get_identity()
            name = s.get("name", "Scanning…")
            expr = s.get("expression", "")
            conf = s.get("confidence", 0.0)
            col  = (C.GREEN  if name == "Boss"
                    else C.YELLOW if name not in ("No Face", "Unknown", "Scanning…")
                    else C.TEXT_DIM)
            lbl = name + (f"  {conf:.0f}%" if conf > 0 else "")
            self._face_name_lbl.setText(lbl)
            self._face_name_lbl.setStyleSheet(
                f"color:{col};background:transparent;font-weight:bold;"
            )
            self._face_expr_lbl.setText(
                expr if expr not in ("No Face", "") else ""
            )
        except Exception:
            pass

    # ── HELPERS ─────────────────────────────────────────────────────────────
    def _section_header(self, text: str) -> QLabel:
        l = QLabel(text); l.setFont(_SF(8, bold=True))
        l.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;letter-spacing:0.5px;")
        return l

    def _panel(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{C.PANEL};border:1px solid {C.BORDER};border-radius:8px;")
        return w

    # ── QUICK ACTIONS ───────────────────────────────────────────────────────
    def _quick_action(self, tool: str, action: str, label: str):
        self._log.append_log(f"SYS: {label}…")
        def run():
            try:
                if tool == "open_browser":
                    import webbrowser; webbrowser.open("https://google.com")
                elif tool == "computer_settings":
                    from actions.computer_settings import computer_settings
                    computer_settings({"action": action, "description": label}, player=self)
                elif tool == "file_controller":
                    if _OS == "Windows": subprocess.Popen(["explorer.exe"])
                    else: subprocess.Popen(["nautilus"])
                self._log_sig.emit(f"SYS: {label} done.")
            except Exception as e:
                self._log_sig.emit(f"ERR: {label} — {str(e)[:50]}")
        threading.Thread(target=run, daemon=True).start()

    # ── WEATHER ─────────────────────────────────────────────────────────────
    def _refresh_weather(self):
        try:
            cfg = {}
            if API_FILE.exists(): cfg = json.loads(API_FILE.read_text(encoding="utf-8"))
            key = cfg.get("gemini_api_key", "")
            if not key: self._update_weather_ui("--°C","Indore, MP","No API key","🌐"); return
            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-2.5-flash",
                generation_config={"response_mime_type": "application/json"})
            resp = model.generate_content(
                'Give current weather for Indore, Madhya Pradesh, India. '
                'Return JSON: {"temp_c": 31, "description": "Partly Cloudy", "icon": "⛅", "city": "Indore, Madhya Pradesh"}')
            data = json.loads(resp.text)
            self._update_weather_ui(
                f"{data.get('temp_c','--')}°C",
                data.get('city','Indore, MP'),
                data.get('description','--'),
                data.get('icon','🌡')
            )
        except Exception:
            self._update_weather_ui("--°C","Indore, MP","—","⛅")

    def _update_weather_ui(self, temp, city, desc, icon):
        def _do():
            self._weather_temp.setText(temp)
            self._weather_city.setText(city)
            self._weather_desc.setText(desc)
            self._weather_icon.setText(icon)
        QTimer.singleShot(0, _do)

    # ── METRICS ─────────────────────────────────────────────────────────────
    def _update_metrics(self):
        snap = _metrics.snapshot()
        cpu = snap["cpu"];  self._bar_cpu.set_value(cpu,  f"{cpu:.0f}%")
        mem = snap["mem"];  self._bar_mem.set_value(mem,  f"{mem:.0f}%")
        gpu = snap["gpu"]
        if gpu >= 0: self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else:        self._bar_gpu.set_value(0,   "N/A")
        disk = snap["disk"]; self._bar_disk.set_value(disk, f"{disk:.0f}%")
        try:
            import platform as pl
            self._sys_labels["OS"].setText(f"{pl.system()} {pl.release()}"[:20])
            self._sys_labels["CPU"].setText(pl.processor()[:22] if pl.processor() else "Unknown")
            vm = psutil.virtual_memory()
            self._sys_labels["RAM"].setText(f"{vm.total/1024**3:.0f} GB")
            el = time.time() - psutil.boot_time()
            self._sys_labels["Uptime"].setText(f"{int(el//3600)}h {int((el%3600)//60)}m")
        except: pass

    # ── MUTE / STATE ────────────────────────────────────────────────────────
    def _toggle_mute(self):
        self._muted = not self._muted; self.hud.muted = self._muted
        if self._muted:
            self._apply_state("MUTED"); self._log.append_log("SYS: Microphone muted.")
            self._voice_status.setText("Muted"); self._voice_status.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;")
            self._mic_btn.setText("🔇  Unmute")
        else:
            self._apply_state("LISTENING"); self._log.append_log("SYS: Microphone active.")
            self._voice_status.setText("Listening…"); self._voice_status.setStyleSheet(f"color:{C.GREEN};background:transparent;")
            self._mic_btn.setText("🎤  Mic")

    def _apply_state(self, state: str):
        self.hud.state = state; self.hud.speaking = (state == "SPEAKING")
        if state == "SPEAKING":
            self._voice_status.setText("MYRA speaking…"); self._voice_status.setStyleSheet(f"color:{C.GREEN};background:transparent;")
            self._wave_lbl.setText("▅▇█▇▅▃▅▇█▇▅  Speaking")
        elif state == "LISTENING":
            self._voice_status.setText("Listening…"); self._voice_status.setStyleSheet(f"color:{C.GREEN};background:transparent;")
            self._wave_lbl.setText("▁▂▃▄▅▃▂▁  Listening")
        elif state == "THINKING":
            self._voice_status.setText("Thinking…"); self._voice_status.setStyleSheet(f"color:{C.YELLOW};background:transparent;")
        elif state == "MUTED":
            self._voice_status.setText("Muted"); self._voice_status.setStyleSheet(f"color:{C.TEXT_DIM};background:transparent;")

    # ── SEND ────────────────────────────────────────────────────────────────
    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear(); self._log.append_log(f"You: {txt}")
        self._hist_list.insertItem(0, f"You: {txt[:32]}")
        if self._hist_list.count() > 20: self._hist_list.takeItem(20)
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _on_file_selected(self, path: str):
        self._current_file = path; p = Path(path)
        self._log.append_log(f"FILE: {p.name} loaded")
        if self.on_text_command:
            msg = f"[FILE_UPLOADED] path={path} | name={p.name} | Briefly tell the user the file '{p.name}' has been loaded and ask what to do with it."
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    # ── CONFIG ──────────────────────────────────────────────────────────────
    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key", "").strip())
        except: return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget(); ow, oh = 460, 500
        ov.setGeometry((cw.width()-ow)//2, (cw.height()-oh)//2, ow, oh)
        ov.done.connect(self._on_setup_done); ov.show(); self._overlay = ov

    def _on_setup_done(self, key: str, or_key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(json.dumps(
            {"gemini_api_key": key, "openrouter_api_key": or_key, "os_system": os_name}, indent=4),
            encoding="utf-8")
        self._ready = True
        if self._overlay: self._overlay.hide(); self._overlay = None
        self._apply_state("LISTENING")
        self._log.append_log(f"SYS: Myra 1.0 online. OS={os_name.upper()}.")
        for name in ["Gemini API", "OpenRouter"]:
            if name in self._status_rows:
                d, sl = self._status_rows[name]
                d.setStyleSheet(f"background:{C.GREEN};border-radius:4px;")
                sl.setText("Connected"); sl.setStyleSheet(f"color:{C.GREEN};background:transparent;")
        threading.Thread(target=self._refresh_weather, daemon=True).start()

    # ── PUBLIC API ───────────────────────────────────────────────────────────
    def write_log(self, text: str): self._log_sig.emit(text)
    def set_state(self, state: str): self._state_sig.emit(state)


# ─── SHIM CLASSES ─────────────────────────────────────────────────────────
class _RootShim:
    def __init__(self, app): self._app = app
    def mainloop(self): self._app.exec()
    def protocol(self, *_): pass


class MYRAui:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self): return self._win._muted
    @muted.setter
    def muted(self, v):
        if v != self._win._muted: self._win._toggle_mute()

    @property
    def current_file(self): return self._win._drop_zone.current_file()
    @property
    def on_text_command(self): return self._win.on_text_command
    @on_text_command.setter
    def on_text_command(self, cb): self._win.on_text_command = cb

    def set_state(self, state: str): self._win._state_sig.emit(state)
    def write_log(self, text: str):  self._win._log_sig.emit(text)
    def wait_for_api_key(self):
        while not self._win._ready: time.sleep(0.1)
    def start_speaking(self): self.set_state("SPEAKING")
    def stop_speaking(self):
        if not self.muted: self.set_state("LISTENING")

# Backward compat aliases
JarvisUI = MYRAui
MYRAUI   = MYRAui
