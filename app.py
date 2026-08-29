import os
import sys
import re
import json
import time
import winreg
import asyncio
import threading
import numpy as np
import sounddevice as sd
from dotenv import load_dotenv

from pynput import keyboard
from pynput.keyboard import Controller, Key, GlobalHotKeys

from google import genai
from google.genai import types

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint, QPointF, QRectF
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QLineEdit, QFrame, QCheckBox, QStackedWidget, QScrollArea
)
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, 
    QConicalGradient, QLinearGradient, QRadialGradient, QPainterPath, QPixmap
)

from version import __version__, __app_name__

# ==========================================================
# 1. WINDOWS REGISTRY STARTUP MANAGER
# ==========================================================
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = __app_name__

def set_windows_startup(enable=True):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            if getattr(sys, 'frozen', False):
                exe_path = f'"{sys.executable}"'
            else:
                exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
            print("🚀 [Windows Startup Enabled]")
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
                print("🛑 [Windows Startup Disabled]")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Registry Error: {e}")
        return False

def is_windows_startup_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

# ==========================================================
# 2. CONFIGURATION MANAGER
# ==========================================================
# Base Directory सेट करें (ताकि .exe बनने पर config.json हमेशा exe के बगल में मिले)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
load_dotenv(os.path.join(BASE_DIR, ".env"))

def load_config():
    default_config = {
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "hotkey_pynput": "<alt>+v",
        "hotkey_display": "Alt + V",
        "start_with_windows": is_windows_startup_enabled()
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception:
            pass
    return default_config

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Config Save Error: {e}")
        return False

current_config = load_config()
MODEL_ID = "gemini-3.5-transcribe-live"
keyboard_controller = Controller()

# ==========================================================
# 3. SIGNAL BRIDGE
# ==========================================================
class AppSignals(QObject):
    toggle_ui = pyqtSignal()
    live_text_received = pyqtSignal(str)
    set_processing_ui = pyqtSignal(bool)
    set_paused_ui = pyqtSignal(bool)
    hide_ui = pyqtSignal()
    open_settings = pyqtSignal()
    config_updated = pyqtSignal()

signals = AppSignals()

# ==========================================================
# 4. STRICT "VAANI" VOICE COMMAND DISPATCHER
# ==========================================================
def process_voice_input_and_type(text):
    if not text or not text.strip():
        return
    
    raw_text = text.strip()
    
    # Normalize text for exact regex phrase detection
    normalized = re.sub(r'[^\w\s]', '', raw_text.lower()).strip()
    for v in ["vani", "wani", "vanni", "vaanee", "funny", "वाणी", "वानी"]:
        normalized = re.sub(rf'\b{v}\b', 'vaani', normalized)

    # 1. COMMAND: VAANI DELETE ALL
    if any(re.search(rf'\b{p}\b', normalized) for p in [
        "vaani delete all", "vaani clear all", "vaani delete everything",
        "vaani sab delete", "vaani sab mita do", "vaani sab saaf"
    ]):
        print("⚡ [Voice Command Executed]: VAANI DELETE ALL", flush=True)
        try:
            with keyboard_controller.pressed(Key.ctrl):
                keyboard_controller.tap('a')
            time.sleep(0.03)
            keyboard_controller.tap(Key.backspace)
        except Exception as e:
            print(f"Command Error: {e}")
        return

    # 2. COMMAND: VAANI UNDO / DELETE LAST
    if any(re.search(rf'\b{p}\b', normalized) for p in [
        "vaani delete last", "vaani undo", "vaani undo that", "vaani pichla hatao"
    ]):
        print("⚡ [Voice Command Executed]: VAANI UNDO", flush=True)
        try:
            with keyboard_controller.pressed(Key.ctrl):
                keyboard_controller.tap('z')
        except Exception as e:
            print(f"Command Error: {e}")
        return

    # 3. COMMAND: VAANI DELETE WORD
    if any(re.search(rf'\b{p}\b', normalized) for p in [
        "vaani delete that", "vaani delete word", "vaani delete", "vaani erase that", "vaani ek word delete"
    ]):
        print("⚡ [Voice Command Executed]: VAANI DELETE WORD", flush=True)
        try:
            with keyboard_controller.pressed(Key.ctrl):
                keyboard_controller.tap(Key.backspace)
        except Exception as e:
            print(f"Command Error: {e}")
        return

    # 4. COMMAND: VAANI PAUSE
    if any(re.search(rf'\b{p}\b', normalized) for p in [
        "vaani pause", "vaani stop listening", "vaani ruk jao", "vaani pause karo"
    ]):
        print("⚡ [Voice Command Executed]: VAANI PAUSE", flush=True)
        manager.set_paused(True)
        return

    # 5. COMMAND: VAANI RESUME
    if any(re.search(rf'\b{p}\b', normalized) for p in [
        "vaani resume", "vaani start listening", "vaani chalu karo", "vaani continue"
    ]):
        print("⚡ [Voice Command Executed]: VAANI RESUME", flush=True)
        manager.set_paused(False)
        return

    # 6. COMMAND: VAANI NEW LINE
    if any(re.search(rf'\b{p}\b', normalized) for p in [
        "vaani new line", "vaani next line", "vaani enter", "vaani line change", "vaani agli line"
    ]):
        print("⚡ [Voice Command Executed]: VAANI NEW LINE", flush=True)
        try:
            keyboard_controller.tap(Key.enter)
        except Exception as e:
            print(f"Command Error: {e}")
        return

    # 7. COMMAND: VAANI ADD SPACE
    if any(re.search(rf'\b{p}\b', normalized) for p in [
        "vaani add space", "vaani space", "vaani ek space"
    ]):
        print("⚡ [Voice Command Executed]: VAANI ADD SPACE", flush=True)
        try:
            keyboard_controller.tap(Key.space)
        except Exception as e:
            print(f"Command Error: {e}")
        return

    # REGULAR DICTATION
    if not manager.is_paused:
        formatted = raw_text if raw_text.endswith(" ") else raw_text + " "
        print(f"👉 [VaaniType]: {formatted}", flush=True)
        try:
            keyboard_controller.type(formatted)
        except Exception as e:
            print(f"Typing Error: {e}")

# ==========================================================
# 5. LIVE TRANSCRIPTION MANAGER (With Resilient Auto-Reconnect)
# ==========================================================
class LiveTranscriptionManager:
    def __init__(self):
        self.sample_rate = 16000
        self.block_size = 1600
        self.state = "IDLE"
        self.is_paused = False
        self.current_amplitude = 0.05
        self.loop = None
        self.audio_queue = None
        self.session = None

    def get_client(self):
        api_key = current_config.get("api_key", "").strip()
        if not api_key:
            return None
        return genai.Client(api_key=api_key)

    def start_session(self):
        if self.state in ["LISTENING", "FINALIZING"]:
            return
        
        api_key = current_config.get("api_key", "").strip()
        if not api_key:
            print("\n❌ API Key missing! Opening Settings...")
            signals.open_settings.emit()
            signals.hide_ui.emit()
            return

        self.state = "LISTENING"
        self.is_paused = False
        self.current_amplitude = 0.05
        signals.set_processing_ui.emit(False)
        signals.set_paused_ui.emit(False)
        print("\n🎤 [VaaniType Active... Speak naturally or say 'Vaani' commands]")
        threading.Thread(target=self._run_async_loop, daemon=True).start()

    def toggle_pause(self):
        self.set_paused(not self.is_paused)

    def set_paused(self, paused):
        self.is_paused = paused
        signals.set_paused_ui.emit(self.is_paused)
        if self.is_paused:
            self.current_amplitude = 0.0
            print("⏸️ [VaaniType Paused - Standby]")
        else:
            self.current_amplitude = 0.05
            print("▶️ [VaaniType Resumed - Listening Active]")

    def finish_session(self):
        if self.state != "LISTENING":
            return
        self.state = "FINALIZING"
        self.is_paused = False
        self.current_amplitude = 0.05
        signals.set_processing_ui.emit(True)
        print("⏳ [Submitting & processing last words...]")

    def cancel_session(self):
        self.state = "CANCELLED"
        self.is_paused = False
        self.current_amplitude = 0.05
        signals.hide_ui.emit()
        print("✕ [Cancelled]")

    def _run_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.audio_queue = asyncio.Queue()
        try:
            self.loop.run_until_complete(self._live_supervisor())
        except Exception as e:
            print(f"Session info: {e}")
        finally:
            self.state = "IDLE"

    def _mic_callback(self, indata, frames, time_info, status):
        if self.state != "LISTENING":
            return
        
        if self.is_paused:
            self.current_amplitude = 0.0
            return
        
        try:
            audio_float = indata.astype(np.float32) / 32768.0
            rms = np.sqrt(max(0.0, float(np.mean(audio_float**2))))
            if not np.isnan(rms) and not np.isinf(rms):
                self.current_amplitude = float(np.clip(rms * 14.0, 0.05, 1.0))
        except Exception:
            self.current_amplitude = 0.05
        
        if self.loop and self.audio_queue and self.loop.is_running():
            raw_bytes = indata.tobytes()
            self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, raw_bytes)

    async def _send_audio(self, session):
        while self.state == "LISTENING":
            try:
                data = await asyncio.wait_for(self.audio_queue.get(), timeout=0.5)
                if not self.is_paused and data:
                    await session.send_realtime_input(
                        audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000")
                    )
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    async def _receive_transcripts(self, session):
        try:
            async for response in session.receive():
                if self.state == "CANCELLED":
                    break

                text_chunk = ""

                if getattr(response, 'text', None):
                    text_chunk = response.text
                elif getattr(response, 'server_content', None):
                    sc = response.server_content
                    final = getattr(sc, 'input_transcription', None)
                    if final and getattr(final, 'text', None):
                        text_chunk = final.text
                    elif getattr(sc, 'model_turn', None):
                        for part in getattr(sc.model_turn, 'parts', []):
                            if getattr(part, 'text', None):
                                text_chunk += part.text

                if text_chunk:
                    clean = text_chunk.strip()
                    if clean:
                        signals.live_text_received.emit(clean)

        except Exception:
            pass

    async def _live_supervisor(self):
        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='int16', blocksize=self.block_size, callback=self._mic_callback):
            while self.state in ["LISTENING", "FINALIZING"]:
                client = self.get_client()
                if not client:
                    break

                config = types.LiveConnectConfig(
                    response_modalities=["TEXT"],
                    input_audio_transcription=types.AudioTranscriptionConfig(
                        language_codes=[],
                        mode="SMART"
                    )
                )

                try:
                    async with client.aio.live.connect(model=MODEL_ID, config=config) as session:
                        self.session = session
                        print("⚡ [Connected to Gemini 3.5 Transcribe Live!]", flush=True)

                        send_task = asyncio.create_task(self._send_audio(session))
                        recv_task = asyncio.create_task(self._receive_transcripts(session))

                        while self.state == "LISTENING":
                            if send_task.done() or recv_task.done():
                                print("🔄 [Reconnecting fresh session after idle pause...]", flush=True)
                                break
                            await asyncio.sleep(0.05)

                        if self.state == "FINALIZING":
                            try:
                                await session.send_realtime_input(audio_stream_end=True)
                            except Exception:
                                pass
                            await asyncio.sleep(0.5)

                        send_task.cancel()
                        recv_task.cancel()

                except Exception as e:
                    while self.state == "LISTENING" and self.is_paused:
                        await asyncio.sleep(0.2)
                    if self.state == "LISTENING":
                        await asyncio.sleep(0.5)
                finally:
                    self.session = None

                if self.state == "FINALIZING":
                    break

        signals.hide_ui.emit()

manager = LiveTranscriptionManager()

# ==========================================================
# 6. WAVEFORM EQUALIZER & ANIMATED LOADING DOTS
# ==========================================================
class WaveformVisualizer(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(105)
        self.setFixedHeight(30)
        self.amplitude = 0.05
        self.is_processing = False
        self.is_paused = False
        self.dot_phase = 0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_amplitude(self, amp):
        if amp is None or np.isnan(amp) or np.isinf(amp):
            amp = 0.05
        self.amplitude = max(0.0, min(1.0, float(amp)))
        self.update()

    def set_processing(self, processing):
        self.is_processing = processing
        self.update()

    def set_paused(self, paused):
        self.is_paused = paused
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.PenStyle.NoPen))

        if self.is_processing:
            self.dot_phase = (self.dot_phase + 0.18) % (2 * np.pi)
            for i in range(3):
                offset = np.sin(self.dot_phase + i * 1.0) * 4
                dot_grad = QLinearGradient(35 + i * 18, 13 + offset, 35 + i * 18, 19 + offset)
                dot_grad.setColorAt(0.0, QColor("#38bdf8"))
                dot_grad.setColorAt(1.0, QColor("#818cf8"))
                painter.setBrush(QBrush(dot_grad))
                painter.drawEllipse(int(30 + i * 18), int(13 + offset), 6, 6)
            return

        if self.is_paused:
            painter.setBrush(QBrush(QColor(245, 158, 11, 140)))
            for i in range(5):
                painter.drawEllipse(int(25 + i * 14), 13, 4, 4)
            return

        num_bars = 9
        spacing = 11
        bar_width = 3.0
        max_height = 22
        min_height = 4.5

        safe_amp = self.amplitude if (self.amplitude and not np.isnan(self.amplitude)) else 0.05

        for i in range(num_bars):
            factor = 1.0 - abs(i - (num_bars // 2)) * 0.18
            height = int(min_height + (max_height - min_height) * safe_amp * factor)
            
            if safe_amp > 0.15:
                height += np.random.randint(-2, 3)
            height = max(int(min_height), min(max_height, height))

            x = 8 + i * spacing
            y = int((self.height() - height) / 2)

            bar_grad = QLinearGradient(x, y, x, y + height)
            bar_grad.setColorAt(0.0, QColor("#38bdf8"))
            bar_grad.setColorAt(1.0, QColor("#818cf8"))
            
            painter.setBrush(QBrush(bar_grad))
            painter.drawRoundedRect(x, y, int(bar_width), height, 1.5, 1.5)

# ==========================================================
# 7. VECTOR PAUSE & SEND BUTTONS
# ==========================================================
class VectorPauseButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.setFixedSize(36, 36)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_paused = False
        self.is_hovered = False
        self.setToolTip("Pause / Resume Dictation")

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()

    def set_paused_state(self, paused):
        self.is_paused = paused
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.is_paused:
            bg_color = QColor(245, 158, 11, 40)
            border_color = QColor(245, 158, 11, 140)
            icon_color = QColor("#fbbf24")
        elif self.is_hovered:
            bg_color = QColor(255, 255, 255, 30)
            border_color = QColor(255, 255, 255, 50)
            icon_color = QColor("#ffffff")
        else:
            bg_color = QColor(255, 255, 255, 18)
            border_color = QColor(255, 255, 255, 30)
            icon_color = QColor("#94a3b8")

        painter.setPen(QPen(border_color, 1.0))
        painter.setBrush(QBrush(bg_color))
        painter.drawEllipse(1, 1, self.width() - 2, self.height() - 2)

        cx = self.width() / 2.0
        cy = self.height() / 2.0

        if self.is_paused:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(icon_color))
            path = QPainterPath()
            path.moveTo(cx - 3.0, cy - 5.5)
            path.lineTo(cx + 5.5, cy)
            path.lineTo(cx - 3.0, cy + 5.5)
            path.closeSubpath()
            painter.drawPath(path)
        else:
            bar_pen = QPen(icon_color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(bar_pen)
            painter.drawLine(QPointF(cx - 3.5, cy - 5), QPointF(cx - 3.5, cy + 5))
            painter.drawLine(QPointF(cx + 3.5, cy - 5), QPointF(cx + 3.5, cy + 5))

class VectorSendButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.setFixedSize(36, 36)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_hovered = False

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_grad = QLinearGradient(0, 0, self.width(), self.height())
        if self.is_hovered:
            bg_grad.setColorAt(0.0, QColor("#7dd3fc"))
            bg_grad.setColorAt(1.0, QColor("#818cf8"))
        else:
            bg_grad.setColorAt(0.0, QColor("#38bdf8"))
            bg_grad.setColorAt(1.0, QColor("#6366f1"))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_grad))
        painter.drawEllipse(0, 0, self.width(), self.height())

        arrow_pen = QPen(QColor("#ffffff"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(arrow_pen)

        cx = self.width() / 2.0
        cy = self.height() / 2.0

        painter.drawLine(QPointF(cx, cy + 5.5), QPointF(cx, cy - 5.5))
        head_width = 4.2
        head_height = 4.5
        painter.drawLine(QPointF(cx - head_width, cy - 5.5 + head_height), QPointF(cx, cy - 5.5))
        painter.drawLine(QPointF(cx + head_width, cy - 5.5 + head_height), QPointF(cx, cy - 5.5))

# ==========================================================
# 8. DRAGGABLE PILL WINDOW (VaaniType Floating Widget)
# ==========================================================
class VoiceTypingWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._drag_pos = QPoint()
        self.beam_angle = 0.0
        self.wobble_phase = 0.0
        self.smooth_amp = 0.05
        self.init_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_ui)
        self.timer.start(16)

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(276, 62)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(8)

        # 1. Cancel Button (✕)
        self.btn_cancel = QPushButton("✕")
        self.btn_cancel.setFixedSize(36, 36)
        self.btn_cancel.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setToolTip("Cancel Dictation")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.07);
                color: #94a3b8;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 18px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.3);
                border: 1px solid rgba(239, 68, 68, 0.5);
                color: #ffffff;
            }
        """)
        self.btn_cancel.clicked.connect(manager.cancel_session)

        # 2. Pause Button (⏸ / ▶)
        self.btn_pause = VectorPauseButton()
        self.btn_pause.clicked.connect(manager.toggle_pause)

        # 3. Waveform Visualizer
        self.visualizer = WaveformVisualizer()

        # 4. Submit Button (↑)
        self.btn_send = VectorSendButton()
        self.btn_send.setToolTip("Finish & Submit (or Right-Click for Settings/Guide)")
        self.btn_send.clicked.connect(manager.finish_session)

        layout.addWidget(self.btn_cancel)
        layout.addWidget(self.btn_pause)
        layout.addWidget(self.visualizer)
        layout.addWidget(self.btn_send)

        screen = QApplication.primaryScreen().geometry()
        self.move(int((screen.width() - self.width()) / 2), int(screen.height() * 0.80))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            signals.open_settings.emit()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0

        pill_rect = QRectF(4, 4, self.width() - 8, self.height() - 8)
        radius = 27.0

        path = QPainterPath()
        path.addRoundedRect(pill_rect, radius, radius)

        # 1. Base Dark Gemini Obsidian Body
        bg_grad = QLinearGradient(0, 0, self.width(), self.height())
        bg_grad.setColorAt(0.0, QColor(8, 12, 24, 250))
        bg_grad.setColorAt(1.0, QColor(14, 20, 36, 250))
        painter.fillPath(path, QBrush(bg_grad))

        # 2. Expansive Inner Aurora Blend
        painter.save()
        painter.setClipPath(path)

        rad = np.radians(self.beam_angle - 180)
        light_x = center_x + np.cos(rad) * (self.width() / 2.0 - 12)
        light_y = center_y + np.sin(rad) * (self.height() / 2.0 - 12)

        bloom_rad = QRadialGradient(QPointF(light_x, light_y), 115.0)
        bloom_alpha = int(55 + self.smooth_amp * 70) if not manager.is_paused else 25

        if manager.is_paused:
            bloom_rad.setColorAt(0.00, QColor(245, 158, 11, bloom_alpha))
            bloom_rad.setColorAt(0.50, QColor(245, 158, 11, int(bloom_alpha * 0.3)))
            bloom_rad.setColorAt(1.00, QColor(8, 12, 24, 0))
        else:
            bloom_rad.setColorAt(0.00, QColor(56, 189, 248, bloom_alpha))
            bloom_rad.setColorAt(0.35, QColor(99, 102, 241, int(bloom_alpha * 0.6)))
            bloom_rad.setColorAt(0.70, QColor(168, 85, 247, int(bloom_alpha * 0.25)))
            bloom_rad.setColorAt(1.00, QColor(8, 12, 24, 0))

        painter.fillPath(path, QBrush(bloom_rad))
        painter.restore()

        # 3. Dual-Sided Trail Traveling Border
        beam_grad = QConicalGradient(QPointF(center_x, center_y), self.beam_angle)
        
        if manager.is_paused:
            beam_grad.setColorAt(0.00, QColor(0, 0, 0, 0))
            beam_grad.setColorAt(0.35, QColor(245, 158, 11, 20))
            beam_grad.setColorAt(0.50, QColor(251, 191, 36, 180))
            beam_grad.setColorAt(0.65, QColor(245, 158, 11, 20))
            beam_grad.setColorAt(1.00, QColor(0, 0, 0, 0))
        else:
            beam_grad.setColorAt(0.00, QColor(0, 0, 0, 0))
            beam_grad.setColorAt(0.22, QColor(0, 0, 0, 0))
            beam_grad.setColorAt(0.34, QColor(37, 99, 235, 45))
            beam_grad.setColorAt(0.42, QColor(99, 102, 241, 140))
            beam_grad.setColorAt(0.48, QColor(56, 189, 248, 240))
            beam_grad.setColorAt(0.50, QColor(255, 255, 255, 255))
            beam_grad.setColorAt(0.52, QColor(56, 189, 248, 240))
            beam_grad.setColorAt(0.58, QColor(168, 85, 247, 140))
            beam_grad.setColorAt(0.66, QColor(37, 99, 235, 45))
            beam_grad.setColorAt(0.78, QColor(0, 0, 0, 0))
            beam_grad.setColorAt(1.00, QColor(0, 0, 0, 0))

        base_pen = QPen(QColor(255, 255, 255, 12), 1.0)
        painter.setPen(base_pen)
        painter.drawPath(path)

        halo_pen = QPen(QBrush(beam_grad), 4.5)
        painter.setPen(halo_pen)
        painter.drawPath(path)

        core_pen = QPen(QBrush(beam_grad), 1.6)
        painter.setPen(core_pen)
        painter.drawPath(path)

    def refresh_ui(self):
        if self.isVisible():
            raw_amp = manager.current_amplitude if manager.state == "LISTENING" and not manager.is_paused else 0.05
            
            self.smooth_amp += (raw_amp - self.smooth_amp) * 0.15
            
            base_speed = 0.4 if manager.is_paused else 0.75
            wobble = np.sin(self.wobble_phase) * 0.15
            rot_speed = base_speed + (self.smooth_amp * 1.5) + wobble
            
            self.beam_angle = (self.beam_angle + rot_speed) % 360.0
            self.wobble_phase = (self.wobble_phase + 0.015) % (2 * np.pi)

            self.visualizer.set_amplitude(manager.current_amplitude)
            self.update()

    def toggle(self):
        if self.isVisible():
            manager.finish_session()
        else:
            self.show()
            manager.start_session()

# ==========================================================
# 9. HOTKEY RECORDER BUTTON
# ==========================================================
class HotkeyRecorderButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_recording = False
        self.recorded_pynput = current_config.get("hotkey_pynput", "<alt>+v")
        self.recorded_display = current_config.get("hotkey_display", "Alt + V")
        self.setText(f"⌨️  {self.recorded_display}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self.start_recording)

    def start_recording(self):
        self.is_recording = True
        self.setText("🔴 Press combination (e.g. Ctrl+Shift+Space)...")
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.2);
                border: 1px solid #ef4444;
                color: #f87171;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
                font-size: 13px;
            }
        """)

    def keyPressEvent(self, event):
        if not self.is_recording:
            super().keyPressEvent(event)
            return

        key = event.key()
        modifiers = event.modifiers()

        if key in [Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta]:
            return

        mod_parts_pynput = []
        mod_parts_display = []

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            mod_parts_pynput.append("<ctrl>")
            mod_parts_display.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            mod_parts_pynput.append("<alt>")
            mod_parts_display.append("Alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            mod_parts_pynput.append("<shift>")
            mod_parts_display.append("Shift")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            mod_parts_pynput.append("<cmd>")
            mod_parts_display.append("Win")

        key_char = ""
        key_name = ""

        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            key_char = chr(key).lower()
            key_name = chr(key).upper()
        elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            key_char = chr(key)
            key_name = chr(key)
        elif key == Qt.Key.Key_Space:
            key_char = "<space>"
            key_name = "Space"
        elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
            f_num = key - Qt.Key.Key_F1 + 1
            key_char = f"<f{f_num}>"
            key_name = f"F{f_num}"
        else:
            key_char = event.text().lower()
            key_name = event.text().upper()

        if not key_char:
            return

        mod_parts_pynput.append(key_char)
        mod_parts_display.append(key_name)

        self.recorded_pynput = "+".join(mod_parts_pynput)
        self.recorded_display = " + ".join(mod_parts_display)
        self.is_recording = False

        self.setText(f"⌨️  {self.recorded_display}")
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(56, 189, 248, 0.12);
                border: 1px solid rgba(56, 189, 248, 0.4);
                color: #38bdf8;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(56, 189, 248, 0.2);
                border: 1px solid #38bdf8;
            }
        """)

# ==========================================================
# 10. COMBINED SETTINGS & INFO GUIDE DIALOG (2 Tabs)
# ==========================================================
class SettingsDialog(QWidget):
    def __init__(self):
        super().__init__()
        self._drag_pos = QPoint()
        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(460, 560)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)

        self.frame = QFrame(self)
        self.frame.setStyleSheet("""
            QFrame {
                background-color: rgba(11, 15, 25, 0.97);
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 20px;
            }
        """)
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(20, 18, 20, 18)
        frame_layout.setSpacing(12)

        # 1. HEADER WITH TAB SWITCHER & CLOSE
        header_layout = QHBoxLayout()
        
        self.btn_tab_settings = QPushButton("⚙️ Settings")
        self.btn_tab_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tab_settings.setFixedHeight(32)

        self.btn_tab_info = QPushButton("📖 Guide & Features")
        self.btn_tab_info.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tab_info.setFixedHeight(32)

        self.btn_tab_settings.clicked.connect(lambda: self.switch_tab(0))
        self.btn_tab_info.clicked.connect(lambda: self.switch_tab(1))

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #94a3b8;
                border: none;
                border-radius: 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: white;
            }
        """)
        self.btn_close.clicked.connect(self.hide)

        header_layout.addWidget(self.btn_tab_settings)
        header_layout.addWidget(self.btn_tab_info)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_close)
        frame_layout.addLayout(header_layout)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: rgba(255, 255, 255, 0.1); border: none;")
        frame_layout.addWidget(line)

        # 2. STACKED WIDGET (Tabs Container)
        self.stack = QStackedWidget()

        # ==========================================
        # TAB 1: SETTINGS PAGE
        # ==========================================
        tab1_widget = QWidget()
        t1_layout = QVBoxLayout(tab1_widget)
        t1_layout.setContentsMargins(0, 4, 0, 4)
        t1_layout.setSpacing(12)

        # API Key Field
        api_label = QLabel("🔑 Gemini API Key:")
        api_label.setStyleSheet("color: #cbd5e1; font-size: 13px; font-weight: 600; border: none;")
        t1_layout.addWidget(api_label)

        self.input_api_key = QLineEdit()
        self.input_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_api_key.setText(current_config.get("api_key", ""))
        self.input_api_key.setPlaceholderText("Paste your Gemini API Key here...")
        self.input_api_key.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 10px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
                background-color: rgba(56, 189, 248, 0.08);
            }
        """)
        t1_layout.addWidget(self.input_api_key)

        self.btn_toggle_key = QPushButton("👁️ Show Key")
        self.btn_toggle_key.setCheckable(True)
        self.btn_toggle_key.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_key.setStyleSheet("QPushButton { background: transparent; color: #94a3b8; border: none; text-align: left; font-size: 11px; } QPushButton:hover { color: #38bdf8; }")
        self.btn_toggle_key.toggled.connect(self.toggle_api_visibility)
        t1_layout.addWidget(self.btn_toggle_key)

        # Hotkey Shortcut
        hotkey_label = QLabel("⌨️ Activation Shortcut (Hotkey):")
        hotkey_label.setStyleSheet("color: #cbd5e1; font-size: 13px; font-weight: 600; border: none; margin-top: 4px;")
        t1_layout.addWidget(hotkey_label)

        self.btn_hotkey_record = HotkeyRecorderButton()
        t1_layout.addWidget(self.btn_hotkey_record)

        # Windows Startup Checkbox
        self.chk_startup = QCheckBox("🚀 Start automatically with Windows (Startup)")
        self.chk_startup.setChecked(is_windows_startup_enabled())
        self.chk_startup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_startup.setStyleSheet("""
            QCheckBox {
                color: #e2e8f0;
                font-size: 13px;
                font-weight: 500;
                border: none;
                spacing: 8px;
                margin-top: 6px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid rgba(56, 189, 248, 0.4);
                background-color: rgba(255, 255, 255, 0.06);
            }
            QCheckBox::indicator:checked {
                background-color: #38bdf8;
                border: 1px solid #38bdf8;
                image: none;
            }
        """)
        t1_layout.addWidget(self.chk_startup)

        hint_label = QLabel("💡 Tip: Right-click on the floating pill widget anytime to reopen this page.")
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #64748b; font-size: 11px; border: none;")
        t1_layout.addWidget(hint_label)

        t1_layout.addStretch()
        
        # ==========================================
        # VAANITYPE CENTERED BRANDING LOGO (Horizontal PNG)
        # ==========================================
        logo_layout = QHBoxLayout()
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        logo_path = os.path.join(BASE_DIR, "vaanilogo.png")
        if os.path.exists(logo_path):
            logo_lbl = QLabel()
            # Horizontal Logo के लिए 180x45 साइज़ (Aspect Ratio बरकरार रहेगा)
            logo_pixmap = QPixmap(logo_path).scaled(
                200, 100, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            logo_lbl.setPixmap(logo_pixmap)
            logo_lbl.setStyleSheet("border: none; background: transparent;")
            logo_layout.addWidget(logo_lbl)
        
        t1_layout.addLayout(logo_layout)

        # Bottom Stretch
        t1_layout.addStretch()

        # Save Button
        self.btn_save = QPushButton("💾 Save & Apply Settings")
        self.btn_save.setFixedHeight(42)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #6366f1);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7dd3fc, stop:1 #818cf8);
            }
        """)
        self.btn_save.clicked.connect(self.save_settings)
        t1_layout.addWidget(self.btn_save)

        self.stack.addWidget(tab1_widget)

        # ==========================================
        # TAB 2: INFO & VOICE COMMANDS GUIDE
        # ==========================================
        tab2_widget = QWidget()
        t2_scroll = QScrollArea()
        t2_scroll.setWidgetResizable(True)
        t2_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollBar { width: 0px; }")
        
        t2_content = QWidget()
        t2_layout = QVBoxLayout(t2_content)
        t2_layout.setContentsMargins(0, 0, 5, 0)
        t2_layout.setSpacing(10)

        # App Info Card (With Custom Logo)
        info_card = QFrame()
        info_card.setStyleSheet("QFrame { background-color: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 12px; }")
        card_layout = QVBoxLayout(info_card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)
        
        # Title Row (Icon + App Name)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        # 1. Custom App Icon
        icon_path = os.path.join(BASE_DIR, "vaani.ico")
        icon_lbl = QLabel()
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(
                24, 24, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            icon_lbl.setPixmap(pixmap)
        else:
            icon_lbl.setText("🎙️")
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        title_row.addWidget(icon_lbl)

        # 2. App Name & Version Text
        lbl_app_name = QLabel(f"{APP_NAME} v{__version__}")
        lbl_app_name.setStyleSheet("color: #38bdf8; font-size: 15px; font-weight: bold; border: none; background: transparent;")
        title_row.addWidget(lbl_app_name)
        title_row.addStretch()

        card_layout.addLayout(title_row)

        # App Description
        lbl_app_desc = QLabel("Next-Gen Live Speech-to-Text Dictation Engine powered by Google Gemini 3.5 Transcribe Live.")
        lbl_app_desc.setWordWrap(True)
        lbl_app_desc.setStyleSheet("color: #cbd5e1; font-size: 12px; border: none; background: transparent;")
        card_layout.addWidget(lbl_app_desc)
        t2_layout.addWidget(info_card)

        # Commands Title
        lbl_cmd_title = QLabel("⚡ Voice Commands Reference:")
        lbl_cmd_title.setStyleSheet("color: #f8fafc; font-size: 13px; font-weight: bold; border: none; margin-top: 4px;")
        t2_layout.addWidget(lbl_cmd_title)

        # Commands List Cards
        commands = [
            ("🔹 'Vaani delete that'", "Deletes the last spoken word (Ctrl + Backspace)"),
            ("🔹 'Vaani delete all'", "Clears all text in the document (Ctrl + A -> Backspace)"),
            ("🔹 'Vaani undo'", "Undoes the last typing segment (Ctrl + Z)"),
            ("🔹 'Vaani pause' / 'resume'", "Pauses or resumes microphone listening"),
            ("🔹 'Vaani new line'", "Presses Enter for a new line"),
            ("🔹 'Vaani add space'", "Inserts a single space character"),
        ]

        for cmd, desc in commands:
            cmd_frame = QFrame()
            cmd_frame.setStyleSheet("QFrame { background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; }")
            cf_layout = QVBoxLayout(cmd_frame)
            cf_layout.setContentsMargins(10, 8, 10, 8)
            
            c_lbl = QLabel(cmd)
            c_lbl.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px; border: none;")
            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; border: none;")
            cf_layout.addWidget(c_lbl)
            cf_layout.addWidget(d_lbl)
            t2_layout.addWidget(cmd_frame)

        t2_scroll.setWidget(t2_content)
        t2_main_layout = QVBoxLayout(tab2_widget)
        t2_main_layout.setContentsMargins(0, 0, 0, 0)
        t2_main_layout.addWidget(t2_scroll)

        self.stack.addWidget(tab2_widget)
        frame_layout.addWidget(self.stack)

        main_layout.addWidget(self.frame)

        # Initial Tab Style
        self.switch_tab(0)

        # Center in screen
        screen = QApplication.primaryScreen().geometry()
        self.move(int((screen.width() - self.width()) / 2), int((screen.height() - self.height()) / 2))

    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.btn_tab_settings.setStyleSheet("""
                QPushButton {
                    background-color: rgba(56, 189, 248, 0.18);
                    color: #38bdf8;
                    border: 1px solid #38bdf8;
                    border-radius: 8px;
                    padding: 4px 14px;
                    font-weight: bold;
                    font-size: 12px;
                }
            """)
            self.btn_tab_info.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94a3b8;
                    border: 1px solid transparent;
                    border-radius: 8px;
                    padding: 4px 14px;
                    font-weight: 500;
                    font-size: 12px;
                }
                QPushButton:hover { color: #f8fafc; }
            """)
        else:
            self.btn_tab_info.setStyleSheet("""
                QPushButton {
                    background-color: rgba(56, 189, 248, 0.18);
                    color: #38bdf8;
                    border: 1px solid #38bdf8;
                    border-radius: 8px;
                    padding: 4px 14px;
                    font-weight: bold;
                    font-size: 12px;
                }
            """)
            self.btn_tab_settings.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94a3b8;
                    border: 1px solid transparent;
                    border-radius: 8px;
                    padding: 4px 14px;
                    font-weight: 500;
                    font-size: 12px;
                }
                QPushButton:hover { color: #f8fafc; }
            """)

    def toggle_api_visibility(self, checked):
        if checked:
            self.input_api_key.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_key.setText("🙈 Hide Key")
        else:
            self.input_api_key.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_key.setText("👁️ Show Key")

    def save_settings(self):
        new_key = self.input_api_key.text().strip()
        new_hotkey_pynput = self.btn_hotkey_record.recorded_pynput
        new_hotkey_display = self.btn_hotkey_record.recorded_display
        enable_startup = self.chk_startup.isChecked()

        # Update Windows Registry for auto-start
        set_windows_startup(enable_startup)

        current_config["api_key"] = new_key
        current_config["hotkey_pynput"] = new_hotkey_pynput
        current_config["hotkey_display"] = new_hotkey_display
        current_config["start_with_windows"] = enable_startup

        if save_config(current_config):
            signals.config_updated.emit()
            self.hide()
            print(f"✅ Settings Saved! Startup Enabled: {enable_startup}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

# ==========================================================
# 11. DYNAMIC HOTKEY MANAGER
# ==========================================================
class DynamicHotkeyManager:
    def __init__(self):
        self.listener = None

    def start(self):
        self.stop()
        hotkey_str = current_config.get("hotkey_pynput", "<alt>+v")
        
        def on_hotkey():
            signals.toggle_ui.emit()

        try:
            self.listener = GlobalHotKeys({hotkey_str: on_hotkey})
            self.listener.start()
            print(f"⌨️ [Hotkey Active]: {current_config.get('hotkey_display', 'Alt + V')} ({hotkey_str})")
        except Exception as e:
            print(f"❌ Hotkey Register Error ({hotkey_str}): {e}")
            self.listener = GlobalHotKeys({"<alt>+v": on_hotkey})
            self.listener.start()

    def stop(self):
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None

# ==========================================================
# 12. MAIN ENTRY POINT
# ==========================================================
def main():
    app = QApplication(sys.argv)

    widget = VoiceTypingWidget()
    settings_dialog = SettingsDialog()
    hotkey_mgr = DynamicHotkeyManager()

    # Signals
    signals.toggle_ui.connect(widget.toggle)
    signals.live_text_received.connect(process_voice_input_and_type)
    signals.set_processing_ui.connect(widget.visualizer.set_processing)
    signals.set_paused_ui.connect(widget.btn_pause.set_paused_state)
    signals.set_paused_ui.connect(widget.visualizer.set_paused)
    signals.hide_ui.connect(widget.hide)
    signals.open_settings.connect(settings_dialog.show)
    signals.config_updated.connect(hotkey_mgr.start)

    hotkey_mgr.start()

    if not current_config.get("api_key", "").strip():
        settings_dialog.show()

    print("==================================================")
    print(" 🎙️ VaaniType - Full Controls & Guide Ready       ")
    print(f" • Press [{current_config.get('hotkey_display', 'Alt + V')}] -> Start Speaking")
    print(" • Right-Click on Widget -> Open Settings & Guide ")
    print("==================================================")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()