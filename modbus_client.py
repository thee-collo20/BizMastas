from __future__ import annotations

from typing import Any, Dict

from pymodbus.client import ModbusTcpClient

from config import PLC_CONFIG


def readAll(client: ModbusTcpClient) -> Dict[str, Any]:
    """Read the standard Modbus registers used by the BizMastas dashboard."""
    data: Dict[str, Any] = {}

    try:
        coils = client.read_coils(0, 8)
        if not coils.isError():
            data["coils"] = list(coils.bits[:8])

        discrete = client.read_discrete_inputs(0, 8)
        if not discrete.isError():
            data["discrete"] = list(discrete.bits[:8])

        holding = client.read_holding_registers(0, 30)
        if not holding.isError():
            data["holding"] = list(holding.registers[:30])

        input_regs = client.read_input_registers(0, 10)
        if not input_regs.isError():
            data["input_regs"] = list(input_regs.registers[:10])

    except Exception as exc:  # pragma: no cover - defensive fallback
        data["Error"] = str(exc)

    return data


class FactoryPLC:
    def __init__(self, host: str | None = None, port: int | None = None, timeout: int | None = None):
        self.client = ModbusTcpClient(
            host or PLC_CONFIG["ip"],
            port=port if port is not None else PLC_CONFIG["port"],
            timeout=timeout if timeout is not None else PLC_CONFIG["timeout"],
        )

    def connect(self):
        return self.client.connect()

    def read_all(self):
        return readAll(self.client)

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass
