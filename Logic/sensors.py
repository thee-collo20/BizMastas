# Sensor evaluation for discrete safety and process inputs.


def process_sensors(discrete_inputs, input_regs):
    if discrete_inputs is None:
        discrete_inputs = []
    if input_regs is None:
        input_regs = []

    result = {
        "e_stop_ok": bool(discrete_inputs[0]) if len(discrete_inputs) > 0 else True,
        "resin_low": bool(discrete_inputs[1]) if len(discrete_inputs) > 1 else False,
        "board_present": bool(input_regs[0]) if len(input_regs) > 0 else False,
        "line_temp": float(input_regs[1]) if len(input_regs) > 1 else 0.0,
    }

    return result
