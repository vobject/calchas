from typing import Any, Dict

def dict_merge(a: Dict[Any, Any], b: Dict[Any, Any], path=None):
    """Based on https://stackoverflow.com/a/7205107/53911"""
    if a is None:
        return b
    if b is None:
        return a
    if path is None: path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                dict_merge(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass # same leaf value
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a
