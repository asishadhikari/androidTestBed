# -*- coding: utf-8 -*-

import os
import sqlite3
import subprocess as sp
import time
from threading import Thread

import Recursos.comandos as comandos
from Componentes.criador import Criador
from Componentes.gerente import Gerente

from .class_container import Container


class Android:

    def __init__(self, nome, console, time_stamp):
        self.nome = nome
        self.console = console
        self.time_stamp = time_stamp

    def start_app(self, activity, ip_cloudlet):
        # Inicia o app
        os.system(comandos.ACTIVITY % (self.console, activity))
        # Define o IP da cloudlet
        os.system(comandos.SET_CLOUDLET % (self.console, activity, ip_cloudlet))

    def exec_run(self, action, ip_cloudlet, argumentos, repeticoes):
        # limpa o logcat para remover resultados de experimentos anteriores
        #clears the logcat to remove results from previous experiments
        os.system(comandos.CLEAR_LOG % self.console)

        num_interacoes = 1

        # ciclo de repeticoes da activity
        while num_interacoes <= repeticoes:
            print("Interaction number %i for device %s" % (num_interacoes, self.nome))

            # chamada da activity
            os.system(comandos.EXEC % (self.console, action, argumentos))

            # loop para esperar os resultados
            while True:
                # captura dos resultados do logcat do dispositivo e escreve em um arquivo
                # com o mesmo nome do container
                self.get_results()

                try:
                    # retorna a quantidade de linhas do arquivo
                    lines = sp.getoutput(comandos.COUNT_LINES % (self.time_stamp, self.nome))
                    # se a quantidade for igual ao numero de repeticoes
                    # a acitvity ja foi executado e pode-se ir para a proxima interacao
                    if int(lines) == num_interacoes:
                        num_interacoes += 1
                        break
                # caso contratio o loop continua
                except:
                    time.sleep(1)

        print("Executions for device %s are finished!" % self.nome)

    def get_results(self):
        os.system(comandos.RESULTS % (self.console, self.time_stamp, self.nome))
        os.system(comandos.ERRORS % (self.console, self.time_stamp, 'errors-' + self.nome))

    def run(self, action, ip_cloudlet, argumentos, repeticoes):
        # import random
        # time.sleep(random.randrange(1, 5))

        android_thread = Thread(target=self.exec_run, args=(action, ip_cloudlet, argumentos, repeticoes,))
        android_thread.start()


class DeviceManager:

    def __init__(self, nome_cenario, ip_cloudlet, diretorio_saida=False):
        self.nome_cenario = nome_cenario
        self.ip_cloudlet = ip_cloudlet
        self.conn = sqlite3.connect('DB/mydb.db')
        self.cur = self.conn.cursor()

        # cria a pasta para guardar os arquivos de saida

        # Nova feature para adicionar depois
        # passar o nome da pasta de saida
        # como parametro na hora de criar o objeto
        # da class DeviceManager
        # por agora vai na gambiarra

        # creates the folder to store the output files
        # New feature to add later //TODO
        # pass the name of the output folder
        # as parameter when creating the object
        # of the DeviceManager class
        # for now go to the gambiarra
        if diretorio_saida:
            self.time_stamp = diretorio_saida
        else:
            self.time_stamp = time.strftime("%d-%m-%Y_%H:%M:%S")
        
        #directory with time stamp for what?
        os.mkdir(self.time_stamp)

    def get_devices(self):
        # conexão com a database
        #connection to the database
        devices = []
        # seleção dos dispositivos que fazem parte do cenário e estão ativos
        # select devices that are part of scenario and are active
        self.cur.execute(
            'SELECT * FROM containers WHERE nome_cenario = :nome AND estado_container = :estado AND is_server = 0 OR is_server = 3',
            {'nome': self.nome_cenario, 'estado': 'EXECUTING'}
            )
        res = self.cur.fetchall()

        for i in range(len(res)):
            """ 
				0 -> nome_cenario
				1 -> nome_container
				2 -> porta_6080
				3 -> porta_5554
				4 -> porta_5555
				5 -> rede
				6 -> estado
				7 -> servidor ou não 
				8 -> memoria
				9 -> cpus
			"""

            # criação do objeto android
            android = Android(res[i][1], res[i][3], self.time_stamp)

            # lista com os dipositivos
            devices.append(android)

        # retorna a lista com objetos
        return devices

    def start_app(self, android, activity):
        android.start_app(activity, self.ip_cloudlet)
        print("Stated activity {} on device {}".format(activity, android.nome))

    def exec_activity(self, android, action, argumentos, repeticoes):
        android.run(action, self.ip_cloudlet, argumentos, repeticoes)

    def start_dynamic_cloudlet(self, threshold, servers_list, nginx_name):
        manager = Criador()
        controller = Gerente()

        added_cloudlets = 0
        while True:
            overload = 0

            for server_info in servers_list:
                # get the cpu percentage of the given container
                cpu, _ = sp.getoutput("docker stats %s --no-stream --format '{{.CPUPerc}}'" % server_info[0]).split("%")

                if float(cpu) > threshold:
                    overload += 1

            # if at least one of the cloudlets is overloaded
            # we create a new cloudlet
            if overload > 0:
                # for now it creates an unlimited clodulet
                novo_container = Container(
                    nome_container="extra-cloudlet-%s" % added_cloudlets,
                    nome_cenario=self.nome_cenario,
                    cpus=server_info[1],
                    memory=server_info[2])

                manager.criar_server(novo_container, False)

                controller.iniciar_cenario(self.nome_cenario)
                controller.configure_nginx(nginx_name, self.nome_cenario)

                print("New cloudlet added")

                added_cloudlets += 1

    def use_dynamic_cloudlet(self, nginx_name, threshold):
        self.cur.execute(
            'SELECT nome_container, cpus, memory FROM containers WHERE nome_cenario = :cenario AND is_server = 1',
            {'cenario': self.nome_cenario})

        servers = self.cur.fetchall()

        self.cloudlet_thread = Thread(target=self.start_dynamic_cloudlet, args=(float(threshold), servers, nginx_name))
        # set the thread to finish afeter the main thred dies
        self.cloudlet_thread.daemon = True

        self.cloudlet_thread.start()
