# Sensor evaluation for discrete safety and process inputs.

def process_sensors(discrete_inputs, input_regs):
    result = {}

    # Safe defaults to avoid crashes when the PLC is unavailable.
    result["e_stop_ok"] = bool(discrete_inputs[0]) if len(discrete_inputs) > 0 else True
    result["resin_low"] = bool(discrete_inputs[1]) if len(discrete_inputs) > 1 else False
    result["board_present"] = bool(input_regs[0]) if len(input_regs) > 0 else False
    result["line_temp"] = input_regs[1] if len(input_regs) > 1 else 0

    return result
