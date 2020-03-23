#!/usr/bin/python3

import time

# importa a API
# Import API instance 
from Recursos.DeviceManagerAPI import DeviceManager

# instancia a classe da API passando o nome do cenario e o ip da cloudlet
# instantiate an API class wihle passing name of the scenario and cloudlet IP addr
DM = DeviceManager("teste", "192.168.1.10")

# guarda os dispositivos do cénario em uma variavel
# store's the scenario's devices in a variable
dispositivos = DM.get_devices()

# inicia a app desejada nos dispositivos
# launches the desired app on devices
for android in dispositivos:
	DM.start_app(android, "br.ufc.great.matrixoperation/.MainActivity")

# tempo para que o app descubra o cloudlet
# time required for the app to discover the cloudlet
print("\nTempo para os dispositivos se comunicarem com o cloudlet.")
time.sleep(13)

# define a qtd de repeticoes, a activity e os argumentos a serem executados
#defines the number of repetitions, the activity and the arguments to be executed
for android in dispositivos:
	DM.exec_activity(android, "br.ufc.great.matrixoperation/.MainActivity", "--es 'operation' 'mul' --ei 'size' 800", 20)
