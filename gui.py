from __future__ import annotations

import queue
import re
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

try:
    import customtkinter as ctk
except ImportError as error:
    raise SystemExit(
        "customtkinter is not installed. Run: pip install customtkinter"
    ) from error

from src.framing import Frame, create_frames, reassemble_frames, serialize_frame
from src.metrics import (
    calculate_efficiency,
    calculate_goodput,
    calculate_throughput,
)
from src.security import xor_decrypt, xor_encrypt
from src.selective_repeat import (
    selective_repeat_bpsk,
    selective_repeat_qam16,
    selective_repeat_wired,
)
from src.utils import read_file, save_recovered_file, text_to_bytes

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class FrameBoard(tk.Canvas):
    FRAME_WIDTH = 106
    FRAME_HEIGHT = 86
    GAP = 18
    MARGIN_X = 28
    MARGIN_Y = 38

    COLORS = {
        "pending": "#263244",
        "window": "#334155",
        "sending": "#2563EB",
        "retransmit": "#7C3AED",
        "ack": "#16A34A",
        "nak": "#EA580C",
        "lost": "#DC2626",
        "timeout": "#CA8A04",
        "crc_failed": "#D97706",
        "failed": "#991B1B",
    }

    LABELS = {
        "pending": "WAITING",
        "window": "IN WINDOW",
        "sending": "SENDING",
        "retransmit": "RETRY",
        "ack": "ACK",
        "nak": "NAK",
        "lost": "LOST",
        "timeout": "TIMEOUT",
        "crc_failed": "CRC ERROR",
        "failed": "FAILED",
    }

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            bg="#101827",
            highlightthickness=0,
            height=185,
            **kwargs,
        )
        self.frame_items: dict[int, dict[str, int | str]] = {}
        self.frame_states: dict[int, str] = {}
        self.frame_attempts: dict[int, int] = {}
        self.window_outline = None
        self.total_frames = 0

    def reset(self, total_frames: int):
        self.delete("all")
        self.frame_items.clear()
        self.frame_states.clear()
        self.frame_attempts.clear()
        self.window_outline = None
        self.total_frames = total_frames

        for sequence_number in range(total_frames):
            self.frame_states[sequence_number] = "pending"
            self.frame_attempts[sequence_number] = 0
            self._draw_frame(sequence_number)

        total_width = (
            self.MARGIN_X * 2
            + total_frames * self.FRAME_WIDTH
            + max(0, total_frames - 1) * self.GAP
        )
        self.configure(scrollregion=(0, 0, max(total_width, 900), 185))
        self.xview_moveto(0)

    def _rounded_rectangle(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _frame_x(self, sequence_number: int) -> int:
        return self.MARGIN_X + sequence_number * (self.FRAME_WIDTH + self.GAP)

    def _draw_frame(self, sequence_number: int):
        x1 = self._frame_x(sequence_number)
        y1 = self.MARGIN_Y
        x2 = x1 + self.FRAME_WIDTH
        y2 = y1 + self.FRAME_HEIGHT

        rectangle = self._rounded_rectangle(
            x1,
            y1,
            x2,
            y2,
            14,
            fill=self.COLORS["pending"],
            outline="#475569",
            width=2,
        )
        number = self.create_text(
            x1 + 14,
            y1 + 15,
            text=f"FRAME {sequence_number}",
            anchor="w",
            fill="#E2E8F0",
            font=("DejaVu Sans", 10, "bold"),
        )
        status = self.create_text(
            x1 + self.FRAME_WIDTH / 2,
            y1 + 46,
            text=self.LABELS["pending"],
            fill="#F8FAFC",
            font=("DejaVu Sans", 11, "bold"),
        )
        attempt = self.create_text(
            x1 + self.FRAME_WIDTH / 2,
            y1 + 69,
            text="Attempt 0",
            fill="#CBD5E1",
            font=("DejaVu Sans", 9),
        )

        self.frame_items[sequence_number] = {
            "rectangle": rectangle,
            "number": number,
            "status": status,
            "attempt": attempt,
        }

    def set_state(self, sequence_number: int, state: str, attempt: int | None = None):
        if sequence_number not in self.frame_items:
            return

        self.frame_states[sequence_number] = state
        if attempt is not None:
            self.frame_attempts[sequence_number] = attempt

        items = self.frame_items[sequence_number]
        self.itemconfigure(items["rectangle"], fill=self.COLORS[state])
        self.itemconfigure(items["status"], text=self.LABELS[state])
        self.itemconfigure(
            items["attempt"],
            text=f"Attempt {self.frame_attempts[sequence_number]}",
        )
        self._scroll_to_frame(sequence_number)

    def set_window(self, start: int, end: int):
        if self.window_outline is not None:
            self.delete(self.window_outline)

        for sequence_number in range(self.total_frames):
            if (
                start <= sequence_number <= end
                and self.frame_states.get(sequence_number) == "pending"
            ):
                self.set_state(sequence_number, "window")
            elif self.frame_states.get(sequence_number) == "window":
                self.set_state(sequence_number, "pending")

        x1 = self._frame_x(start) - 9
        x2 = self._frame_x(end) + self.FRAME_WIDTH + 9
        y1 = self.MARGIN_Y - 20
        y2 = self.MARGIN_Y + self.FRAME_HEIGHT + 20
        self.window_outline = self._rounded_rectangle(
            x1,
            y1,
            x2,
            y2,
            18,
            fill="",
            outline="#38BDF8",
            width=3,
            dash=(7, 5),
        )
        self.tag_lower(self.window_outline)
        self._scroll_to_frame(start)

    def _scroll_to_frame(self, sequence_number: int):
        if self.total_frames <= 0:
            return
        total_width = max(
            self.winfo_width(),
            self.MARGIN_X * 2
            + self.total_frames * self.FRAME_WIDTH
            + max(0, self.total_frames - 1) * self.GAP,
        )
        x = self._frame_x(sequence_number)
        fraction = max(0.0, min(1.0, (x - 50) / total_width))
        self.xview_moveto(fraction)


class SignalPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=8, pady=(4, 2), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="PHYSICAL LAYER SIGNAL",
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#E2E8F0",
        ).grid(row=0, column=0, sticky="w")

        self.details_text = ctk.StringVar(
            value="The transmitted and received signals will appear here."
        )
        ctk.CTkLabel(
            header,
            textvariable=self.details_text,
            anchor="e",
            font=ctk.CTkFont(size=11),
            text_color="#7DD3FC",
        ).grid(row=0, column=1, sticky="e")

        self.figure = Figure(figsize=(10, 3.2), dpi=100, facecolor="#0F1B2D")
        self.transmitted_axis = self.figure.add_subplot(121)
        self.received_axis = self.figure.add_subplot(122)
        self.figure.subplots_adjust(
            left=0.07, right=0.98, bottom=0.16, top=0.85, wspace=0.24
        )

        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.grid(row=1, column=0, padx=8, pady=(0, 7), sticky="nsew")
        canvas_widget.configure(bg="#0F1B2D", highlightthickness=0)

        self.reset()

    def _style_axis(self, axis, title: str):
        axis.set_facecolor("#091321")
        axis.set_title(title, color="#E2E8F0", fontsize=10, fontweight="bold")
        axis.tick_params(colors="#94A3B8", labelsize=8)
        axis.grid(True, alpha=0.16, color="#94A3B8")
        axis.set_xlabel("Sample / Symbol", color="#64748B", fontsize=8)

        for spine in axis.spines.values():
            spine.set_color("#26364A")

    def reset(self):
        self.transmitted_axis.clear()
        self.received_axis.clear()
        self._style_axis(self.transmitted_axis, "Before Channel")
        self._style_axis(self.received_axis, "After Channel")

        for axis in (self.transmitted_axis, self.received_axis):
            axis.text(
                0.5,
                0.5,
                "Waiting for signal data",
                transform=axis.transAxes,
                ha="center",
                va="center",
                color="#64748B",
                fontsize=10,
            )
            axis.set_xticks([])
            axis.set_yticks([])

        self.details_text.set("The transmitted and received signals will appear here.")
        self.canvas.draw_idle()

    def show_signal(self, signal_data: dict):
        method = signal_data.get("method", "unknown")
        frame = signal_data.get("frame")
        attempt = signal_data.get("attempt")

        self.transmitted_axis.clear()
        self.received_axis.clear()

        method_title = {
            "b8zs": "B8ZS",
            "hdb3": "HDB3",
            "bpsk": "BPSK",
            "qam16": "16-QAM",
        }.get(method, method.upper())

        self.details_text.set(f"Frame {frame}  •  Attempt {attempt}  •  {method_title}")

        if signal_data.get("lost"):
            self._style_axis(self.transmitted_axis, "Before Channel")
            self._style_axis(self.received_axis, "After Channel")
            self.transmitted_axis.text(
                0.5,
                0.5,
                "Frame dropped before reception",
                transform=self.transmitted_axis.transAxes,
                ha="center",
                va="center",
                color="#F59E0B",
                fontsize=11,
                fontweight="bold",
            )
            self.received_axis.text(
                0.5,
                0.5,
                "No received signal",
                transform=self.received_axis.transAxes,
                ha="center",
                va="center",
                color="#EF4444",
                fontsize=11,
                fontweight="bold",
            )
            self.transmitted_axis.set_xticks([])
            self.transmitted_axis.set_yticks([])
            self.received_axis.set_xticks([])
            self.received_axis.set_yticks([])
            self.canvas.draw_idle()
            return

        transmitted_signal = signal_data["transmitted_signal"]
        received_signal = signal_data["received_signal"]

        if method == "qam16":
            self._style_axis(self.transmitted_axis, "Transmitted Constellation")
            self._style_axis(self.received_axis, "Received Constellation")

            self.transmitted_axis.scatter(
                transmitted_signal.real,
                transmitted_signal.imag,
                s=20,
                alpha=0.72,
                color="#38BDF8",
            )
            self.received_axis.scatter(
                received_signal.real,
                received_signal.imag,
                s=20,
                alpha=0.72,
                color="#F472B6",
            )

            for axis in (self.transmitted_axis, self.received_axis):
                axis.axhline(0, linewidth=0.8, alpha=0.35, color="#94A3B8")
                axis.axvline(0, linewidth=0.8, alpha=0.35, color="#94A3B8")
                axis.set_xlim(-5, 5)
                axis.set_ylim(-5, 5)
                axis.set_xlabel("In-phase", color="#64748B", fontsize=8)
                axis.set_ylabel("Quadrature", color="#64748B", fontsize=8)
                axis.set_aspect("equal", adjustable="box")

        elif method in ("b8zs", "hdb3"):
            self._style_axis(self.transmitted_axis, "Before Channel")
            self._style_axis(self.received_axis, "After Gaussian Noise")

            self.transmitted_axis.step(
                range(len(transmitted_signal)),
                transmitted_signal,
                where="post",
                linewidth=1.5,
                color="#38BDF8",
            )
            self.received_axis.step(
                range(len(received_signal)),
                received_signal,
                where="post",
                linewidth=1.5,
                color="#F472B6",
            )

            self.transmitted_axis.set_ylim(-1.5, 1.5)
            self.transmitted_axis.set_yticks([-1, 0, 1])
            self.transmitted_axis.set_ylabel(
                "Signal level",
                color="#64748B",
                fontsize=8,
            )

            if len(received_signal) > 0:
                largest_amplitude = max(
                    1.5,
                    abs(min(received_signal)) + 0.2,
                    abs(max(received_signal)) + 0.2,
                )
            else:
                largest_amplitude = 1.5

            self.received_axis.set_ylim(
                -largest_amplitude,
                largest_amplitude,
            )
            self.received_axis.set_ylabel(
                "Noisy amplitude",
                color="#64748B",
                fontsize=8,
            )
            self.received_axis.axhline(
                0.5,
                linewidth=1,
                linestyle="--",
                alpha=0.6,
                color="#FBBF24",
            )
            self.received_axis.axhline(
                -0.5,
                linewidth=1,
                linestyle="--",
                alpha=0.6,
                color="#FBBF24",
            )

        else:
            self._style_axis(self.transmitted_axis, "Before AWGN")
            self._style_axis(self.received_axis, "After AWGN")

            self.transmitted_axis.plot(
                transmitted_signal,
                linewidth=1.05,
                color="#38BDF8",
            )
            self.received_axis.plot(
                received_signal,
                linewidth=1.0,
                color="#F472B6",
            )

            for axis in (self.transmitted_axis, self.received_axis):
                axis.set_ylabel("Amplitude", color="#64748B", fontsize=8)

        self.canvas.draw_idle()


class NetworkSimulatorGUI(ctk.CTk):
    EVENT_DELAY_MS = 90

    def __init__(self):
        super().__init__()

        self.title("End-to-End Network Simulator")
        self.geometry("1480x920")
        self.minsize(1240, 780)
        self.configure(fg_color="#08111F")

        self.event_queue: queue.Queue = queue.Queue()
        self.simulation_running = False
        self.current_frame = None
        self.total_frames = 0
        self.acked_frames: set[int] = set()
        self.selected_file_path: str | None = None

        self.input_type = ctk.StringVar(value="Text")
        self.channel_type = ctk.StringVar(value="Wireless")
        self.method = ctk.StringVar(value="BPSK")

        self.window_size = ctk.StringVar(value="4")
        self.timeout_ticks = ctk.StringVar(value="3")
        self.max_attempts = ctk.StringVar(value="10")
        self.loss_rate = ctk.StringVar(value="0.0")
        self.wired_noise_std = ctk.StringVar(value="0.0")
        self.snr_db = ctk.StringVar(value="10")
        self.samples_per_bit = ctk.StringVar(value="50")
        self.seed = ctk.StringVar(value="42")
        self.payload_size = ctk.StringVar(value="4")

        self.status_text = ctk.StringVar(value="READY")
        self.window_text = ctk.StringVar(value="Sender window: —")
        self.current_event_text = ctk.StringVar(value="Waiting for a transmission")
        self.file_name_text = ctk.StringVar(value="No file selected")

        self._build_interface()
        self._update_input_mode("Text")
        self._update_channel("Wireless")
        self.after(40, self._process_event_queue)

    def _build_interface(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(
            self,
            width=340,
            corner_radius=0,
            fg_color="#0D1726",
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            self.sidebar,
            text="NETWORK\nSIMULATOR",
            justify="left",
            anchor="w",
            font=ctk.CTkFont(size=27, weight="bold"),
            text_color="#F8FAFC",
        )
        title.grid(row=0, column=0, padx=24, pady=(26, 4), sticky="ew")

        subtitle = ctk.CTkLabel(
            self.sidebar,
            text="Physical + Data Link Layer",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color="#7DD3FC",
        )
        subtitle.grid(row=1, column=0, padx=24, pady=(0, 22), sticky="ew")

        self._section_label(self.sidebar, "INPUT", 2)
        input_switch = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["Text", "File"],
            variable=self.input_type,
            command=self._update_input_mode,
            height=36,
        )
        input_switch.grid(row=3, column=0, padx=24, pady=(6, 10), sticky="ew")

        self.message_box = ctk.CTkTextbox(
            self.sidebar,
            height=90,
            corner_radius=12,
            fg_color="#111F31",
            border_width=1,
            border_color="#26364A",
        )
        self.message_box.grid(row=4, column=0, padx=24, pady=(0, 10), sticky="ew")
        self.message_box.insert("1.0", "Hello Network")

        self.file_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.file_frame.grid(row=5, column=0, padx=24, pady=(0, 14), sticky="ew")
        self.file_frame.grid_columnconfigure(0, weight=1)

        self.file_label = ctk.CTkLabel(
            self.file_frame,
            textvariable=self.file_name_text,
            anchor="w",
            text_color="#94A3B8",
        )
        self.file_label.grid(row=0, column=0, pady=(0, 7), sticky="ew")

        self.browse_button = ctk.CTkButton(
            self.file_frame,
            text="Choose file",
            command=self._browse_file,
            height=34,
            fg_color="#1E3A5F",
            hover_color="#28517F",
        )
        self.browse_button.grid(row=1, column=0, sticky="ew")

        self._section_label(self.sidebar, "CHANNEL", 6)
        channel_switch = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["Wired", "Wireless"],
            variable=self.channel_type,
            command=self._update_channel,
            height=36,
        )
        channel_switch.grid(row=7, column=0, padx=24, pady=(6, 10), sticky="ew")

        self.method_menu = ctk.CTkOptionMenu(
            self.sidebar,
            variable=self.method,
            values=["BPSK", "16-QAM"],
            height=36,
        )
        self.method_menu.grid(row=8, column=0, padx=24, pady=(0, 16), sticky="ew")

        self._section_label(self.sidebar, "SIMULATION", 9)
        settings_frame = ctk.CTkFrame(
            self.sidebar,
            corner_radius=14,
            fg_color="#111F31",
        )
        settings_frame.grid(row=10, column=0, padx=24, pady=(6, 16), sticky="ew")
        settings_frame.grid_columnconfigure((0, 1), weight=1)

        settings = [
            ("Window", self.window_size),
            ("Timeout", self.timeout_ticks),
            ("Attempts", self.max_attempts),
            ("Payload", self.payload_size),
            ("Loss", self.loss_rate),
            ("Wired noise std", self.wired_noise_std),
            ("SNR", self.snr_db),
            ("Seed", self.seed),
        ]

        for index, (label, variable) in enumerate(settings):
            row = (index // 2) * 2
            column = index % 2
            ctk.CTkLabel(
                settings_frame,
                text=label,
                anchor="w",
                text_color="#94A3B8",
                font=ctk.CTkFont(size=11),
            ).grid(row=row, column=column, padx=10, pady=(10, 2), sticky="ew")
            ctk.CTkEntry(
                settings_frame,
                textvariable=variable,
                height=32,
                fg_color="#0B1625",
                border_color="#26364A",
            ).grid(row=row + 1, column=column, padx=10, pady=(0, 6), sticky="ew")

        self.start_button = ctk.CTkButton(
            self.sidebar,
            text="START TRANSMISSION",
            command=self._start_simulation,
            height=48,
            corner_radius=14,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#0284C7",
            hover_color="#0369A1",
        )
        self.start_button.grid(row=11, column=0, padx=24, pady=(0, 9), sticky="ew")

        self.clear_button = ctk.CTkButton(
            self.sidebar,
            text="Reset dashboard",
            command=self._clear_output,
            height=38,
            fg_color="#1E293B",
            hover_color="#334155",
        )
        self.clear_button.grid(row=12, column=0, padx=24, pady=(0, 24), sticky="ew")

        self.content = ctk.CTkFrame(self, fg_color="#08111F", corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.grid(row=0, column=0, padx=26, pady=(22, 12), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Selective Repeat Transmission",
            anchor="w",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#F8FAFC",
        ).grid(row=0, column=0, sticky="ew")

        self.status_badge = ctk.CTkLabel(
            header,
            textvariable=self.status_text,
            width=125,
            height=34,
            corner_radius=17,
            fg_color="#334155",
            text_color="#E2E8F0",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.status_badge.grid(row=0, column=1, sticky="e")

        event_card = ctk.CTkFrame(
            self.content,
            corner_radius=16,
            fg_color="#0F1B2D",
            border_width=1,
            border_color="#1E334D",
        )
        event_card.grid(row=1, column=0, padx=26, pady=(0, 12), sticky="ew")
        event_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            event_card,
            text="CURRENT EVENT",
            anchor="w",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38BDF8",
        ).grid(row=0, column=0, padx=18, pady=(13, 2), sticky="ew")

        ctk.CTkLabel(
            event_card,
            textvariable=self.current_event_text,
            anchor="w",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#F8FAFC",
        ).grid(row=1, column=0, padx=18, pady=(0, 13), sticky="ew")

        board_card = ctk.CTkFrame(
            self.content,
            corner_radius=18,
            fg_color="#0F1B2D",
            border_width=1,
            border_color="#1E334D",
        )
        board_card.grid(row=2, column=0, padx=26, pady=(0, 12), sticky="ew")
        board_card.grid_columnconfigure(0, weight=1)

        board_header = ctk.CTkFrame(board_card, fg_color="transparent")
        board_header.grid(row=0, column=0, padx=18, pady=(14, 2), sticky="ew")
        board_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            board_header,
            text="FRAME FLOW",
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#E2E8F0",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            board_header,
            textvariable=self.window_text,
            anchor="e",
            text_color="#7DD3FC",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=1, sticky="e")

        canvas_holder = ctk.CTkFrame(board_card, fg_color="#101827", corner_radius=12)
        canvas_holder.grid(row=1, column=0, padx=18, pady=(8, 10), sticky="ew")
        canvas_holder.grid_columnconfigure(0, weight=1)

        self.frame_board = FrameBoard(canvas_holder)
        self.frame_board.grid(row=0, column=0, sticky="ew")

        scrollbar = ctk.CTkScrollbar(
            canvas_holder,
            orientation="horizontal",
            command=self.frame_board.xview,
            height=14,
        )
        scrollbar.grid(row=1, column=0, padx=8, pady=(2, 7), sticky="ew")
        self.frame_board.configure(xscrollcommand=scrollbar.set)

        legend = ctk.CTkFrame(board_card, fg_color="transparent")
        legend.grid(row=2, column=0, padx=18, pady=(0, 14), sticky="ew")

        legend_items = [
            ("Waiting", "pending"),
            ("Sending", "sending"),
            ("ACK", "ack"),
            ("NAK", "nak"),
            ("Lost", "lost"),
            ("Retry", "retransmit"),
            ("Failed", "failed"),
        ]
        for index, (label, state) in enumerate(legend_items):
            marker = ctk.CTkLabel(
                legend,
                text="●",
                width=18,
                text_color=FrameBoard.COLORS[state],
                font=ctk.CTkFont(size=16),
            )
            marker.grid(row=0, column=index * 2, padx=(0, 2), sticky="w")
            ctk.CTkLabel(
                legend,
                text=label,
                text_color="#94A3B8",
                font=ctk.CTkFont(size=11),
            ).grid(row=0, column=index * 2 + 1, padx=(0, 13), sticky="w")

        lower = ctk.CTkFrame(self.content, fg_color="transparent")
        lower.grid(row=3, column=0, padx=26, pady=(0, 22), sticky="nsew")
        lower.grid_columnconfigure(0, weight=1)
        lower.grid_rowconfigure(1, weight=1)

        stats = ctk.CTkFrame(lower, fg_color="transparent")
        stats.grid(row=0, column=0, pady=(0, 10), sticky="ew")
        for column in range(5):
            stats.grid_columnconfigure(column, weight=1)

        self.stat_values = {}
        stat_definitions = [
            ("Frames", "0 / 0"),
            ("Ticks", "0"),
            ("Retries", "0"),
            ("Goodput", "0.00"),
            ("Efficiency", "0.00%"),
        ]
        for index, (label, value) in enumerate(stat_definitions):
            card = ctk.CTkFrame(
                stats,
                corner_radius=14,
                fg_color="#0F1B2D",
                border_width=1,
                border_color="#1E334D",
            )
            card.grid(
                row=0, column=index, padx=(0 if index == 0 else 6, 0), sticky="ew"
            )
            ctk.CTkLabel(
                card,
                text=label.upper(),
                text_color="#64748B",
                font=ctk.CTkFont(size=10, weight="bold"),
            ).pack(anchor="w", padx=13, pady=(11, 2))
            value_label = ctk.CTkLabel(
                card,
                text=value,
                text_color="#F8FAFC",
                font=ctk.CTkFont(size=19, weight="bold"),
            )
            value_label.pack(anchor="w", padx=13, pady=(0, 11))
            self.stat_values[label] = value_label

        self.dashboard_tabs = ctk.CTkTabview(
            lower,
            corner_radius=16,
            fg_color="#0F1B2D",
            segmented_button_fg_color="#111F31",
            segmented_button_selected_color="#0284C7",
            segmented_button_selected_hover_color="#0369A1",
        )
        self.dashboard_tabs.grid(row=1, column=0, sticky="nsew")

        signal_tab = self.dashboard_tabs.add("PHYSICAL SIGNAL")
        events_tab = self.dashboard_tabs.add("LIVE EVENTS")
        result_tab = self.dashboard_tabs.add("RESULT")
        self.dashboard_tabs.set("PHYSICAL SIGNAL")

        signal_tab.grid_columnconfigure(0, weight=1)
        signal_tab.grid_rowconfigure(0, weight=1)
        self.signal_panel = SignalPanel(signal_tab)
        self.signal_panel.grid(row=0, column=0, sticky="nsew")

        events_tab.grid_columnconfigure(0, weight=1)
        events_tab.grid_rowconfigure(0, weight=1)
        self.log_box = ctk.CTkTextbox(
            events_tab,
            fg_color="#091321",
            text_color="#C9D7E8",
            font=("DejaVu Sans Mono", 11),
            corner_radius=10,
        )
        self.log_box.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        self.log_box.configure(state="disabled")

        result_tab.grid_columnconfigure(0, weight=1)
        result_tab.grid_rowconfigure(1, weight=1)
        self.progress = ctk.CTkProgressBar(
            result_tab,
            height=10,
            corner_radius=5,
            progress_color="#0EA5E9",
        )
        self.progress.grid(row=0, column=0, padx=12, pady=(10, 8), sticky="ew")
        self.progress.set(0)

        self.result_box = ctk.CTkTextbox(
            result_tab,
            fg_color="#091321",
            text_color="#D7E2EE",
            font=("DejaVu Sans", 12),
            corner_radius=10,
        )
        self.result_box.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self.result_box.configure(state="disabled")

    def _section_label(self, parent, text: str, row: int):
        ctk.CTkLabel(
            parent,
            text=text,
            anchor="w",
            text_color="#64748B",
            font=ctk.CTkFont(size=10, weight="bold"),
        ).grid(row=row, column=0, padx=24, pady=(4, 0), sticky="ew")

    def _update_input_mode(self, selected: str):
        if selected == "Text":
            self.message_box.configure(state="normal")
            self.file_label.configure(text_color="#475569")
            self.browse_button.configure(state="disabled")
            self.payload_size.set("4")
        else:
            self.message_box.configure(state="disabled")
            self.file_label.configure(text_color="#94A3B8")
            self.browse_button.configure(state="normal")
            self.payload_size.set("256")

    def _update_channel(self, selected: str):
        if selected == "Wired":
            self.method_menu.configure(values=["B8ZS", "HDB3"])
            self.method.set("B8ZS")
        else:
            self.method_menu.configure(values=["BPSK", "16-QAM"])
            self.method.set("BPSK")

    def _browse_file(self):
        path = filedialog.askopenfilename(title="Choose a file")
        if path:
            self.selected_file_path = path
            self.file_name_text.set(Path(path).name)

    def _read_configuration(self) -> dict:
        try:
            configuration = {
                "window_size": int(self.window_size.get()),
                "timeout_ticks": int(self.timeout_ticks.get()),
                "max_attempts": int(self.max_attempts.get()),
                "payload_size": int(self.payload_size.get()),
                "loss_rate": float(self.loss_rate.get()),
                "wired_noise_std": float(self.wired_noise_std.get()),
                "snr_db": float(self.snr_db.get()),
                "samples_per_bit": int(self.samples_per_bit.get()),
                "seed": int(self.seed.get()),
            }
        except ValueError as error:
            raise ValueError(
                "Simulation settings must contain valid numbers."
            ) from error

        if configuration["window_size"] <= 0:
            raise ValueError("Window size must be greater than zero.")
        if configuration["timeout_ticks"] <= 0:
            raise ValueError("Timeout ticks must be greater than zero.")
        if configuration["max_attempts"] <= 0:
            raise ValueError("Maximum attempts must be greater than zero.")
        if configuration["payload_size"] <= 0:
            raise ValueError("Payload size must be greater than zero.")
        if not 0 <= configuration["loss_rate"] <= 1:
            raise ValueError("Loss rate must be between 0 and 1.")
        if configuration["wired_noise_std"] < 0:
            raise ValueError("Wired noise std must be zero or greater.")

        configuration["channel"] = self.channel_type.get().lower()
        configuration["method"] = self.method.get().lower().replace("-", "")
        return configuration

    def _get_input_data(self) -> tuple[str, bytes, str, str | None]:
        if self.input_type.get() == "Text":
            message = self.message_box.get("1.0", "end").rstrip("\n")
            if not message:
                raise ValueError("Enter a message before starting the transmission.")
            return "text", text_to_bytes(message), message, None

        if not self.selected_file_path:
            raise ValueError("Choose a file before starting the transmission.")

        file_path = Path(self.selected_file_path)
        if not file_path.is_file():
            raise ValueError("The selected file does not exist.")

        data = read_file(str(file_path))
        if not data:
            raise ValueError("The selected file is empty.")

        return "file", data, file_path.name, str(file_path)

    def _start_simulation(self):
        if self.simulation_running:
            return

        try:
            configuration = self._read_configuration()
            input_type, original_data, input_name, original_path = (
                self._get_input_data()
            )
        except ValueError as error:
            messagebox.showerror("Invalid input", str(error))
            return

        encrypted_data = xor_encrypt(original_data, b"network-key")
        frames = create_frames(encrypted_data, configuration["payload_size"])

        self._prepare_dashboard(len(frames))
        self.simulation_running = True
        self.start_button.configure(state="disabled", text="TRANSMITTING...")
        self._set_status("RUNNING", "#075985")

        worker = threading.Thread(
            target=self._run_transmission,
            args=(
                frames,
                configuration,
                input_type,
                original_data,
                encrypted_data,
                input_name,
                original_path,
            ),
            daemon=True,
        )
        worker.start()

    def _run_transmission(
        self,
        frames: list[Frame],
        configuration: dict,
        input_type: str,
        original_data: bytes,
        encrypted_data: bytes,
        input_name: str,
        original_path: str | None,
    ):
        def event_callback(message: str):
            self.event_queue.put(("transmission_event", message))

        def signal_callback(signal_data: dict):
            self.event_queue.put(("signal", signal_data))

        try:
            method = configuration["method"]

            if configuration["channel"] == "wired":
                result = selective_repeat_wired(
                    frames,
                    window_size=configuration["window_size"],
                    timeout_ticks=configuration["timeout_ticks"],
                    coding_method=method,
                    wired_noise_std=configuration["wired_noise_std"],
                    loss_rate=configuration["loss_rate"],
                    max_attempts=configuration["max_attempts"],
                    seed=configuration["seed"],
                    return_status=True,
                    event_callback=event_callback,
                    signal_callback=signal_callback,
                )
            elif method == "bpsk":
                result = selective_repeat_bpsk(
                    frames,
                    window_size=configuration["window_size"],
                    timeout_ticks=configuration["timeout_ticks"],
                    snr_db=configuration["snr_db"],
                    loss_rate=configuration["loss_rate"],
                    samples_per_bit=configuration["samples_per_bit"],
                    max_attempts=configuration["max_attempts"],
                    seed=configuration["seed"],
                    return_status=True,
                    event_callback=event_callback,
                    signal_callback=signal_callback,
                )
            else:
                result = selective_repeat_qam16(
                    frames,
                    window_size=configuration["window_size"],
                    timeout_ticks=configuration["timeout_ticks"],
                    snr_db=configuration["snr_db"],
                    loss_rate=configuration["loss_rate"],
                    max_attempts=configuration["max_attempts"],
                    seed=configuration["seed"],
                    return_status=True,
                    event_callback=event_callback,
                    signal_callback=signal_callback,
                )

            self.event_queue.put(
                (
                    "result",
                    {
                        "result": result,
                        "configuration": configuration,
                        "input_type": input_type,
                        "original_data": original_data,
                        "encrypted_data": encrypted_data,
                        "input_name": input_name,
                        "original_path": original_path,
                    },
                )
            )
        except Exception as error:
            self.event_queue.put(("error", str(error)))

    def _process_event_queue(self):
        try:
            event_type, data = self.event_queue.get_nowait()
        except queue.Empty:
            self.after(40, self._process_event_queue)
            return

        if event_type == "transmission_event":
            self._handle_transmission_event(data)
            self.after(self.EVENT_DELAY_MS, self._process_event_queue)
            return

        if event_type == "signal":
            self.signal_panel.show_signal(data)
            self.after(self.EVENT_DELAY_MS, self._process_event_queue)
            return

        if event_type == "result":
            self._handle_result(data)
        elif event_type == "error":
            self._handle_error(data)

        self.after(40, self._process_event_queue)

    def _parse_event(self, message: str) -> dict:
        event = {
            "message": message,
            "type": "log",
            "frame": None,
            "attempt": None,
        }

        match = re.search(r"Sender window: (\d+) to (\d+)", message)
        if match:
            event.update(
                type="window",
                window_start=int(match.group(1)),
                window_end=int(match.group(2)),
            )
            return event

        match = re.search(r"(SEND|RETRANSMIT) frame (\d+) \(attempt (\d+)\)", message)
        if match:
            event.update(
                type="sending" if match.group(1) == "SEND" else "retransmit",
                frame=int(match.group(2)),
                attempt=int(match.group(3)),
            )
            return event

        patterns = [
            ("lost", r"Frame (\d+) lost"),
            ("timeout", r"TIMEOUT (\d+)"),
            ("ack", r"ACK (\d+)"),
            ("crc_failed", r"CRC failed for frame (\d+)"),
            ("nak", r"NAK (\d+)"),
            ("failed", r"Maximum attempts reached for frame (\d+)"),
        ]

        for event_name, pattern in patterns:
            match = re.search(pattern, message)
            if match:
                event.update(type=event_name, frame=int(match.group(1)))
                return event

        match = re.search(r"Hamming corrected blocks: (\d+)", message)
        if match:
            event.update(
                type="hamming",
                frame=self.current_frame,
                corrected_blocks=int(match.group(1)),
            )

        return event

    def _handle_transmission_event(self, message: str):
        event = self._parse_event(message)
        self._append_log(message)
        self.current_event_text.set(self._friendly_event_text(event))

        event_type = event["type"]
        sequence_number = event.get("frame")

        if event_type == "window":
            start = event["window_start"]
            end = event["window_end"]
            self.window_text.set(f"Sender window: {start} → {end}")
            self.frame_board.set_window(start, end)
            return

        if sequence_number is None:
            return

        if event_type in ("sending", "retransmit"):
            self.current_frame = sequence_number
            self.frame_board.set_state(
                sequence_number,
                event_type,
                event.get("attempt"),
            )
        elif event_type == "ack":
            self.acked_frames.add(sequence_number)
            self.frame_board.set_state(sequence_number, "ack")
            self._update_progress()
        elif event_type in ("nak", "lost", "timeout", "crc_failed", "failed"):
            self.frame_board.set_state(sequence_number, event_type)

    def _friendly_event_text(self, event: dict) -> str:
        event_type = event["type"]
        frame = event.get("frame")

        messages = {
            "window": f"Sender window moved to frames {event.get('window_start')}–{event.get('window_end')}",
            "sending": f"Sending frame {frame} — attempt {event.get('attempt')}",
            "retransmit": f"Retransmitting frame {frame} — attempt {event.get('attempt')}",
            "ack": f"Frame {frame} received successfully — ACK",
            "nak": f"Frame {frame} rejected — NAK",
            "lost": f"Frame {frame} was lost in the channel",
            "timeout": f"Frame {frame} timed out",
            "crc_failed": f"CRC check failed for frame {frame}",
            "failed": f"Frame {frame} reached the maximum attempts",
            "hamming": f"Hamming corrected {event.get('corrected_blocks')} block(s)",
        }
        return messages.get(event_type, event["message"])

    def _handle_result(self, data: dict):
        (
            received_frames,
            logs,
            total_ticks,
            retransmissions,
            corrected_blocks,
            total_transmitted_bits,
            transmission_completed,
            failed_frame,
        ) = data["result"]

        original_data = data["original_data"]
        encrypted_data = data["encrypted_data"]
        input_type = data["input_type"]
        input_name = data["input_name"]
        original_path = data["original_path"]
        configuration = data["configuration"]

        received_frame_numbers = [frame.sequence_number for frame in received_frames]
        useful_bits = sum(len(frame.payload) for frame in received_frames) * 8
        delivered_channel_bits = sum(
            len(serialize_frame(frame)) * 12 for frame in received_frames
        )
        throughput = calculate_throughput(delivered_channel_bits, total_ticks)
        goodput = calculate_goodput(useful_bits, total_ticks)
        efficiency = calculate_efficiency(goodput, throughput)

        recovered_message = None
        recovered_file = None

        if transmission_completed:
            received_encrypted_data = reassemble_frames(received_frames)
            recovered_data = xor_decrypt(received_encrypted_data, b"network-key")
            transmission_completed = (
                received_encrypted_data == encrypted_data
                and recovered_data == original_data
            )

            if transmission_completed and input_type == "text":
                recovered_message = recovered_data.decode("utf-8")
            elif transmission_completed and input_type == "file":
                recovered_file = save_recovered_file(recovered_data, original_path)

        if transmission_completed:
            self._set_status("SUCCESS", "#166534")
            self.current_event_text.set("Transmission completed successfully")
        else:
            self._set_status("INCOMPLETE", "#991B1B")
            self.current_event_text.set(
                f"Transmission stopped at frame {failed_frame}"
                if failed_frame is not None
                else "Transmission did not complete"
            )

        self.stat_values["Frames"].configure(
            text=f"{len(received_frames)} / {self.total_frames}"
        )
        self.stat_values["Ticks"].configure(text=str(total_ticks))
        self.stat_values["Retries"].configure(text=str(retransmissions))
        self.stat_values["Goodput"].configure(text=f"{goodput:.2f}")
        self.stat_values["Efficiency"].configure(text=f"{efficiency:.2f}%")

        self._write_result(
            transmission_completed=transmission_completed,
            failed_frame=failed_frame,
            received_frame_numbers=received_frame_numbers,
            input_type=input_type,
            input_name=input_name,
            recovered_message=recovered_message,
            recovered_file=recovered_file,
            configuration=configuration,
            corrected_blocks=corrected_blocks,
            total_transmitted_bits=total_transmitted_bits,
            throughput=throughput,
        )

        self.progress.set(
            len(received_frames) / self.total_frames if self.total_frames else 0
        )
        self.simulation_running = False
        self.start_button.configure(state="normal", text="START TRANSMISSION")

    def _write_result(
        self,
        transmission_completed: bool,
        failed_frame: int | None,
        received_frame_numbers: list[int],
        input_type: str,
        input_name: str,
        recovered_message: str | None,
        recovered_file: str | None,
        configuration: dict,
        corrected_blocks: int,
        total_transmitted_bits: int,
        throughput: float,
    ):
        lines = [
            f"Method: {self.method.get()}",
            f"Input: {input_name}",
            f"Received frames: {received_frame_numbers}",
        ]

        if transmission_completed:
            if input_type == "text":
                lines.append(f"Recovered: {recovered_message}")
            else:
                lines.append(f"Saved to: {recovered_file}")
            lines.append("Status: Successful")
        else:
            lines.append(f"Failed frame: {failed_frame}")
            lines.append("Status: Incomplete")
            lines.append("No partial data was reconstructed.")

        lines.extend(
            [
                "",
                f"Corrected Hamming blocks: {corrected_blocks}",
                f"Transmitted bits: {total_transmitted_bits}",
                f"Throughput: {throughput:.2f} bits/tick",
                f"Loss rate: {configuration['loss_rate']}",
            ]
        )

        if configuration["channel"] == "wired":
            lines.append(f"Wired noise std: {configuration['wired_noise_std']}")
        else:
            lines.append(f"SNR: {configuration['snr_db']} dB")

        self.result_box.configure(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", "\n".join(lines))
        self.result_box.configure(state="disabled")

    def _handle_error(self, message: str):
        self.simulation_running = False
        self.start_button.configure(state="normal", text="START TRANSMISSION")
        self._set_status("ERROR", "#991B1B")
        self.current_event_text.set("The simulation stopped because of an error")
        messagebox.showerror("Simulation error", message)

    def _prepare_dashboard(self, total_frames: int):
        self.total_frames = total_frames
        self.acked_frames.clear()
        self.current_frame = None
        self.frame_board.reset(total_frames)
        self.signal_panel.reset()
        self.dashboard_tabs.set("PHYSICAL SIGNAL")
        self.progress.set(0)
        self.window_text.set("Sender window: —")
        self.current_event_text.set("Preparing frames")
        self._clear_textbox(self.log_box)
        self._clear_textbox(self.result_box)

        self.stat_values["Frames"].configure(text=f"0 / {total_frames}")
        self.stat_values["Ticks"].configure(text="0")
        self.stat_values["Retries"].configure(text="0")
        self.stat_values["Goodput"].configure(text="0.00")
        self.stat_values["Efficiency"].configure(text="0.00%")

    def _clear_output(self):
        if self.simulation_running:
            return
        self.frame_board.reset(0)
        self.signal_panel.reset()
        self.dashboard_tabs.set("PHYSICAL SIGNAL")
        self._clear_textbox(self.log_box)
        self._clear_textbox(self.result_box)
        self.progress.set(0)
        self.window_text.set("Sender window: —")
        self.current_event_text.set("Waiting for a transmission")
        self._set_status("READY", "#334155")
        for label, value in {
            "Frames": "0 / 0",
            "Ticks": "0",
            "Retries": "0",
            "Goodput": "0.00",
            "Efficiency": "0.00%",
        }.items():
            self.stat_values[label].configure(text=value)

    def _update_progress(self):
        if self.total_frames:
            self.progress.set(len(self.acked_frames) / self.total_frames)
            self.stat_values["Frames"].configure(
                text=f"{len(self.acked_frames)} / {self.total_frames}"
            )

    def _append_log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_textbox(self, textbox):
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        textbox.configure(state="disabled")

    def _set_status(self, text: str, color: str):
        self.status_text.set(text)
        self.status_badge.configure(fg_color=color)


if __name__ == "__main__":
    app = NetworkSimulatorGUI()
    app.mainloop()
