"""Modbus TCP access to the line PLC, plus a simulator for demos/offline use."""
from __future__ import annotations

import math
import random
import time
from typing import Any, Dict

from pymodbus.client import ModbusTcpClient

from config import PLC_CONFIG, READ_BLOCKS, REGISTER_MAP


def readAll(client: ModbusTcpClient) -> Dict[str, Any]:
    """Read every table in READ_BLOCKS.

    Returns {"coils": [...], "discrete": [...], "holding": [...],
    "input_regs": [...], "failed": [names of tables that could not be read]}.
    """
    readers = {
        "coils": client.read_coils,
        "discrete": client.read_discrete_inputs,
        "holding": client.read_holding_registers,
        "input_regs": client.read_input_registers,
    }
    data: Dict[str, Any] = {"failed": []}

    for name, read in readers.items():
        count = READ_BLOCKS[name]
        try:
            response = read(0, count=count)  # `count` must be a keyword in pymodbus 3.x
            if response.isError():
                data["failed"].append(name)
                continue
            items = response.bits if name in ("coils", "discrete") else response.registers
            data[name] = list(items[:count])
        except Exception:
            data["failed"].append(name)

    return data


class FactoryPLC:
    def __init__(self, host: str | None = None, port: int | None = None, timeout: float | None = None):
        self.client = ModbusTcpClient(
            host or PLC_CONFIG["ip"],
            port=port if port is not None else PLC_CONFIG["port"],
            timeout=timeout if timeout is not None else PLC_CONFIG["timeout"],
        )

    def connect(self) -> bool:
        try:
            return bool(self.client.connect())
        except Exception:
            return False

    def read_all(self) -> Dict[str, Any]:
        return readAll(self.client)

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass


def simulate_raw() -> Dict[str, Any]:
    """Fake PLC data laid out exactly like REGISTER_MAP, with gentle drift."""
    t = time.time()
    h, c = REGISTER_MAP["holding"], REGISTER_MAP["coils"]
    d, i = REGISTER_MAP["discrete"], REGISTER_MAP["input_regs"]

    holding = [0.0] * READ_BLOCKS["holding"]
    for n, (a_idx, s_idx) in enumerate(zip(h["oven_actual"], h["oven_setpoint"])):
        holding[s_idx] = 145.0
        holding[a_idx] = round(145.0 + 2.2 * math.sin(t / 40 + n) + random.uniform(-0.5, 0.5), 1)
    holding[h["line_speed_actual"]] = round(22.0 + random.uniform(-0.2, 0.2), 1)
    holding[h["line_speed_setpoint"]] = 22.0
    holding[h["hydraulic_pressure"]] = round(35.2 + random.uniform(-0.4, 0.4), 1)

    coils = [False] * READ_BLOCKS["coils"]
    for name in ("main_drive", "hydraulic_pump", "unwinder", "rewinder"):
        coils[c[name]] = True

    discrete = [False] * READ_BLOCKS["discrete"]
    discrete[d["e_stop_ok"]] = True
    discrete[d["resin_low"]] = False

    input_regs = [0] * READ_BLOCKS["input_regs"]
    input_regs[i["board_present"]] = 1
    input_regs[i["line_temp"]] = 85

    return {
        "coils": coils,
        "discrete": discrete,
        "holding": holding,
        "input_regs": input_regs,
        "failed": [],
    }
