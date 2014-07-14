#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Zoe Agent Manager - https://github.com/RMed/zoe_agent_manager
#
# Copyright (c) 2014 Rafael Medina García <rafamedgar@gmail.com>
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import configparser
import os
import shutil
import stat
import subprocess
import zoe
from zoe.deco import *


@Agent(name = "manager")
class AgentManager:

    @Message(tags = ["install"])
    def install(self, ag_name, ag_source):
        """ Install new agent from source. 

            - ag_name: name of the agent
            - ag_source: the git repository from which to download the agent.
                It can be presented in two ways:

                user/agent : GitHub repository
                git://path_to_repo : regular git repository
        """
        temp = os.path.join(os.environ["ZOE_VAR"], "manager", ag_name)
        fetch_source = subprocess.call(["git", "clone", ag_source, temp])

        if fetch_source != 0:
            print("Could not fetch source from %s" % ag_source)
            return

        agent_info = configparser.ConfigParser()
        agent_info.read(os.path.join(temp, "setup.zoe"))

        # Move agent files
        for dest in agent_info["INSTALL"]:
            shutil.move(
                os.path.join(temp, agent_info["INSTALL"][dest]),
                os.path.join(os.environ["ZOE_HOME"], dest))

        # Add agent to the zoe.conf file
        conf_path = os.path.join(os.environ["ZOE_HOME"], "etc", "zoe.conf")
        zconf = configparser.ConfigParser()
        zconf.read(conf_path)

        ports = []
        for sec in zconf.sections():
            if 'port' in zconf[sec]:
                ports.append(int(zconf[sec]["port"]))
        ports = sorted(ports)

        free_port = ports[0]
        while free_port in ports:
            free_port += 1

        zconf.add_section("agent " + ag_name)
        zconf["agent " + ag_name]["port"] = str(free_port)
        with open(conf_path, 'w') as configfile:
            zconf.write(configfile)

        print("Agent %s installed correctly." % ag_name)

        # Launch the agent
        self.launch_agent(ag_name)

        # Cleanup
        shutil.rmtree(os.path.join(os.environ["ZOE_VAR"], "manager"))

    @Message(tags = ["launch"])
    def launch_agent(self, ag_name):
        """ Launch an agent. """
        agent_dir = os.path.join(os.environ["ZOE_HOME"], "agents", ag_name)
        if not os.path.isdir(agent_dir):
            print("Agent %s does not exist!" %ag_name)

        script = None
        # Get executable script
        # Obtained from http://stackoverflow.com/a/8957768
        executable = stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
        for filename in os.listdir('.'):
            if os.path.isfile(filename):
                st = os.stat(filename)
                mode = st.st_mode
                if mode & executable:
                    script = filename

        print("Launching agent %s..." % ag_name)
        log_file = open(os.path.join(os.environ["ZOE_LOGS"], ag_name + ".log"))
        proc = subprocess.Popen([os.path.join(agent_dir, script)],
                stdout=log_file, stderr=log_file)
        print("Launched agent %s with PID %i" % (ag_name, proc.pid))

        pid_path = os.path.join(os.environ["ZOE_VAR"], ag_name + ".pid")
        with open(pid_path, "w+") as pf:
            print(proc.pid, file=pf)
