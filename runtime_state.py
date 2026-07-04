"""
Runtime state management for the YouTube bot.

This module handles runtime-mutable state (like the user whitelist) separately
from static configuration (API keys, tokens). Runtime state is persisted to the
data/ directory, which should be mounted as a persistent volume in containerized
deployments.

Static config (env vars) is only used as an initial seed on first run.
"""

import json
import logging
import os
from pathlib import Path


class RuntimeState:
    """Manages runtime-mutable state with persistence to disk."""

    def __init__(self, data_dir: str):
        """
        Initialize runtime state manager.

        Args:
            data_dir: Path to the persistent data directory
        """
        self.data_dir = Path(data_dir)
        self.whitelist_path = self.data_dir / "whitelist.json"
        self._whitelist: set[int] = set()
        self._load_or_initialize()

    def _load_or_initialize(self):
        """Load whitelist from disk, or initialize from env vars on first run."""
        if self.whitelist_path.exists():
            # Load existing runtime state from disk
            try:
                with open(self.whitelist_path) as f:
                    data = json.load(f)
                    self._whitelist = set(data.get("user_ids", []))
                logging.info(
                    f"✅ Loaded whitelist from {self.whitelist_path}: "
                    f"{len(self._whitelist)} users"
                )
            except (OSError, json.JSONDecodeError) as e:
                logging.error(f"Failed to load whitelist from disk: {e}")
                logging.warning("Initializing empty whitelist")
                self._whitelist = set()
                self._save()
        else:
            # First run: seed from environment variable
            env_whitelist = os.getenv("WHITELIST", "")
            if env_whitelist.strip():
                try:
                    self._whitelist = {
                        int(user_id.strip())
                        for user_id in env_whitelist.split(",")
                        if user_id.strip()
                    }
                    logging.info(
                        f"🌱 Seeded whitelist from WHITELIST env var: "
                        f"{len(self._whitelist)} users"
                    )
                except ValueError as e:
                    logging.error(f"Invalid user ID in WHITELIST env var: {e}")
                    self._whitelist = set()
            else:
                logging.info("🌱 Initialized empty whitelist (no WHITELIST env var)")
                self._whitelist = set()

            # Persist the initial state
            self._save()
            logging.info(f"💾 Saved initial whitelist to {self.whitelist_path}")

    def _save(self):
        """Persist whitelist to disk."""
        try:
            # Ensure data directory exists
            self.data_dir.mkdir(parents=True, exist_ok=True)

            # Write whitelist to JSON file
            with open(self.whitelist_path, "w") as f:
                json.dump(
                    {
                        "user_ids": sorted(self._whitelist),
                        "version": 1,
                    },
                    f,
                    indent=2,
                )
        except OSError as e:
            logging.error(f"Failed to save whitelist to disk: {e}")

    def is_user_whitelisted(self, user_id: int) -> bool:
        """
        Check if a user is in the whitelist.

        Args:
            user_id: Telegram user ID

        Returns:
            True if user is whitelisted, False otherwise
        """
        return user_id in self._whitelist

    def add_user(self, user_id: int) -> bool:
        """
        Add a user to the whitelist.

        Args:
            user_id: Telegram user ID to add

        Returns:
            True if user was added, False if already in whitelist
        """
        if user_id in self._whitelist:
            return False

        self._whitelist.add(user_id)
        self._save()
        logging.info(f"➕ Added user {user_id} to whitelist")
        return True

    def remove_user(self, user_id: int) -> bool:
        """
        Remove a user from the whitelist.

        Args:
            user_id: Telegram user ID to remove

        Returns:
            True if user was removed, False if not in whitelist
        """
        if user_id not in self._whitelist:
            return False

        self._whitelist.discard(user_id)
        self._save()
        logging.info(f"➖ Removed user {user_id} from whitelist")
        return True

    def get_whitelist(self) -> list[int]:
        """
        Get a copy of the current whitelist.

        Returns:
            List of whitelisted user IDs
        """
        return sorted(self._whitelist)

    def get_whitelist_size(self) -> int:
        """
        Get the number of users in the whitelist.

        Returns:
            Number of whitelisted users
        """
        return len(self._whitelist)

    def clear_whitelist(self):
        """Remove all users from the whitelist."""
        self._whitelist.clear()
        self._save()
        logging.info("🗑️ Cleared whitelist")
