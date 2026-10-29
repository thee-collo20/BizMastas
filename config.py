PLC_CONFIG={
    "ip" : "192.168.1.88",
    "port" : 502,
    "timeout" : 2
}

REGISTAR_MAP={
    "holding" : {
        0:"Oven1_Actual",
        1:"Oven2_Actual",
        2:"Oven1_Setpoint",
        3:"Oven2_Setpoint",
        10:"Line_Speed",
        11:"Pressure"
    },
    "coils" : {
        0:"Motor_RUN",
        1:"Hydraulic_pump",
        2:"Heater_Enable"
    }, 
    "descrete_Inputs" : {
        0:"Board_Sensor",
        2:"E_STOP_OK"
    }
}