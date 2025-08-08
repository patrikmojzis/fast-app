from functools import wraps
from threading import local

instances = {}

def singleton(cls):
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance

