#!/usr/bin/env python
"""
Migration script to help transition from the original LLMHandler to the LangGraph-based implementation.

This script:
1. Makes a backup of the original settings
2. Updates the settings to use LangGraph
3. Provides guidance on how to switch between implementations
"""

import os
import json
import shutil
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Dasi Migration")


def backup_settings(config_dir):
    """Backup the current settings."""
    settings_path = Path(config_dir) / "settings.json"
    if not settings_path.exists():
        logger.warning(f"Settings file not found at {settings_path}")
        return False

    # Create backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(config_dir) / f"settings_backup_{timestamp}.json"

    try:
        shutil.copy(settings_path, backup_path)
        logger.info(f"Settings backed up to {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to backup settings: {e}")
        return False


def update_settings(config_dir, enable_langgraph):
    """Update settings to use LangGraph."""
    settings_path = Path(config_dir) / "settings.json"
    if not settings_path.exists():
        logger.warning(f"Settings file not found at {settings_path}")
        return False

    try:
        # Read existing settings
        with open(settings_path, 'r') as f:
            settings = json.load(f)

        # Update settings to use LangGraph
        if 'general' not in settings:
            settings['general'] = {}

        settings['general']['use_langgraph'] = enable_langgraph

        # Write updated settings
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)

        logger.info(f"Settings updated: use_langgraph = {enable_langgraph}")
        return True
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        return False


def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(
        description="Migrate Dasi to use LangGraph"
    )
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Enable LangGraph (default is to disable)"
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        default=os.path.expanduser("~/.config/dasi"),
        help="Path to Dasi config directory (default: ~/.config/dasi)"
    )

    args = parser.parse_args()

    logger.info(
        f"Starting migration {'to' if args.enable else 'from'} LangGraph")

    # Ensure config directory exists
    config_dir = Path(args.config_dir)
    if not config_dir.exists():
        logger.error(f"Config directory not found: {config_dir}")
        return 1

    # Backup settings
    if not backup_settings(config_dir):
        return 1

    # Update settings
    if not update_settings(config_dir, args.enable):
        return 1

    # Print success message
    if args.enable:
        logger.info("Successfully migrated to LangGraph!")
        logger.info("Restart Dasi for changes to take effect.")
        logger.info(
            "If you encounter any issues, you can revert with: python migrate_to_langgraph.py")
    else:
        logger.info("Successfully reverted to original implementation!")
        logger.info("Restart Dasi for changes to take effect.")

    return 0


if __name__ == "__main__":
    exit(main())
