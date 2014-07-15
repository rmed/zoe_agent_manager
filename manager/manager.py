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
    def add(self, name, source):
        """ Add an agent to the repository. """
        repo = self.read_repo()

        if name in repo.sections():
            print("Agent %s is already in the repository" % name)
            return

        repo.add_section(name)
        repo[name]["source"] = str(source)
        repo[name]["installed"] = "0"
        repo[name]["version"] = ""
        repo[name]["data"] = ""

        self.write_repo(repo)

        print("Added new agent %s to the repo" % name)

    @Message(tags = ["clean"])
    def clean(self):
        """ Clean the temp data stored in var/manager. """
        try:
            shutil.rmtree(os.path.join(os.environ["ZOE_VAR"], "manager"))
        except:
            # Nothing to remove?
            pass

    @Message(tags = ["install"])
    def install(self, name):
        """ Install an agent from source. """
        repo = self.read_repo()

        if name not in repo.sections():
            print("Agent not found in repository")
            return

        if self.installed(name):
            print("Agent %s is already installed" % name)
            return

        temp = os.path.join(os.environ["ZOE_VAR"], "manager", name)
        git_code = self.fetch(name)

        if git_code != 0:
            print("Could not fetch source")
            return

        a_setup = configparser.ConfigParser()
        a_setup.read(os.path.join(temp, "setup.zoe"))

        # Move agent files
        data_list = []
        for dest in a_setup["INSTALL"]:
            shutil.move(
                os.path.join(temp, a_setup["INSTALL"][dest]),
                os.path.join(os.environ["ZOE_HOME"], dest))
            data_list.append(os.path.join(os.environ["ZOE_HOME"], dest))

        # Make script executable
        script = os.path.join(os.environ["ZOE_HOME"], "agents",
            name, a_setup["RUN"]["script"])
        st = os.stat(script)
        os.chmod(script, st.st_mode | stat.S_IEXEC)

        # Add agent to the zoe.conf file
        conf_path = os.path.join(os.environ["ZOE_HOME"], "etc", "zoe.conf")
        zconf = configparser.ConfigParser()
        zconf.read(conf_path)

        ports = []
        for sec in zconf.sections():
            if "port" in zconf[sec]:
                ports.append(int(zconf[sec]["port"]))
        ports = sorted(ports)

        free_port = ports[0]
        while free_port in ports:
            free_port += 1

        zconf.add_section("agent " + name)
        zconf["agent " + name]["port"] = str(free_port)
        with open(conf_path, 'w') as configfile:
            zconf.write(configfile)

        # Update agent repo
        repo[name]["installed"] = "1"
        repo[name]["version"] = a_setup["INFO"]["version"]
        repo[name]["data"] = ';'.join(data_list)

        self.write_repo(repo)

        print("Agent %s installed correctly." % name)

        # Launch the agent
        self.launch(name, a_setup["RUN"]["script"])

        # Cleanup
        self.clean()

    @Message(tags = ["launch"])
    def launch(self, name, script):
        """ Launch an agent. """
        agent_dir = os.path.join(os.environ["ZOE_HOME"], "agents", name)
        if not os.path.isdir(agent_dir):
            print("Agent %s does not exist!" % name)
            return

        print("Launching agent %s..." % name)
        log_path = os.path.join(os.environ["ZOE_LOGS"], name + ".log")
        log_file = open(log_path, "w+")
        proc = subprocess.Popen([os.path.join(agent_dir, script)],
            stdout=log_file, stderr=log_file)
        print("Launched agent %s with PID %i" % (name, proc.pid))

        pid_path = os.path.join(os.environ["ZOE_VAR"], name + ".pid")
        with open(pid_path, "w+") as pf:
            print(proc.pid, file=pf)

    @Message(tags = ["remove"])
    def remove(self, name):
        """ Remove an agent from the agent repository. """
        repo = self.read_repo()

        if name not in repo.sections():
            print("Cannot find agent %s in the repository" % name)
            return

        if repo[name]["installed"] == "1":
            print("Agent %s is installed, uninstall it first" % name)
            return

        repo.remove_section(name)
        self.write_repo(repo)

    @Message(tags = ["stop"])
    def stop(self, name):
        """ Stop an agent's execution. """
        pid_path = os.path.join(os.environ["ZOE_VAR"], name + ".pid")
        if not self.running(name):
            print("Agent %s is not running" % name)
            return

        with open(pid_path, "r") as pf:
            pid = str(int(pf.read()))

        killed = subprocess.call(["kill", pid])
        if killed != 0:
            print("Oops, something happened while stopping %s" % name)
            return

        os.remove(pid_path)

        print("Stopped agent %s" % name)

    @Message(tags = ["uninstall"])
    def uninstall(self, name):
        """ Uninstall an agent.

            Any additional files (such as configuration files) are kept
            in case the agent is installed again.
        """
        if not self.installed(name):
            print("Agent %s is not installed" % name)
            return

        if self.running(name):
            self.stop(name)

        ag_path = os.path.join(os.environ["ZOE_HOME"], "agents", name)
        shutil.rmtree(ag_path)

        repo = self.read_repo()
        repo[name]["installed"] = "0"
        repo[name]["version"] = ""

        self.write_repo(repo)

        print("Agent %s uninstalled" % name)

    def fetch(self, name):
        """ Download the source of the agent to var/manager/name. """
        temp = os.path.join(os.environ["ZOE_VAR"], "manager", name)
        repo = self.read_repo()

        source = repo[name]["source"]
        return subprocess.call(["git", "clone", source, temp])

    def installed(self, name):
        """ Check if an agent is installed or not. """
        repo = self.read_repo()

        if name in repo.sections():
            if repo[name]["installed"] == "1":
                return True

        return False

    def read_repo(self):
        """ Read the agents repository.

            Returns ConfigParser object.
        """
        rpath = os.path.join(os.environ["ZOE_HOME"], "etc", "agents_repo.conf")
        repo = configparser.ConfigParser()
        repo.read(rpath)

        return repo

    def running(self, name):
        """ Check if an agent is running. """
        # We depend on the .pid files here
        pid_path = os.path.join(os.environ["ZOE_VAR"], name + ".pid")

        if os.path.isfile(pid_path):
            return True

        return False

    def write_repo(self, rparser):
        """ Write data into repository. """
        rpath = os.path.join(os.environ["ZOE_HOME"], "etc", "agents_repo.conf")
        with open(rpath, 'w') as repofile:
            rparser.write(repofile)
