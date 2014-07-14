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

    @Message(tags = ["add"])
    def add(self, ag_name, ag_source):
        """ Add an agent to the repository. """
        rpath = os.path.join(os.environ["ZOE_HOME"], "etc", "agents_repo.conf")
        repo = configparser.ConfigParser()
        repo.read(rpath)

        # Check if already installed
        if ag_name in repo.sections():
            if repo[ag_name]["installed"] == "1":
                print("Agent %s is already installed" % ag_name)
                return

        repo.add_section(ag_name)
        repo[ag_name]["source"] = str(ag_source)
        repo[ag_name]["installed"] = "0"
        repo[ag_name]["version"] = ""

        with open(rpath, 'w') as repofile:
            repo.write(repofile)

        print("Added new agent %s to the repo" % ag_name)

    @Message(tags = ["install"])
    def install(self, ag_name):
        """ Install an agent from source. """
        rpath = os.path.join(os.environ["ZOE_HOME"], "etc", "agents_repo.conf")
        repo = configparser.ConfigParser()
        repo.read(rpath)

        # Check if already installed
        if ag_name in repo.sections():
            if repo[ag_name]["installed"] == "1":
                print("Agent %s is already installed" % ag_name)
                return
        else:
            print("Agent not found in repository")
            return

        temp = os.path.join(os.environ["ZOE_VAR"], "manager", ag_name)
        git_code = self._fetch_source(ag_name)

        if git_code != 0:
            print("Could not fetch source")
            return

        a_setup = configparser.ConfigParser()
        a_setup.read(os.path.join(temp, "setup.zoe"))

        # Move agent files
        for dest in a_setup["INSTALL"]:
            shutil.move(
                os.path.join(temp, a_setup["INSTALL"][dest]),
                os.path.join(os.environ["ZOE_HOME"], dest))

        # Make script executable
        script = os.path.join(os.environ["ZOE_HOME"], "agents",
            ag_name, a_setup["RUN"]["script"])
        st = os.stat(script)
        os.chmod(script, st.st_mode | stat.S_IEXEC)

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

        # Update agent repo
        repo[ag_name]["installed"] = "1"
        repo[ag_name]["version"] = a_setup["INFO"]["version"]

        with open(rpath, 'w') as repofile:
            repo.write(repofile)

        print("Agent %s installed correctly." % ag_name)

        # Launch the agent
        self.launch_agent(ag_name, a_setup["RUN"]["script"])

        # Cleanup
        self._clean_temp()

    @Message(tags = ["launch"])
    def launch_agent(self, ag_name, script):
        """ Launch an agent. """
        agent_dir = os.path.join(os.environ["ZOE_HOME"], "agents", ag_name)
        if not os.path.isdir(agent_dir):
            print("Agent %s does not exist!" % ag_name)

        print("Launching agent %s..." % ag_name)
        log_path = os.path.join(os.environ["ZOE_LOGS"], ag_name + ".log")
        log_file = open(log_path, "w+")
        proc = subprocess.Popen([os.path.join(agent_dir, script)],
            stdout=log_file, stderr=log_file)
        print("Launched agent %s with PID %i" % (ag_name, proc.pid))

        pid_path = os.path.join(os.environ["ZOE_VAR"], ag_name + ".pid")
        with open(pid_path, "w+") as pf:
            print(proc.pid, file=pf)

    @Message(tags = ["remove"])
    def remove(self, ag_name):
        """ Remove an agent from the agent repository. """
        rpath = os.path.join(os.environ["ZOE_HOME"], "etc", "agents_repo.conf")
        repo = configparser.ConfigParser()
        repo.read(rpath)

        # Check if installed
        if ag_name in repo.sections():
            if repo[ag_name]["installed"] == "0":
                print("Agent %s is not installed" % ag_name)
                return
        else:
            print("Cannot find agent %s in the repository" % ag_name)

    @Message(tags = ["stop"])
    def stop_agent(self, ag_name):
        """ Stop an agent's execution. """
        pid_path = os.path.join(os.environ["ZOE_VAR"], ag_name + ".pid")
        if not os.path.isfile(pid_path):
            print("Agent %s is not running" % ag_name)

        with open(pid_path, "r") as pf:
            pid = str(int(pf.read()))

        killed = subprocess.call(["kill", pid])
        if killed != 0:
            print("Oops, something happened while stopping %s" % ag_name)
            return

        print("Stopped agent %s" % ag_name)

    def _clean_temp(self):
        """ Clean the temporal data stored in var/manager. """
        try:
            shutil.rmtree(os.path.join(os.environ["ZOE_VAR"], "manager"))
        except:
            pass

    def _fetch_source(self, ag_name):
        """ Download the source of the agent to var/manager/ag_name. """
        temp = os.path.join(os.environ["ZOE_VAR"], "manager", ag_name)
        rpath = os.path.join(os.environ["ZOE_HOME"], "etc", "agents_repo.conf")
        repo = configparser.ConfigParser()
        repo.read(rpath)

        source = repo[ag_name]["source"]
        return subprocess.call(["git", "clone", source, temp])
