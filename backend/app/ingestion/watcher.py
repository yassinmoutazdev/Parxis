"""Vault Watcher for monitoring Obsidian vault changes.

Corresponds to ARCHITECTURE Section 3 (ADR-11) - Vault Watcher event normalization.

The VaultWatcher normalizes file system events from watchdog into a single
handle_event() entry point with debouncing and hash-based deduplication.
"""

import hashlib
import logging
import threading
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.config import settings

logger = logging.getLogger(__name__)


class VaultWatcher:
    """Watches the Obsidian vault for file changes.

    Corresponds to ARCHITECTURE Section 6.1 (Vault Watcher sequence diagram).

    Attributes:
        vault_path: The path to the Obsidian vault
        debounce_seconds: Time window for coalescing multiple events
        event_handler: Callback function for processed events
    """

    def __init__(
        self,
        vault_path: Path | None = None,
        debounce_seconds: float | None = None,
        event_handler: Callable[[str], None] | None = None,
    ):
        """Initialize the VaultWatcher.

        Args:
            vault_path: Path to the Obsidian vault (defaults to settings.vault_path)
            debounce_seconds: Debounce window in seconds (defaults to settings.watcher_debounce_seconds)
            event_handler: Callback function called with the file path on processed events
        """
        self.vault_path = vault_path or settings.vault_path
        self.debounce_seconds = debounce_seconds or settings.watcher_debounce_seconds
        self.event_handler = event_handler

        # Debounce state: {path: last_event_time}
        self._debounce_state: dict[str, float] = {}
        self._debounce_lock = threading.Lock()

        # The watchdog observer and handler
        self._observer: Observer | None = None
        self._handler: _VaultEventHandler | None = None

    def start(self) -> bool:
        """Start watching the vault.

        Returns:
            True if watcher started successfully, False if vault_path doesn't exist

        Note:
            If vault_path doesn't exist, logs a warning and returns False,
            but leaves the API functional per Architecture Section 11.1.
        """
        if not self.vault_path.exists():
            logger.warning(
                f"Vault path does not exist: {self.vault_path}. "
                "Watcher not started - API remains functional."
            )
            return False

        if not self.vault_path.is_dir():
            logger.warning(
                f"Vault path is not a directory: {self.vault_path}. "
                "Watcher not started - API remains functional."
            )
            return False

        logger.info(f"Starting VaultWatcher for: {self.vault_path}")

        # Create the event handler - use self.handle_event as the callback
        self._handler = _VaultEventHandler(
            debounce_seconds=self.debounce_seconds,
            debounce_state=self._debounce_state,
            debounce_lock=self._debounce_lock,
            on_event=self.handle_event,
        )

        # Create and start the observer
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.vault_path), recursive=True)
        self._observer.start()

        logger.info("VaultWatcher started successfully")
        return True

    def stop(self) -> None:
        """Stop the VaultWatcher."""
        if self._observer:
            logger.info("Stopping VaultWatcher...")
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            self._handler = None
            logger.info("VaultWatcher stopped")

    def _dispatch_event(self, path: str) -> None:
        """Dispatch a debounced event to the handler.

        Args:
            path: The file path that triggered the event
        """
        if self.event_handler:
            try:
                self.event_handler(path)
            except Exception as e:
                logger.error(f"Error in event_handler for {path}: {e}")
        else:
            logger.debug(f"Debounced event for: {path}")

    def handle_event(self, path: str) -> None:
        """Handle a normalized file system event.

        Corresponds to ARCHITECTURE Section 6.1 (handle_event sequence step).

        This method:
        1. Computes content_hash
        2. Compares against existing Note.content_hash (no-op on match)
        3. Upserts Note row
        4. Calls IngestionService.process_note()

        Args:
            path: The file path that triggered the event
        """
        # Import here to avoid circular imports
        from app.db.engine import Session
        from app.db.models.note import Note
        from app.db.models.system import NoteStatus
        from app.ingestion.service import IngestionService

        logger.info(f"Handling event for: {path}")

        # Read and hash the file content
        file_path = Path(path)
        if not file_path.exists():
            logger.warning(f"File no longer exists: {path}")
            return

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Check if Note exists and compare hash
        with Session() as session:
            note = session.query(Note).filter(Note.vault_path == path).first()

            if note:
                # Check if content changed
                if note.content_hash == content_hash:
                    logger.debug(f"Content unchanged for: {path}")
                    return

                # Check if already processed - write-once model
                if note.status == NoteStatus.PROCESSED:
                    logger.info(f"Note already processed, marking changed: {path}")
                    note.changed_since_processed = True
                    session.commit()
                    return

                # Update existing note hash
                note.content_hash = content_hash
            else:
                # Create new note
                note = Note(
                    vault_path=path,
                    content_hash=content_hash,
                    status=NoteStatus.NEW,
                )
                session.add(note)

            session.commit()
            note_id = note.id

        # Process the note through ingestion
        logger.info(f"Processing note: {path} (id: {note_id})")
        try:
            IngestionService.process_note(note_id)
        except Exception as e:
            logger.error(f"Error processing note {path}: {e}")


class _VaultEventHandler(FileSystemEventHandler):
    """Internal event handler for watchdog events.

    Normalizes on_created, on_modified, on_moved events into a single
    debounced handler call.
    """

    def __init__(
        self,
        debounce_seconds: float,
        debounce_state: dict[str, float],
        debounce_lock: threading.Lock,
        on_event: Callable[[str], None],
    ):
        """Initialize the event handler.

        Args:
            debounce_seconds: Time window for debouncing
            debounce_state: Shared debounce state dict
            debounce_lock: Lock for thread-safe debounce state access
            on_event: Callback for debounced events
        """
        super().__init__()
        self._debounce_seconds = debounce_seconds
        self._debounce_state = debounce_state
        self._debounce_lock = debounce_lock
        self._on_event = on_event

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if not event.is_directory:
            self._handle_event(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if not event.is_directory:
            self._handle_event(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move/rename events."""
        if not event.is_directory:
            # Handle both src and dest paths for moves
            self._handle_event(event.src_path)
            if event.dest_path:
                self._handle_event(event.dest_path)

    def _handle_event(self, path: str) -> None:
        """Handle a raw event with debouncing.

        Corresponds to ARCHITECTURE Section 6.1 (debounce step).

        Args:
            path: The file path that triggered the event
        """
        import time

        # Filter to markdown files only
        if not path.endswith(".md"):
            return

        with self._debounce_lock:
            current_time = time.time()
            last_time = self._debounce_state.get(path, 0)

            # Check if within debounce window
            if current_time - last_time < self._debounce_seconds:
                logger.debug(f"Debouncing event for: {path}")
                return

            # Update last event time
            self._debounce_state[path] = current_time

        # Dispatch the event
        logger.debug(f"Dispatching event for: {path}")
        self._on_event(path)


# Module-level singleton for convenience
_vault_watcher: VaultWatcher | None = None


def get_vault_watcher() -> VaultWatcher:
    """Get the module-level VaultWatcher instance.

    Returns:
        The VaultWatcher instance
    """
    global _vault_watcher
    if _vault_watcher is None:
        _vault_watcher = VaultWatcher()
    return _vault_watcher
