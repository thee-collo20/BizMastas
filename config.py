"""Discrete safety / process inputs and analog input registers."""
from config import REGISTER_MAP
from logic import bit, reg


def process_sensors(discrete_inputs, input_regs):
    discrete_inputs = discrete_inputs or []
    input_regs = input_regs or []
    d = REGISTER_MAP["discrete"]
    i = REGISTER_MAP["input_regs"]

    return {
        "e_stop_ok": bit(discrete_inputs, d["e_stop_ok"], True),
        "resin_low": bit(discrete_inputs, d["resin_low"], False),
        "board_present": bit(input_regs, i["board_present"], False),
        "line_temp": reg(input_regs, i["line_temp"], 0.0),
    }
