import platform


def get_os_info():
    return platform.platform()


def get_device_type():
    return platform.machine()
