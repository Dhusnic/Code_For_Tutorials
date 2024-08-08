import psutil


def get_system_resource_usage():
    """
    Gets CPU, disk, and memory usage using psutil.

    Returns:
        tuple: A tuple containing CPU percentage, disk usage percentage, and memory usage percentage.
    """

    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=1)

    # Disk usage
    disk_partitions = psutil.disk_partitions()
    disk_usage = None
    for partition in disk_partitions:
        if partition.mountpoint == "/":  # Adjust for your desired disk
            disk_usage = psutil.disk_usage(partition.mountpoint)
            break
    if disk_usage:
        disk_percent = disk_usage.percent
    else:
        disk_percent = 0

    # Memory usage
    memory = psutil.virtual_memory()
    memory_percent = memory.percent

    return cpu_percent, disk_percent, memory_percent


# Example usage
cpu_usage, disk_usage, memory_usage = get_system_resource_usage()
print(f"CPU Usage: {cpu_usage}%")
print(f"Disk Usage: {disk_usage}%")
print(f"Memory Usage: {memory_usage}%")
