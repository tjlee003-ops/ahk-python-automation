"""Application entry point."""

from python.file_manager import ensure_dirs
from python.engine.bundle_manager import ensure_reference_bundle


def main():
    ensure_dirs()
    ensure_reference_bundle()

    # Generate user guide HTML
    from python.engine.guide_generator import generate
    generate()

    # Start API server in background
    from python.api.server import start_server
    start_server()

    # Connect AHK bridge (non-blocking)
    from python.engine.ahk_bridge import get_bridge
    get_bridge().connect()

    # Start backup scheduler
    from python.engine.backup_manager import get_scheduler
    get_scheduler().start()

    # Launch GUI (blocks until window closed)
    from python.gui.app_shell import launch
    launch()


if __name__ == "__main__":
    main()
