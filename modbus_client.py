from pymodbus.client import ModbusTcpClient
from config import PLC_CONFIG
import time

class FactoryPLC:
    def __init__(self):
        self.clirnt=ModbusTcpClient(
            PLC_CONFIG["ip"],
            port=PLC_CONFIG["port"],
            timeout=PLC_CONFIG["timeout"]
        )

    def connect(self):
        return self.clirnt.connect()

    def readAll(self):
        data={}
        try:
            #Coils
            c=self.client.read_coils(0,8)
            if not c.isError():
                data['coils']=c.bits[:8]

            #Descrete_Inputs
            d=self.client.read_descrete_inputs(0,8)
            if not d.isError():
                data["Inputs"]= d.bits[:6]

            #Holding registars
            h=self.client.read_holding_registers(0,20)
            if not h.isError():
                data ["holding"]=h.registers

            #Input registrars
            inp=self.self.client.read_Input_registers(0,6)
            if not h.isError():
                data['input_ regs'] =h.registers

    except Exception as e:
            data["Error"]=str(e)

    return data 

def close(self):
    self.client.close()


                                     
































































































































































































































