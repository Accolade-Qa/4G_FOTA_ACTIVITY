"""Continuous FOTA Utility Application CLI Entry Point.

Headless Command Line Interface (CLI) runner for Continuous FOTA Automation.
Supports command-line arguments (--port, --baud, --state, --list-ports, --non-interactive),
interactive console menus, timestamped serial stream logging, 10-stage pipeline validation,
and automatic CSV audit logging (results/fota_results.csv).
"""

import os
import sys
import time
import logging
import argparse
from pathlib import Path

# Ensure repo root directory is at the top of sys.path
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.path_resolver import get_base_dir
from backend.config import Config
from backend.serial_worker import SerialWorker
from backend.orchestrator import FotaOrchestrator
from backend.session_logger import SessionLogger

BASE_DIR = get_base_dir()

# Setup logging
logs_dir = BASE_DIR / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
log_file = logs_dir / "fota_activity.log"

file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"))

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"))

logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler], force=True)
logger = logging.getLogger("main")


def print_banner() -> None:
    banner = """
====================================================================
               AEPL CONTINUOUS FOTA AUTOMATION UTILITY              
====================================================================
"""
    print(banner)


def list_ports_and_exit() -> None:
    ports = SerialWorker.list_detailed_ports()
    print_banner()
    if not ports:
        print("No serial COM ports detected.")
    else:
        print("Connected Serial COM Ports:")
        for idx, p in enumerate(ports, start=1):
            print(f"  [{idx}] {p.display_text} (HWID: {p.hwid})")
    sys.exit(0)


def prompt_port_selection(serial_worker_cls) -> str:
    detailed_ports = serial_worker_cls.list_detailed_ports()
    if not detailed_ports:
        print("\n❌ No serial COM ports detected on system. Please connect hardware and retry.")
        sys.exit(1)

    if len(detailed_ports) == 1:
        selected = detailed_ports[0].device
        print(f"\n✓ Auto-selected single COM Port: {detailed_ports[0].display_text}")
        return selected

    print("\nAvailable COM Ports:")
    for idx, p in enumerate(detailed_ports, start=1):
        print(f"  [{idx}] {p.display_text}")

    while True:
        try:
            choice = input(f"\nSelect COM Port (1-{len(detailed_ports)}) [Default 1]: ").strip()
            if not choice:
                return detailed_ports[0].device
            val = int(choice)
            if 1 <= val <= len(detailed_ports):
                return detailed_ports[val - 1].device
            print(f"Invalid choice. Please enter a number between 1 and {len(detailed_ports)}.")
        except (ValueError, KeyboardInterrupt):
            sys.exit(0)


def prompt_state_selection(orchestrator: FotaOrchestrator, default_state: str) -> str:
    all_states = list(orchestrator.resolver.get_all_states())
    if not all_states:
        return default_state or "Bihar"

    print("\nAvailable Target States in Matrix:")
    for idx, st in enumerate(all_states, start=1):
        def_tag = " (Default)" if st.lower() == (default_state or "").lower() else ""
        print(f"  [{idx}] {st}{def_tag}")

    while True:
        try:
            choice = input(f"\nSelect Target State [Default {default_state or all_states[0]}]: ").strip()
            if not choice:
                return default_state or all_states[0]
            val = int(choice)
            if 1 <= val <= len(all_states):
                return all_states[val - 1]
            print(f"Invalid choice. Please enter a number between 1 and {len(all_states)}.")
        except (ValueError, KeyboardInterrupt):
            sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AEPL Continuous FOTA Automation CLI Utility",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("-p", "--port", type=str, help="Serial COM port name (e.g. COM5)")
    parser.add_argument("-b", "--baud", type=int, help="Serial baud rate (default: 115200)")
    parser.add_argument("-s", "--state", type=str, help="Target state for server matrix validation (e.g. Maharashtra)")
    parser.add_argument("-l", "--list-ports", action="store_true", help="List all connected COM ports hardware & exit")
    parser.add_argument("-n", "--non-interactive", action="store_true", help="Disable interactive prompts (batch mode)")
    parser.add_argument("-u", "--user", type=str, help="User ID override for REST API calls")
    parser.add_argument("-c", "--config", type=str, help="Path to custom .env file")

    args = parser.parse_args()

    if args.list_ports:
        list_ports_and_exit()

    print_banner()

    # Load configuration
    config = Config(base_dir=BASE_DIR)
    if args.user:
        os.environ["USER_ID"] = args.user

    session_logger = SessionLogger(config.logs_dir)

    # Instantiate Orchestrator
    orchestrator = FotaOrchestrator(config=config)
    orchestrator.initialize_system()

    # Determine Port, Baud, and State
    baud_rate = args.baud or config.serial_baud or 115200

    if args.port:
        target_port = args.port
    elif args.non_interactive or config.serial_port:
        target_port = config.serial_port or (SerialWorker.list_available_ports()[0] if SerialWorker.list_available_ports() else "")
    else:
        target_port = prompt_port_selection(SerialWorker)

    if args.state:
        target_state = args.state
    elif args.non_interactive:
        target_state = config.default_state or "Bihar"
    else:
        target_state = prompt_state_selection(orchestrator, config.default_state)

    logger.info("Configuration: Port=%s, Baud=%d, State=%s", target_port, baud_rate, target_state)
    print(f"\n====================================================================")
    print(f"  Target COM Port: {target_port}")
    print(f"  Baud Rate:       {baud_rate}")
    print(f"  Target State:    {target_state}")
    print(f"  Activity Log:    {log_file}")
    print(f"  Serial Log:      {session_logger.master_log_path}")
    print(f"  Results Output:  {config.audit_csv_path}")
    print(f"====================================================================\n")

    # Wire Orchestrator Callbacks
    def on_status(msg: str) -> None:
        logger.info("[STATUS] %s", msg)

    def on_progress(prog: float) -> None:
        logger.info("[FOTA PROGRESS] %.2f%%", prog)

    def on_stage_change(stage: int, status: str, msg: str) -> None:
        logger.info("[STAGE %d/10] [%s] %s", stage, status, msg)

    def on_request_command(cmd: str) -> None:
        if serial_worker:
            serial_worker.send_command(cmd)

    def on_audit_record(rec) -> None:
        logger.info("[AUDIT RESULT] UIN=%s, Initial=%s, Target=%s, Status=%s, Remarks=%s",
                    rec.uin, rec.initial_version, rec.final_version, rec.status, rec.remarks)

    orchestrator.on_status = on_status
    orchestrator.on_progress = on_progress
    orchestrator.on_stage_change = on_stage_change
    orchestrator.on_request_command = on_request_command
    orchestrator.on_audit_record = on_audit_record

    # Wire Serial Worker Callbacks
    def on_raw_log(line: str) -> None:
        session_logger.write_lines([line])
        orchestrator.process_log_line(line)

    def on_login_packet(pkt) -> None:
        session_logger.update_session_info(pkt.imei, pkt.version)
        orchestrator.process_login_packet(pkt, selected_ui_state=target_state)

    def on_port_status(connected: bool, msg: str) -> None:
        if connected:
            logger.info("[SERIAL PORT] %s", msg)
        else:
            logger.error("[SERIAL PORT ERROR] %s", msg)

    serial_worker = SerialWorker(
        port_name=target_port,
        baud_rate=baud_rate,
        on_raw_log=on_raw_log,
        on_login_packet=on_login_packet,
        on_port_status=on_port_status,
        on_progress=on_progress,
    )

    logger.info("Starting Serial Worker thread...")
    serial_worker.start()

    print("Press Ctrl+C to terminate application.\n")

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\nTermination request received (Ctrl+C). Shutting down...")
        logger.info("User requested shutdown. Stopping serial worker...")
        serial_worker.stop()
        if orchestrator.poller_worker:
            orchestrator.poller_worker.stop()
        print("Shutdown complete. Goodbye.")


if __name__ == "__main__":
    main()
