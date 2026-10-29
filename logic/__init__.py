"""BizMastas line-monitoring logic package.

Each module turns raw Modbus data into a plain dict that app.py can render.
"""


def reg(values, index, default=0.0):
    """Return values[index] as a float, or `default` if it can't be read."""
    try:
        return float(values[index])
    except (IndexError, TypeError, ValueError):
        return default


def bit(values, index, default=False):
    """Return values[index] as a bool, or `default` if it can't be read."""
    try:
        return bool(values[index])
    except (IndexError, TypeError):
        return default
