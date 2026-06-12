from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QScrollArea,
    QFrame,
    QListWidget,
    QMainWindow,
    QSizePolicy,
)

# =========================================================
# PATHS
# =========================================================

def _base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


BASE_DIR = _base_dir()

CHAT_HISTORY_PATH = BASE_DIR / "data" / "chat_history.json"
API_FILE = BASE_DIR / "config" / "api_keys.json"

# =========================================================
# COLORS
# =========================================================

CC = {
    "bg": "#0f0f11",
    "sidebar": "#17181c",
    "sidebar2": "#1e2025",
    "chat_bg": "#0f0f11",
    "user": "#2b2d31",
    "assistant": "#1e1f24",
    "border": "#2f3136",
    "text": "#ececf1",
    "muted": "#8e8ea0",
    "accent": "#10a37f",
    "hover": "#2a2b32",
}

# =========================================================
# HELPERS
# =========================================================

def _load_api_key():
    try:
        with open(API_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("gemini_api_key", "")
    except:
        return ""


# =========================================================
# AI THREAD
# =========================================================

class ChatWorker(QThread):

    chunk_ready = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, messages):
        super().__init__()
        self.messages = messages

    def run(self):

        key = _load_api_key()

        if not key:
            self.error.emit("No Gemini API key found.")
            return

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=key)

            contents = []

            for msg in self.messages:

                role = "user" if msg["role"] == "user" else "model"

                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part(text=msg["content"])]
                    )
                )

            full = ""

            stream = client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=contents,
            )

            for chunk in stream:

                text = chunk.text or ""

                if text:
                    full += text
                    self.chunk_ready.emit(text)

            self.finished.emit(full)

        except Exception as e:
            self.error.emit(str(e))


# =========================================================
# CHAT BUBBLE
# =========================================================

class ChatBubble(QFrame):

    def __init__(self, text, user=False):

        super().__init__()

        self.full_text = text
        self.user = user

        self.setMaximumWidth(850)

        self.setStyleSheet(f"""
            QFrame {{
                background: {'#2b2d31' if user else '#1e1f24'};
                border: 1px solid {CC['border']};
                border-radius: 16px;
            }}
        """)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(16, 14, 16, 14)

        name = QLabel("You" if user else "MYRA AI")

        name.setFont(QFont("Segoe UI", 8))

        name.setStyleSheet(f"color:{CC['muted']};")

        layout.addWidget(name)

        self.text = QTextEdit()

        self.text.setReadOnly(True)

        self.text.setFrameStyle(0)

        self.text.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.text.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.text.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        self.text.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                border: none;
                color: {CC['text']};
                font-size: 14px;
                padding: 0px;
            }}
        """)

        self.text.document().setTextWidth(760)

        self.text.setHtml(self.render(text))

        self.resize_bubble()

        layout.addWidget(self.text)

    def render(self, text):

        html = text

        html = re.sub(
            r'```(\w*)\n?(.*?)```',
            r'<pre style="background:#111;padding:12px;'
            r'border-radius:10px;color:#10a37f;'
            r'font-family:Consolas;">\2</pre>',
            html,
            flags=re.DOTALL
        )

        html = re.sub(
            r'\*\*(.*?)\*\*',
            r'<b>\1</b>',
            html
        )

        html = re.sub(
            r'`(.*?)`',
            r'<code style="background:#222;padding:2px 6px;'
            r'border-radius:6px;">\1</code>',
            html
        )

        html = html.replace("\n", "<br>")

        return html

    def resize_bubble(self):

        h = int(self.text.document().size().height()) + 12

        self.text.setFixedHeight(max(40, h))

    def append_text(self, chunk):

        self.full_text += chunk

        self.text.setHtml(self.render(self.full_text))

        self.resize_bubble()

    def set_text(self, txt):

        self.full_text = txt

        self.text.setHtml(self.render(txt))

        self.resize_bubble()


# =========================================================
# MAIN WINDOW
# =========================================================

class ChatWindow(QMainWindow):

    def __init__(self, parent=None):

        super().__init__(parent)

        self.worker = None
        self.ai_bubble = None

        self.setWindowTitle("MYRA AI")

        self.resize(1450, 900)

        central = QWidget()

        self.setCentralWidget(central)

        root = QHBoxLayout(central)

        root.setContentsMargins(0, 0, 0, 0)

        root.setSpacing(0)

        # =====================================================
        # SIDEBAR
        # =====================================================

        sidebar = QFrame()

        sidebar.setFixedWidth(260)

        sidebar.setStyleSheet(f"""
            background:{CC['sidebar']};
            border-right:1px solid {CC['border']};
        """)

        s_layout = QVBoxLayout(sidebar)

        title = QLabel("MYRA AI")

        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))

        title.setStyleSheet(f"color:{CC['text']};")

        s_layout.addWidget(title)

        new_chat = QPushButton("+ New Chat")

        new_chat.setStyleSheet(f"""
            QPushButton {{
                background:{CC['sidebar2']};
                color:white;
                border:none;
                border-radius:10px;
                padding:12px;
                text-align:left;
            }}

            QPushButton:hover {{
                background:{CC['hover']};
            }}
        """)

        new_chat.clicked.connect(self.new_chat)

        s_layout.addWidget(new_chat)

        self.history = QListWidget()

        self.history.setStyleSheet(f"""
            QListWidget {{
                background:transparent;
                border:none;
                color:white;
            }}

            QListWidget::item {{
                padding:10px;
                border-radius:8px;
            }}

            QListWidget::item:hover {{
                background:{CC['hover']};
            }}
        """)

        s_layout.addWidget(self.history)

        root.addWidget(sidebar)

        # =====================================================
        # CHAT AREA
        # =====================================================

        chat_frame = QFrame()

        chat_frame.setStyleSheet(f"""
            background:{CC['chat_bg']};
        """)

        chat_layout = QVBoxLayout(chat_frame)

        chat_layout.setContentsMargins(0, 0, 0, 0)

        chat_layout.setSpacing(0)

        # TOP BAR

        top = QFrame()

        top.setFixedHeight(55)

        top.setStyleSheet(f"""
            background:{CC['chat_bg']};
            border-bottom:1px solid {CC['border']};
        """)

        top_layout = QHBoxLayout(top)

        top_title = QLabel("MYRA AI")

        top_title.setStyleSheet("""
            color:white;
            font-size:16px;
        """)

        top_layout.addWidget(top_title)

        top_layout.addStretch()

        chat_layout.addWidget(top)

        # SCROLL AREA

        self.scroll = QScrollArea()

        self.scroll.setWidgetResizable(True)

        self.scroll.setStyleSheet("""
            QScrollArea {
                border:none;
            }
        """)

        self.container = QWidget()

        self.messages_layout = QVBoxLayout(self.container)

        self.messages_layout.setContentsMargins(30, 30, 30, 30)

        self.messages_layout.setSpacing(16)

        self.messages_layout.addStretch()

        self.scroll.setWidget(self.container)

        chat_layout.addWidget(self.scroll)

        # INPUT BAR

        bottom = QFrame()

        bottom.setFixedHeight(120)

        bottom.setStyleSheet(f"""
            background:{CC['chat_bg']};
            border-top:1px solid {CC['border']};
        """)

        b_layout = QVBoxLayout(bottom)

        input_frame = QFrame()

        input_frame.setStyleSheet(f"""
            background:{CC['assistant']};
            border:1px solid {CC['border']};
            border-radius:14px;
        """)

        input_layout = QHBoxLayout(input_frame)

        self.input = QTextEdit()

        self.input.setPlaceholderText("Message MYRA AI...")

        self.input.setFixedHeight(50)

        self.input.setStyleSheet(f"""
            QTextEdit {{
                background:transparent;
                border:none;
                color:white;
                padding:12px;
                font-size:15px;
            }}
        """)

        input_layout.addWidget(self.input)

        send = QPushButton("↑")

        send.setFixedSize(42, 42)

        send.setStyleSheet(f"""
            QPushButton {{
                background:{CC['accent']};
                color:white;
                border:none;
                border-radius:10px;
                font-size:20px;
            }}

            QPushButton:hover {{
                background:#0dbb90;
            }}
        """)

        send.clicked.connect(self.send_message)

        input_layout.addWidget(send)

        b_layout.addWidget(input_frame)

        chat_layout.addWidget(bottom)

        root.addWidget(chat_frame)

    # =====================================================
    # SEND MESSAGE
    # =====================================================

    def send_message(self):

        text = self.input.toPlainText().strip()

        if not text:
            return

        if self.worker:
            return

        self.input.clear()

        user_bubble = ChatBubble(text, True)

        self.messages_layout.insertWidget(
            self.messages_layout.count() - 1,
            user_bubble,
            alignment=Qt.AlignmentFlag.AlignRight
        )

        self.ai_bubble = ChatBubble("Thinking...", False)

        self.messages_layout.insertWidget(
            self.messages_layout.count() - 1,
            self.ai_bubble,
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        self.scroll_bottom()

        messages = [
            {
                "role": "user",
                "content": text
            }
        ]

        self.worker = ChatWorker(messages)

        self.worker.chunk_ready.connect(self.on_chunk)

        self.worker.finished.connect(self.on_done)

        self.worker.error.connect(self.on_error)

        self.worker.start()

    # =====================================================
    # STREAMING
    # =====================================================

    def on_chunk(self, chunk):

        if not self.ai_bubble:
            return

        if self.ai_bubble.full_text == "Thinking...":
            self.ai_bubble.set_text(chunk)
        else:
            self.ai_bubble.append_text(chunk)

        self.scroll_bottom()

    def on_done(self, text):

        self.worker = None

    def on_error(self, err):

        if self.ai_bubble:
            self.ai_bubble.set_text(f"Error:\n{err}")

        self.worker = None

    # =====================================================
    # UTILITIES
    # =====================================================

    def scroll_bottom(self):

        QTimer.singleShot(
            50,
            lambda: self.scroll.verticalScrollBar().setValue(
                self.scroll.verticalScrollBar().maximum()
            )
        )

    def new_chat(self):

        while self.messages_layout.count() > 1:

            item = self.messages_layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()