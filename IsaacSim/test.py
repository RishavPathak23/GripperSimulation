"""
creo_identify_linux_client.py
==============================
Self-contained Linux stand-in for the Windows Creo identify client.

There is no Creo on Linux, so this client simulates it end to end — the
separate test_creo_identify_publisher.py is no longer needed.

Per identify_request from Kit it will:

  1. Read the user's manual retain-list edits out of the request
     (``added_to_retain`` / ``removed_from_retain``). Empty on a first
     identify; populated on a re-identify.
  2. Write INCLUDE_PARTS.txt and EXCLUDE_PARTS.txt into the watch dir —
     always both files, even when empty, so Creo's inputs always exist.
  3. Simulate a Creo run, streaming progress lines to creo_process.log and
     to Kit (so the Geometry tab status label updates live).
  4. Produce FINAL_PARTS.csv, applying the txt files to a seed baseline:
         final = (seed | include) - exclude
     The seed stands in for "what Creo would classify on its own", so a
     first run returns it unchanged and each re-identify reflects the edits.
  5. Read FINAL_PARTS.csv back and send identify_result to Kit.
  6. Archive the run: log -> Archive/, FINAL_PARTS.csv -> Retained-Data/,
     other CSVs -> Extra-Data/. The txt files are left in place as the
     record of what Creo was last given.

A new identify_request (or an identify_cancel) supersedes any run still in
flight: its simulation stops and its result is discarded, so a stale
identify_result can never land against a newer file.

Run alongside ws_server.py:
    python3 creo_identify_linux_client.py --config creo_identify_config.json

Relevant config keys (under the "linux" section):
    identify_watch_dir   where the log, txt and csv files live
    identify_seed_csv    optional seed CSV; falls back to identify_seed_parts
    identify_seed_parts  optional list of names; falls back to a demo list
    simulate_delay          per-stage delay when pacing is off (default 0.4)
    simulate_duration_secs  total run length; 0 disables pacing (default 840)
    simulate_heartbeat_secs gap between "still processing" lines (default 30)
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import shutil
import socket
import struct
import threading
import time
from pathlib import Path
from typing import List, Optional, Set


# ── WebSocket framing ──────────────────────────────────────────────────

WS_FIN   = 0x80
WS_TEXT  = 0x01
WS_CLOSE = 0x08
WS_PING  = 0x09
WS_PONG  = 0x0A


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _recv_frame(sock):
    hdr = _recv_exact(sock, 2)
    if not hdr:
        return None
    opcode  = hdr[0] & 0x0F
    masked  = (hdr[1] & 0x80) != 0
    pay_len = hdr[1] & 0x7F
    if opcode == WS_CLOSE:
        return None
    if opcode in (WS_PING, WS_PONG):
        return b""
    if pay_len == 126:
        pay_len = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif pay_len == 127:
        pay_len = struct.unpack("!Q", _recv_exact(sock, 8))[0]
    mask_key = _recv_exact(sock, 4) if masked else None
    payload  = _recv_exact(sock, pay_len)
    if payload is None:
        return None
    if masked and mask_key:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    return payload


def _make_frame(payload: bytes) -> bytes:
    frame = bytearray()
    frame.append(WS_FIN | WS_TEXT)
    n = len(payload)
    mask_key = os.urandom(4)
    if n < 126:
        frame.append(0x80 | n)
    elif n < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack("!H", n))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack("!Q", n))
    frame.extend(mask_key)
    frame.extend(bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload)))
    return bytes(frame)


def _handshake(sock, host, port) -> bool:
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET / HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(req.encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        chunk = sock.recv(1024)
        if not chunk:
            print(f"[CreoIdentify] Handshake closed early, got {resp!r}")
            return False
        resp += chunk
    return b"101" in resp


# ── Names and constants ────────────────────────────────────────────────

LOG_NAME        = "creo_process.log"
INCLUDE_TXT     = "INCLUDE_PARTS.txt"
EXCLUDE_TXT     = "EXCLUDE_PARTS.txt"
FINAL_CSV       = "FINAL_PARTS.csv"
CSV_COLUMN      = "Component Name"
COMPLETION_LINE = "Creo identification process complete."

# Stands in for what Creo would classify with no user input. Overridden by
# identify_seed_csv or identify_seed_parts in the config.
DEFAULT_SEED_PARTS = [
    "ENGINE_BLOCK",
    "CRANK_SHAFT",
    "OIL_PAN",
    "VALVE_COVER",
    "VALVE_COVER_1",
]

SIM_LOG_LINES = [
    "Creo Parametric identification starting...",
    "Loading assembly model...",
    "Reading INCLUDE_PARTS.txt / EXCLUDE_PARTS.txt...",
    "Analysing part materials...",
    "Checking design constraints...",
    "Running GIS simulation pre-check...",
    "Identifying conductor components...",
    "Identifying insulator components...",
    "Classification complete.",
    "Generating output report...",
    "Writing CSV file...",
]

# Real Creo takes 12-15 minutes, so the simulation is stretched to match by
# default. Milestones are spread evenly across the duration and a heartbeat is
# emitted in between, otherwise the log would sit silent for ~75s at a stretch.
# Set simulate_duration_secs to 0 (or pass --fast) for quick testing.
DEFAULT_SIM_DURATION_SECS  = 0.0   # 14 minutes  840.0
DEFAULT_SIM_HEARTBEAT_SECS = 30.0

# Set only on Ctrl+C. Per-run cancellation uses each run's own event.
_shutdown = threading.Event()


# ── Small file helpers ─────────────────────────────────────────────────

def _clean(val) -> str:
    """Strip whitespace and stray quotes off a config or request value."""
    return (val or "").strip().strip("'\"")


def _move_file(src: str, dest_dir: str) -> None:
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(src))
    if os.path.exists(dest):
        os.remove(dest)
    shutil.move(src, dest)
    print(f"[CreoIdentify] Moved: {src} -> {dest}")


def read_parts_csv(csv_path: str) -> List[str]:
    """Read the Component Name column, tolerating common header variants."""
    parts: List[str] = []
    try:
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                name = (
                    row.get("Component Name")
                    or row.get("component name")
                    or row.get("ComponentName")
                    or row.get("COMPONENT NAME")
                    or row.get("Part Name")
                    or row.get("part name")
                )
                if name and name.strip():
                    parts.append(name.strip())
    except Exception as e:
        print(f"[CreoIdentify] ERROR reading {csv_path}: {e}")
    return parts


def write_parts_txt(path: str, parts: List[str], header: str) -> None:
    """Write one part name per line. Always written, even when empty."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {header}\n")
            f.write(f"# generated {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            for p in parts:
                f.write(p + "\n")
        print(f"[CreoIdentify] Wrote {os.path.basename(path)} "
              f"({len(parts)} part(s))")
    except Exception as e:
        print(f"[CreoIdentify] ERROR writing {path}: {e}")


def write_final_csv(path: str, parts: List[str]) -> None:
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([CSV_COLUMN, "Source"])
            for p in parts:
                w.writerow([p, "creo_sim"])
        print(f"[CreoIdentify] Wrote {os.path.basename(path)} "
              f"({len(parts)} part(s))")
    except Exception as e:
        print(f"[CreoIdentify] ERROR writing {path}: {e}")


def load_seed_parts(config: dict) -> List[str]:
    """Baseline 'what Creo finds on its own': CSV, config list, or demo."""
    seed_csv = _clean(config.get("identify_seed_csv"))
    if seed_csv and os.path.exists(seed_csv):
        parts = read_parts_csv(seed_csv)
        if parts:
            print(f"[CreoIdentify] Seed from CSV {seed_csv}: "
                  f"{len(parts)} part(s)")
            return parts
        print(f"[CreoIdentify] Seed CSV had no usable rows: {seed_csv}")
    elif seed_csv:
        print(f"[CreoIdentify] Seed CSV not found: {seed_csv}")

    listed = config.get("identify_seed_parts")
    if isinstance(listed, list) and listed:
        parts = [str(p).strip() for p in listed if str(p).strip()]
        print(f"[CreoIdentify] Seed from config list: {len(parts)} part(s)")
        return parts

    print(f"[CreoIdentify] Seed from built-in demo list: "
          f"{len(DEFAULT_SEED_PARTS)} part(s)")
    return list(DEFAULT_SEED_PARTS)


def archive_run(watch_dir: str, log_path: str, final_csv: str) -> None:
    """Log -> Archive/, FINAL_PARTS.csv -> Retained-Data/, rest -> Extra-Data/.

    The txt files stay put as the record of what Creo was last given.
    """
    archive_dir  = os.path.join(watch_dir, "Archive")
    retained_dir = os.path.join(watch_dir, "Retained-Data")
    extra_dir    = os.path.join(watch_dir, "Extra-Data")
    try:
        if log_path and os.path.exists(log_path):
            _move_file(log_path, archive_dir)
        for csv_file in Path(watch_dir).glob("*.csv"):
            s = str(csv_file)
            if final_csv and os.path.abspath(s) == os.path.abspath(final_csv):
                _move_file(s, retained_dir)
            else:
                _move_file(s, extra_dir)
    except Exception as e:
        print(f"[CreoIdentify] Archive error: {e}")


# ── Simulation ─────────────────────────────────────────────────────────

def _elapsed_str(started: float) -> str:
    """'3m 20s' style elapsed time for heartbeat lines."""
    secs = int(time.time() - started)
    return f"{secs // 60}m {secs % 60:02d}s" if secs >= 60 else f"{secs}s"


def _paced_wait(cancel: threading.Event, total: float,
                heartbeat: float, on_heartbeat) -> bool:
    """Wait ``total`` seconds, calling ``on_heartbeat`` every ``heartbeat``.

    Waits in 1s chunks so cancellation is picked up promptly. Returns False if
    cancelled or shutting down, True if the full wait completed.
    """
    if total <= 0:
        return not (cancel.is_set() or _shutdown.is_set())
    waited = 0.0
    since_beat = 0.0
    while waited < total:
        chunk = min(1.0, total - waited)
        cancel.wait(timeout=chunk)
        if cancel.is_set() or _shutdown.is_set():
            return False
        waited += chunk
        since_beat += chunk
        if heartbeat > 0 and since_beat >= heartbeat and waited < total:
            since_beat = 0.0
            try:
                on_heartbeat()
            except Exception:
                pass
    return True


def compute_final_parts(seed: List[str],
                        include: List[str],
                        exclude: List[str]) -> List[str]:
    """final = (seed | include) - exclude, order-stable.

    Mirrors how Creo consumes the two txt files: additions are honoured,
    exclusions win over inclusions.
    """
    excl: Set[str] = set(exclude)
    out: List[str] = []
    seen: Set[str] = set()
    for name in list(seed) + list(include):
        if name in excl or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


# ── Client ─────────────────────────────────────────────────────────────

class CreoIdentifyLinuxClient:

    def __init__(self, host: str, port: int, config: dict):
        self.host     = host
        self.port     = port
        self.config   = config
        self._sock    = None
        self._running = False

        self._lock       = threading.Lock()
        self._run_seq    = 0
        self._active_id  = 0
        self._active_evt: Optional[threading.Event] = None

    # -- sending -------------------------------------------------------

    def _send_on(self, sock, msg: dict) -> None:
        if sock is None:
            return
        try:
            sock.sendall(_make_frame(json.dumps(msg).encode()))
        except Exception as e:
            print(f"[CreoIdentify] Send failed: {e}")

    def _send(self, msg: dict) -> None:
        self._send_on(self._sock, msg)

    def _send_for(self, run_id: int, sock, msg: dict) -> None:
        """Send only while this run is still the active one."""
        with self._lock:
            if self._active_id != run_id:
                return
        self._send_on(sock or self._sock, msg)

    # -- run lifecycle -------------------------------------------------

    def _cancel_active(self, reason: str) -> None:
        with self._lock:
            evt, rid = self._active_evt, self._active_id
            self._active_evt = None
            self._active_id  = 0
        if evt is not None and not evt.is_set():
            print(f"[CreoIdentify] Cancelling run {rid} ({reason})")
            evt.set()

    def _start_run(self, request: dict) -> None:
        self._cancel_active("superseded by new identify_request")
        with self._lock:
            self._run_seq += 1
            run_id = self._run_seq
            evt = threading.Event()
            self._active_id  = run_id
            self._active_evt = evt
        threading.Thread(
            target=self._run_identification,
            args=(request, self._sock, run_id, evt),
            daemon=True,
            name=f"identify-{run_id}",
        ).start()
        print(f"[CreoIdentify] Started run {run_id}")

    def _on_message(self, msg: dict) -> None:
        mtype = msg.get("type")
        print(f"[CreoIdentify] Received: {mtype}")
        if mtype == "identify_request":
            self._start_run(msg)
        elif mtype == "identify_cancel":
            self._cancel_active("cancel requested by Kit")

    def start_monitoring_now(self) -> None:
        print("[CreoIdentify] Immediate run (test mode)")
        self._start_run({})

    # -- the work ------------------------------------------------------

    def _run_identification(self, request: dict, sock,
                            run_id: int, cancel: threading.Event) -> None:
        tag = f"run {run_id}"
        watch_dir = (_clean(self.config.get("identify_watch_dir"))
                     or _clean(self.config.get("identify_output_dir"))
                     or ".")
        delay     = float(self.config.get("simulate_delay", 0.15))
        duration  = float(self.config.get("simulate_duration_secs",
                                          DEFAULT_SIM_DURATION_SECS))
        heartbeat = float(self.config.get("simulate_heartbeat_secs",
                                          DEFAULT_SIM_HEARTBEAT_SECS))
        log_path  = os.path.join(watch_dir, LOG_NAME)
        final_csv = os.path.join(watch_dir, FINAL_CSV)

        def stopped() -> bool:
            return cancel.is_set() or _shutdown.is_set()

        def emit(line: str) -> None:
            """Append to the log and stream to Kit's status label."""
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception as e:
                print(f"[CreoIdentify] {tag}: log write failed: {e}")
            print(f"[CreoIdentify] {tag} LOG: {line}")
            self._send_for(run_id, sock,
                           {"type": "identify_log", "message": line})

        try:
            os.makedirs(watch_dir, exist_ok=True)

            working_dir   = (_clean(request.get("working_dir"))
                             or _clean(self.config.get("creo_working_dir")))
            assembly_file = (_clean(request.get("assembly_file"))
                             or _clean(self.config.get("creo_assembly_file")))

            # The user's manual retain-list edits. Absent on a first identify.
            include = [str(p).strip() for p in
                       (request.get("added_to_retain") or []) if str(p).strip()]
            exclude = [str(p).strip() for p in
                       (request.get("removed_from_retain") or []) if str(p).strip()]

            print(f"[CreoIdentify] {tag}: working_dir   = {working_dir}")
            print(f"[CreoIdentify] {tag}: assembly_file = {assembly_file}")
            print(f"[CreoIdentify] {tag}: include={include or '(none)'}")
            print(f"[CreoIdentify] {tag}: exclude={exclude or '(none)'}")

            # Fresh log so a stale one can't be mistaken for this run's output.
            try:
                open(log_path, "w").close()
            except Exception as e:
                print(f"[CreoIdentify] {tag}: could not clear log: {e}")

            # ── Always write both txt files, empty or not ──────────────
            write_parts_txt(
                os.path.join(watch_dir, INCLUDE_TXT), include,
                "INCLUDE_PARTS - parts the user added to the retain list",
            )
            write_parts_txt(
                os.path.join(watch_dir, EXCLUDE_TXT), exclude,
                "EXCLUDE_PARTS - parts the user removed from the retain list",
            )
            if stopped():
                print(f"[CreoIdentify] {tag}: cancelled after writing txt")
                return

            # ── Simulate the Creo run ─────────────────────────────────
            # Paced to duration_secs so the whole thing lands in the same
            # ballpark as real Creo. Waits are chunked, so a cancel still
            # takes effect within a second rather than at the next milestone.
            started = time.time()
            if duration > 0:
                slice_secs = duration / float(len(SIM_LOG_LINES))
                print(f"[CreoIdentify] {tag}: pacing over "
                      f"{duration:.0f}s (~{slice_secs:.0f}s per stage)")
            else:
                slice_secs = delay
                print(f"[CreoIdentify] {tag}: fast mode, {delay}s per stage")

            for idx, line in enumerate(SIM_LOG_LINES, start=1):
                if not _paced_wait(cancel, slice_secs, heartbeat,
                                   lambda: emit(
                                       f"... stage {idx}/{len(SIM_LOG_LINES)} "
                                       f"still processing "
                                       f"({_elapsed_str(started)} elapsed)")):
                    print(f"[CreoIdentify] {tag}: cancelled during simulation")
                    return
                emit(line)

            seed  = load_seed_parts(self.config)
            final = compute_final_parts(seed, include, exclude)
            write_final_csv(final_csv, final)

            emit(f"OUTPUT_CSV_PATH:{final_csv}")
            emit(COMPLETION_LINE)

            if stopped():
                print(f"[CreoIdentify] {tag}: cancelled before reading CSV")
                return

            # ── Read the CSV back, as the Windows client does ──────────
            parts = read_parts_csv(final_csv)
            print(f"[CreoIdentify] {tag}: read {len(parts)} part(s) from "
                  f"{os.path.basename(final_csv)}")

            if not parts:
                self._send_for(run_id, sock, {
                    "type": "identify_error",
                    "message": f"No parts found in {CSV_COLUMN} column",
                })
                archive_run(watch_dir, log_path, final_csv)
                return

            if stopped():
                print(f"[CreoIdentify] {tag}: cancelled before send")
                return

            print(f"[CreoIdentify] {tag}: sending {len(parts)} parts to Kit")
            self._send_for(run_id, sock, {
                "type":         "identify_result",
                "retain_parts": parts,
                "csv_path":     final_csv,
            })
            print(f"[CreoIdentify] {tag}: identify_result sent")

            archive_run(watch_dir, log_path, final_csv)

        except Exception as e:
            print(f"[CreoIdentify] {tag}: ERROR {e}")
            self._send_for(run_id, sock,
                           {"type": "identify_error", "message": str(e)})
            archive_run(watch_dir, log_path, final_csv)

        finally:
            with self._lock:
                if self._active_id == run_id:
                    self._active_id  = 0
                    self._active_evt = None

    # -- connection ----------------------------------------------------

    def run(self) -> None:
        self._running = True
        while self._running and not _shutdown.is_set():
            try:
                print(f"[CreoIdentify] Connecting to "
                      f"ws://{self.host}:{self.port}")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((self.host, self.port))
                sock.settimeout(None)
                if not _handshake(sock, self.host, self.port):
                    print("[CreoIdentify] Handshake failed")
                    sock.close()
                    time.sleep(3)
                    continue

                self._sock = sock
                print("[CreoIdentify] Connected — registering as creo_identify")
                self._send({"type": "register", "role": "creo_identify"})

                while self._running and not _shutdown.is_set():
                    frame = _recv_frame(sock)
                    if frame is None:
                        print("[CreoIdentify] Connection lost")
                        break
                    if not frame:
                        continue
                    try:
                        self._on_message(json.loads(frame.decode("utf-8")))
                    except Exception as e:
                        print(f"[CreoIdentify] Bad message: {e}")

            except Exception as e:
                print(f"[CreoIdentify] Connection error: {e}")
            finally:
                self._sock = None
                if self._running and not _shutdown.is_set():
                    print("[CreoIdentify] Reconnecting in 3s...")
                    time.sleep(3)

    def stop(self) -> None:
        self._running = False
        _shutdown.set()
        self._cancel_active("client shutting down")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Self-contained Creo Identify client for Linux"
    )
    parser.add_argument("--config",      default="creo_identify_config.json")
    parser.add_argument("--host",        default=None)
    parser.add_argument("--port",        default=None, type=int)
    parser.add_argument("--seed-csv",    default=None,
                        help="Override identify_seed_csv")
    parser.add_argument("--monitor-now", action="store_true",
                        help="Run once immediately without waiting for Kit")
    parser.add_argument("--fast", action="store_true",
                        help="Skip the 12-15 min pacing (for quick testing)")
    args = parser.parse_args()

    config = {}
    if os.path.exists(args.config):
        with open(args.config) as f:
            config = json.load(f)
        print(f"[CreoIdentify] Config loaded: {args.config}")
    else:
        print(f"[CreoIdentify] Config not found: {args.config} — using defaults")

    host = args.host or config.get("server", {}).get("host", "localhost")
    port = args.port or config.get("server", {}).get("port", 9001)

    os_mode = config.get("os_mode", "linux")
    print(f"[CreoIdentify] OS mode: {os_mode}")
    flat = {**config, **config.get(os_mode, {})}
    if args.seed_csv:
        flat["identify_seed_csv"] = args.seed_csv
    if args.fast:
        flat["simulate_duration_secs"] = 0
        print("[CreoIdentify] --fast: pacing disabled")

    client = CreoIdentifyLinuxClient(host, port, flat)
    try:
        if args.monitor_now:
            client.start_monitoring_now()
        client.run()
    except KeyboardInterrupt:
        print("[CreoIdentify] Stopping...")
        client.stop()
        print("[CreoIdentify] Stopped")


if __name__ == "__main__":
    main()
