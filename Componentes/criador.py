# -*- coding: utf-8 -*-

import json
import os
import re
import sqlite3

import docker

from Recursos.class_container import Container

from .gerente import Gerente


class Criador:

    def __init__(self):
        #manager instance
        self.gerente = Gerente()
        # conexão com o docker, utilize o comando 'docker version' e descubra a versão da API do servidor
        self.client = docker.from_env(version='1.40')
        # conexao com o sqlite
        self.conn = sqlite3.connect('DB/mydb.db')
        # criacao do cursor
        self.cur = self.conn.cursor()
        # tantativa de criacao da tabela containers e cenarios
        with self.conn:
            self.cur.execute(
                # OBS.: 'is_server' indicates a lot of things:
                # if 0 -> android container
                # if 1 -> server container
                # if 2 -> nginx container
                # if 3 -> real device

                """CREATE TABLE IF NOT EXISTS  containers (
                        nome_cenario text,
                        nome_container text,
                        porta_6080 integer,
                        porta_5554 text,
                        porta_5555 integer,
                        rede text,
                        estado_container text default 'CREATED',
                        is_server integer default 0,
                        memory text,
                        cpus text
                    )"""
            )

            self.cur.execute(
                """CREATE TABLE IF NOT EXISTS cenarios(
                        nome_cenario text,
                        estado_cenario text default 'STOPPED'
                    )"""
            )

        # procurar as maiores portas em uso e definindo o valor das portas para novos containers
        self.cur.execute('SELECT MAX(porta_6080) FROM containers')
        resposta = self.cur.fetchone()
        if resposta[0] is None:
            self.porta_6080 = 6080
        else:
            self.porta_6080 = resposta[0] + 1

        self.cur.execute('SELECT MAX(porta_5554) FROM containers')
        resposta = self.cur.fetchone()
        if resposta[0] is None:
            self.porta_5554 = 5554
        else:
            try:
                _, port_5554 = resposta[0].split('-')
                self.porta_5554 = int(port_5554) + 2
            except ValueError:
                pass

        self.cur.execute('SELECT MAX(porta_5555) FROM containers')
        resposta = self.cur.fetchone()
        if resposta[0] is None:
            self.porta_5555 = 5555
        else:
            self.porta_5555 = resposta[0] + 2

    def criar_cenario(self, nome_cenario):
        if self.gerente.cenario_existe(nome_cenario):
            # insercao no arquivo mydb.db
            with self.conn:
                try:
                    self.cur.execute(
                        "INSERT INTO cenarios (nome_cenario) VALUES (:nome)",
                        {'nome': nome_cenario}
                    )

                    print('Scenario created')

                    return True

                except Exception as e:
                    print(e)
                    return False
        else:
            print('The name is already in use!')
            return False

    def deleta_cenario(self, nome_cenario):
        self.cur.execute('SELECT nome_container, is_server FROM containers WHERE nome_cenario = :nome',
                         {'nome': nome_cenario})
        res = self.cur.fetchall()

        for i in range(len(res)):
            for container in self.client.containers.list(all=True):
                if container.name == res[i][0]:
                    self.deleta_container(container.name)

        with self.conn:
            try:
                self.cur.execute('DELETE FROM cenarios WHERE nome_cenario = :nome', {'nome': nome_cenario})
            except Exception as e:
                raise e

    def delete_real_devices(self, nome_cenario):
        self.cur.execute('SELECT nome_container, is_server FROM containers WHERE nome_cenario = :nome',
                         {'nome': nome_cenario})
        res = self.cur.fetchall()

        for i in res:
            if i[1] is 3:
                with self.conn:
                    self.cur.execute('DELETE FROM containers WHERE nome_container = :nome', {'nome': i[0]})

    def criar_cliente(self, novo_container, rede):
        with self.conn:
            try:
                self.client.containers.run(
                    'renanalves/android-testbed',
                    cap_add=['NET_ADMIN'],
                    detach=True,
                    privileged=True,
                    publish_all_ports=True,
                    name=novo_container.nome,
                    ports={
                        '6080/tcp': self.porta_6080,
                        '5554/tcp': self.porta_5554,
                        '5555/tcp': self.porta_5555
                    }
                )

                self.cur.execute(
                    "INSERT INTO containers (nome_cenario, nome_container, porta_6080, porta_5554, porta_5555, rede, memory, cpus) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        novo_container.cenario, novo_container.nome, self.porta_6080,
                        "emulator-{}".format(self.porta_5554),
                        self.porta_5555, rede, novo_container.memory, novo_container.cpus)
                )

                self.porta_6080 += 1
                self.porta_5554 += 2
                self.porta_5555 += 2

            except:
                print("Error while trying to connect to container")
                return 1

    def criar_server(self, novo_container, bind_ports=True):
        if bind_ports:
            self.client.containers.run(
                'renanalves/server-testbed',
                detach=True,
                tty=True,
                stdin_open=True,
                privileged=True,
                ports={
                    '30015/tcp': 30015,
                    '31000/tcp': 31000,
                    '36114/tcp': 36114,
                    '36381/tcp': 36381,
                    '36415/tcp': 36415,
                    '36241/tcp': 36241,
                    '40000/tcp': 40000,
                    '40001/tcp': 40001,
                    '40005/tcp': 40005,
                    '40006/tcp': 40006,
                    '40010/tcp': 40010,
                    '40011/tcp': 40011,
                    '40020/tcp': 40020,
                    '36619/tcp': 36619
                },
                publish_all_ports=True,
                cap_add=['NET_ADMIN'],
                name=novo_container.nome,
                mem_limit=novo_container.memory
            )
        else:
            self.client.containers.run(
                'renanalves/server-testbed',
                detach=True,
                tty=True,
                stdin_open=True,
                privileged=True,
                cap_add=['NET_ADMIN'],
                name=novo_container.nome,
                mem_limit=novo_container.memory
            )

        if not novo_container.cpus == "":
            self.gerente.update_cpus(novo_container.nome, novo_container.cpus)

        with self.conn:
            try:
                self.cur.execute(
                    "INSERT INTO containers (nome_cenario, nome_container, cpus, is_server, memory, porta_6080, porta_5554, porta_5555, rede) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (novo_container.cenario, novo_container.nome, novo_container.cpus, 1, novo_container.memory, None,
                     None, None, None)
                )

            except Exception as e:
                print(e)

    def criar_nginx(self, novo_container):
        nginx = self.client.containers.run('nginx', detach=True, name=novo_container.nome)

        with self.conn:
            try:
                self.cur.execute(
                    "INSERT INTO containers (nome_cenario, nome_container, porta_6080, porta_5554, porta_5555, rede, is_server, cpus) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (novo_container.cenario, nginx.name, None, None, None, None, 2, None)
                )

            except Exception as e:
                print(e)

    def deleta_container(self, nome_container):
        for container in self.client.containers.list(all=True):
            if container.name == nome_container:
                print('Deleating container %s' % container.name)
                container.remove(force=True)

                with self.conn:
                    self.cur.execute('DELETE FROM containers WHERE nome_container = :nome', {'nome': nome_container})

    def add_real_device(self, device_name, cenario):
        with self.conn:
            self.cur.execute(
                "INSERT INTO containers (nome_cenario, nome_container, porta_6080, porta_5554, porta_5555, rede, memory, cpus, estado_container, is_server) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cenario, device_name, None, device_name, device_name, None, None, None, "EXECUTING", 3)
            )

    def create_from_json(self, json_file, cenario):
        try:
            config_data = json.load(open(json_file, 'r'))
        except FileNotFoundError:
            print("File not found!")
            return

        for device in config_data.get('mobile-devices'):
            if not self.gerente.container_existe(device.get('name')):
                regex = re.match('lte|umts|full|[0-9]', device.get('network'))

                if regex is None:
                    print('Network configuration for device %s is not supported!' % device.get('name'))
                    continue

                if int(device.get('memory')) < 512:
                    print("Memory value too low for device %s." % device.get('name'))
                    continue

                new_container = Container(
                    nome_container=device.get('name'),
                    memory=device.get('memory'),
                    nome_cenario=cenario
                )

                print("Creating container: %s" % device.get('name'))
                self.criar_cliente(new_container, device.get('network'))

            else:
                print("The name %s is already in use!" % device.get('name'))

        for server in config_data.get('server'):
            if not self.gerente.container_existe(server.get('name')):
                try:
                    if int(server.get('memory')):
                        """
                            the docker api I'm using requires the memory value
                            and the unit, in this case m for megabytes
                            so, for example, 512m or 1024m
                        """
                        mem_limit = server.get('memory') + 'm'
                except ValueError:
                    mem_limit = ''

                new_container = Container(
                    nome_container=server.get('name'),
                    cpus=server.get('cpus'),
                    memory=mem_limit,
                    nome_cenario=cenario
                )
                
                print("Creating container: %s" % server.get('name'))
                self.criar_server(new_container, False)

        """Creates the Nginx container in order to access the previous created servers. The name is random"""
        print("Creating Nginx container")
        self.criar_nginx(Container('', cenario))

        print("Starting containers....")
        self.gerente.iniciar_cenario(cenario)
