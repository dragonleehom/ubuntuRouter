"""StorageManager - unified entry for disk, SMART, and mount management"""

from . import disk, smart, mount


class StorageManager:
    """Unified entry point for storage operations (disk, SMART, mount)."""

    @staticmethod
    def list_disks() -> list[dict]:
        """List all physical block devices."""
        return disk.list_disks()

    @staticmethod
    def get_smart_info(device: str) -> dict:
        """Get full SMART info for a device."""
        return smart.get_smart_info(device)

    @staticmethod
    def get_smart_status(device: str) -> dict:
        """Get SMART health status for a device."""
        return smart.get_smart_status(device)

    @staticmethod
    def list_mounts() -> list[dict]:
        """List all mounts with usage info."""
        return mount.list_mounts()

    @staticmethod
    def mount(device: str, target: str, fs_type: str | None = None) -> dict:
        """Mount a device to a target path."""
        return mount.mount(device, target, fs_type)

    @staticmethod
    def unmount(target: str) -> dict:
        """Unmount a filesystem."""
        return mount.unmount(target)

    def get_overview(self) -> dict:
        """Combined view: disks + mounts + smart summary.

        Returns a dict with 'disks', 'mounts', and 'smart_summary' keys.
        """
        disks_data = self.list_disks()
        mounts_data = self.list_mounts()

        # Smart summary: query SMART status for each disk that is a physical device
        smart_summary = []
        for d in disks_data:
            if "error" in d:
                continue
            name = d.get("name", "")
            # Only query SMART for whole disk devices (type='disk'), not partitions
            if d.get("type") == "disk" and name:
                smart_result = self.get_smart_status(name)
                if "error" not in smart_result:
                    smart_summary.append({
                        "device": name,
                        "smart_available": smart_result.get("smart_available", False),
                        "overall_health": smart_result.get("overall_health", "unknown"),
                    })

        return {
            "disks": disks_data,
            "mounts": mounts_data,
            "smart_summary": smart_summary,
        }

    def get_disk_detail(self, device: str) -> dict:
        """Single disk detail with SMART data.

        Args:
            device: Device name (e.g. 'sda')

        Returns:
            dict with disk info and SMART data.
        """
        # Find disk in listing
        disks = self.list_disks()
        disk_info = None
        for d in disks:
            if "error" in d:
                continue
            if d.get("name") == device:
                disk_info = d
                break

        if disk_info is None:
            # Return at least device name with error
            return {"device": device, "error": f"Device '{device}' not found"}

        # Get SMART data
        smart_data = self.get_smart_info(device)

        return {
            **disk_info,
            "smart": smart_data,
        }


# Convenience module-level aliases
storage_manager = StorageManager()
overview = storage_manager.get_overview
disk_detail = storage_manager.get_disk_detail
