# -*- coding: utf-8 -*-

import os
import re
import sqlite3
import subprocess as sp

import docker
import nginx
from texttable import Texttable

import Recursos.comandos as comandos


class Gerente:

    def __init__(self):
        # conexão com o docker, utilize o comando 'docker version' e descubra a versão da API do servidor
        self.client = docker.from_env(version='1.40')
        # conexao com o sqlite
        self.conn = sqlite3.connect('DB/mydb.db')
        # criacao do cursor
        self.cur = self.conn.cursor()

    def listar_cenarios(self):
        self.cur.execute('SELECT * FROM cenarios')
        res = self.cur.fetchall()

        table = Texttable()
        table.add_row(['Scenario Name', 'Scenario State'])

        for i in range(len(res)):
            # posição 0 contém o nome e posição 1 o estado
            table.add_row([res[i][0], res[i][1]])

        print(table.draw())

    # cria a tabela de listagem dos containers
    def listar_containers(self, nome_cenario):
        self.cur.execute('SELECT * FROM containers WHERE nome_cenario = ? ORDER BY nome_container', (nome_cenario,))
        res = self.cur.fetchall()

        table = Texttable(max_width=0)
        table.header(['Container Name', 'VNC', 'Emulador', 'IP', 'Network/Speed', 'Memory', 'CPUS', 'State'])

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

            cpus = '---'
            vnc = '---'
            console_adb = '---'
            ip = sp.getoutput(comandos.GET_IP % res[i][1])

            if res[i][7] == 0:
                # criando o edereço para o noVNC
                vnc = 'localhost:%s' % str(res[i][2])
                console_adb = '%s' % str(res[i][3])

            if res[i][7] == 3:
                console_adb = '%s' % str(res[i][3])
                ip = '---'
            else:
                cpus = res[i][9]

            # configurações de formatação da tabela
            table.set_cols_align(['l', 'c', 'c', 'c', 'c', 'c', 'c', 'c'])
            table.add_row([res[i][1], vnc, console_adb, ip, res[i][5], res[i][8], cpus, res[i][6]])

        # mostra a tabela
        print(table.draw())

    def listar_console_dispositivos(self, nome_cenario):
        self.cur.execute('SELECT porta_5554 FROM containers WHERE nome_cenario = :nome AND is_server = 0 OR is_server = 3',
                         {'nome': nome_cenario})
        consoles = []

        for i in self.cur.fetchall():
            consoles.append(i[0])

        return consoles

    # checa se um cenário existe
    def cenario_existe(self, nome_cenario):
        # coloca o nome em formato de tupla para comparacao futura
        nome = (nome_cenario,)

        self.cur.execute("SELECT nome_cenario FROM cenarios WHERE nome_cenario = :nome", {'nome': nome_cenario})
        resultado = self.cur.fetchall()

        # checagem de nome unico
        for i in resultado:
            # comparacao com as tuplas retornadas
            if i == nome:
                return False

        return True

    # checa se o container existe
    def container_existe(self, nome_container):
        # o nome deve seguir as seguintes restrições
        regex = re.match('[a-zA-Z0-9][a-zA-Z0-9_.-]', nome_container)
        if regex == None:
            # em caso negativo
            return True

        # coloca o nome em formato de tupla para comparacao futura
        nome = (nome_container,)
        self.cur.execute("SELECT nome_container FROM containers")

        # checagem por nome repetido de containers
        for i in self.cur.fetchall():
            if i == nome:
                # nome existe
                return True

        # nome nao existe
        return False

    # inicia o servico do emulador ou do MpOs dependendo do tipo do container
    def iniciar_servicos(self, lista_containers, nome_cenario):
        for container in self.client.containers.list(all=True):
            for i in lista_containers:
                # posição 0 contém o nome do container a posição 1 contém o tipo de rede que ele deve usar
                if i[0] == container.name:
                    # posição 2 diz se ele é cliente ou servidor
                    if i[2] == 0:
                        try:
                            # posição 3 tem a qtd de memoria usada pelo emulador
                            container.exec_run(comandos.START_EMU % (i[1], i[3]), detach=True)
                        except:
                            pass
                    if i[2] == 1:
                        # captura o ip do container
                        ip_servidor = sp.getoutput(comandos.GET_IP % i[0])
                        # forma um comando sed
                        cmd = comandos.MPOS_IP_CHANGE % ip_servidor
                        # configura o IP do container no arquivo de configuração do MpOS
                        container.exec_run("sh -c '%s'" % cmd)
                        # inicia o cloudlet
                        container.exec_run("sh -c '%s'" % comandos.START_MPOS, detach=True)

                    if i[2] == 2:
                        self.configure_nginx(i[0], nome_cenario)

    def iniciar_cenario(self, nome_cenario):
        # retorna o nome e o tipo de rede de containers em estado STOPPED ou CREATED do cenário
        self.cur.execute(
            'SELECT nome_container, rede, is_server, memory FROM containers WHERE nome_cenario = ? AND (estado_container = ? OR estado_container = ?)',
            (nome_cenario, 'CREATED', 'STOPPED')
        )
        resultado = self.cur.fetchall()

        # lista de containers ativos
        for container in self.client.containers.list(all=True):
            # resultado dos containers que fazem parte do cenário
            for i in resultado:
                # posição 0 contém o nome do container a posição 1 contém o tipo de rede que ele deve usar
                if i[0] == container.name:
                    # inicia o container
                    container.restart()

                    # atualiza o estado do container no banco para EXECUTING
                    with self.conn:
                        try:
                            self.cur.execute("UPDATE containers SET estado_container = ? WHERE nome_container = ?",
                                             ('EXECUTING', i[0]))
                        except Exception as e:
                            raise e

        self.iniciar_servicos(resultado, nome_cenario)

        # atualiza o estado cenario no banco para ACTIVE
        with self.conn:
            try:
                self.cur.execute("UPDATE cenarios SET estado_cenario = :novo_estado WHERE nome_cenario = :nome",
                                 {'novo_estado': 'ACTIVE', 'nome': nome_cenario})
            except Exception as e:
                raise e

    def parar_cenario(self, nome_cenario):
        self.cur.execute(
            'SELECT nome_container, is_server FROM containers WHERE nome_cenario = ? AND (estado_container = ? OR estado_container = ?)',
            (nome_cenario, 'CREATED', 'EXECUTING')
        )

        resultado = self.cur.fetchall()

        for container in self.client.containers.list():
            for i in resultado:
                # posição 0 contém o nome do container a posição 1 diz se o container é cliente ou servidor
                if i[0] == container.name:
                    # se for servidor
                    if i[1] == 1:
                        # coleta o IP do servidor
                        ip_servidor = sp.getoutput(comandos.GET_IP % container.name)
                        # forma o comando sed
                        cmd = comandos.MPOS_DEFAULT % ip_servidor
                        # retira o IP do servidor no arquivo config.properties
                        container.exec_run("sh -c '%s'" % cmd)

                    # para o cintainer
                    container.stop()

                    # atualiza o estado do container no banco para STOPPED
                    with self.conn:
                        try:
                            self.cur.execute("UPDATE containers SET estado_container = ? WHERE nome_container = ?",
                                             ('STOPPED', i[0]))
                            # Removes real device entries from the database
                            self.cur.execute("DELETE FROM containers WHERE is_server = :is_server", {'is_server': 3})
                        except Exception as e:
                            raise e

        # atualiza o estado cenario no banco para ACTIVE
        with self.conn:
            try:
                self.cur.execute("UPDATE cenarios SET estado_cenario = :novo_estado WHERE nome_cenario = :nome",
                                 {'novo_estado': 'STOPPED', 'nome': nome_cenario})
            except Exception as e:
                raise e  # Latest commit a9494d7  4 days ago

    # conexão com os emuladores pelo adb
    def conectar_dispositivos(self, nome_cenario):
        os.system(comandos.ADB_KILL)
        output = sp.getoutput(comandos.ADB_START)

        print(output)

    # instalar app
    def install_app(self, apk, nome_cenario):
        consoles = self.listar_console_dispositivos(nome_cenario)
        #print("DEBUGGING: ", consoles)
        for i in consoles:
            #print("DEBUGGING: ", comandos.INSTALL_APP % (i, apk))
            saida = os.system(comandos.INSTALL_APP % (i, apk))
            print(saida)

    def restart_container(self, nome_container, nome_cenario):
        for container in self.client.containers.list():
            if container.name == nome_container:
                with self.conn:
                    self.cur.execute(
                        'SELECT nome_container, rede, is_server, memory FROM containers WHERE nome_container = ? AND estado_container = ?',
                        (nome_container, 'EXECUTING'))

                    resultado = self.cur.fetchall()

                if resultado[0][2] == 0 or resultado[0][2] == 1:
                    container.restart()

                print('Restarting container %s' % nome_container)

                self.iniciar_servicos(resultado, nome_cenario)

    def configure_nginx(self, nome_container, nome_cenario):
        # Lista com o servircos do MpOS e as portas
        # Em caso de deploy de um novo app, adicione o Nome e a porta aqui
        services = {
            'PingTcpServer': '40000',
            'PingUdpServer': '40001',
            'JitterUdpServer': '40005',
            'DeployAppTcpServer': '40020',
            'BandwidthTcpServer': '40010',
            'PersistenceTcpServer': '40011',
            'JitterRetrieveTcpServer': '40006',
            'RpcTcpServer_benchImage2': '36114',
            'DiscoveryServiceTcpServer': '30015',
            'DiscoveryMulticastService': '31000',
            'RpcTcpServer_matrixOperations': '36415',
            'RpcTcpServer_kotlin_matrixOperations': '36241',
            'RpcTcpServer_sourceafis': '36619'
        }

        conf = nginx.Conf()
        stream = nginx.Stream()

        self.cur.execute("SELECT nome_container FROM containers WHERE is_server = ? AND nome_cenario = ?",
                         (1, nome_cenario))

        server_ips = []
        for container in self.cur.fetchall():
            server_ips.append(sp.getoutput(comandos.GET_IP % container))

        for service_name, port in services.items():
            upstream = nginx.Upstream(service_name)
            for ip in server_ips:
                upstream.add(
                    nginx.Key(
                        'server', '{}:{}'.format(ip, port)))

            server = nginx.Server()
            server.add(
                nginx.Key('listen', port),
                nginx.Key('proxy_pass', service_name))

            stream.add(upstream, server)

        conf.add(stream)

        sp.call('cp Recursos/nginx.conf.org Recursos/nginx.conf', shell=True)
        with open('Recursos/nginx.conf', 'a') as file:
            nginx.dump(conf, file)

        sp.call('docker cp Recursos/nginx.conf %s:/etc/nginx/nginx.conf' % nome_container, shell=True)
        sp.call('docker exec %s bash -c "nginx -s reload"' % nome_container, shell=True, stderr=sp.DEVNULL,
                stdout=sp.DEVNULL)
        sp.call('rm Recursos/nginx.conf', shell=True)

    def update_cpus(self, nome_container, qtd_cpus):
        sp.call("docker update --cpus='%s' %s" % (qtd_cpus, nome_container), shell=True, stderr=sp.DEVNULL,
                stdout=sp.DEVNULL)
