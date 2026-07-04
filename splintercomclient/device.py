import platform


def get_os_info():
    return str(platform.platform())[0:30]


def get_device_type():
    return str(platform.machine())[0:30]
