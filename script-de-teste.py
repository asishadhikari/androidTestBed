#!/usr/bin/python3

import time

# importa a API
from Recursos.DeviceManagerAPI import DeviceManager

# instancia a classe da API passando o nome do cenario e o ip da cloudlet
DM = DeviceManager("teste", "192.168.1.10")

# guarda os dispositivos do cénario em uma variavel
dispositivos = DM.get_devices()

# inicia a app desejada nos dispositivos
for android in dispositivos:
	DM.start_app(android, "br.ufc.great.matrixoperation/.MainActivity")

# tempo para que o app descubra o cloudlet
print("\nTempo para os dispositivos se comunicarem com o cloudlet.")
time.sleep(13)

# define a qtd de repeticoes, a activity e os argumentos a serem executados
for android in dispositivos:
	DM.exec_activity(android, "br.ufc.great.matrixoperation/.MainActivity", "--es 'operation' 'mul' --ei 'size' 800", 20)
