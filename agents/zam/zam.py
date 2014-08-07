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

import os
import shutil
import stat
import subprocess
import zoe
from configparser import ConfigParser
from io import StringIO
from os import environ as env
from os.path import join as path
from semantic_version import Version
from zoe.deco import *

ZAM_TEMP = path(env["ZOE_VAR"], "zam")
ZAM_LIST = path(env["ZOE_HOME"], "etc", "zam", "list")
ZAM_INFO = path(env["ZOE_HOME"], "etc", "zam", "info")


@Agent(name = "zam")
class AgentManager:

    @Message(tags = ["add"])
    def add(self, name, source):
        """ Add an agent to the list. """
        alist = self.read_list()

        if name in alist.sections():
            print("Agent %s is already in the list" % name)
            return

        alist.add_section(name)
        alist[name]["source"] = str(source)
        alist[name]["installed"] = "0"
        alist[name]["version"] = ""

        self.write_list(alist)

        print("Added new agent %s to the list" % name)

    @Message(tags = ["clean"])
    def clean(self):
        """ Clean the temp data stored in var/zam. """
        try:
            shutil.rmtree(ZAM_TEMP)
        except:
            # Nothing to remove?
            pass

    @Message(tags = ["forget"])
    def forget(self, name):
        """ Remove an agent from the agent list.

            The agent must be uninstalled first, and means that in order to
            install it again, the source must be provided.
        """
        if self.installed(name):
            print("Agent %s is installed, uninstall it first" % name)
            return

        alist = self.read_list()
        if name in alist.sections():
            alist.remove_section(name)
            self.write_list(alist)

        print("Removed agent %s from agent list" % name)

    @Message(tags = ["install"])
    def install(self, name, source=None):
        """ Install an agent from source. """
        alist = self.read_list()

        if self.installed(name):
            print("Agent %s is already installed" % name)
            return

        if name not in alist.sections():
            if not source:
                print("Source not found")
                return
            else:
                self.add(name, source)
                alist = self.read_list()

        self.clean()

        temp = path(ZAM_TEMP, name)
        git_code = self.fetch(name, source)

        if git_code != 0:
            print("Could not fetch source")
            self.clean()
            return

        info_path = path(temp, "zam", "info")
        a_info = ConfigParser()
        # Add a dummy section
        a_info.read_string(StringIO(
            "[info]\n%s" % open(info_path).read()).read())

        # PREINSTALL
        preinst = path(temp, "zam", "preinst")
        if os.path.isfile(preinst):
            st = os.stat(preinst)
            os.chmod(preinst, st.st_mode | stat.S_IEXEC)
            proc = subprocess.call([preinst,])
            print("Ran preinst script, got code %i" % proc)

        # INSTALL
        # Generate list of source files
        file_list = self.move_files(name)

        # Save agent file list
        with open(path(ZAM_INFO, name + ".list"), "w+") as dfile:
            for f in file_list:
                dfile.write("%s\n" % f)

        # Make script executable
        script = path(env["ZOE_HOME"], "agents",
            name, a_info["info"]["script"])
        st = os.stat(script)
        os.chmod(script, st.st_mode | stat.S_IEXEC)

        # Add agent to the zoe.conf file
        conf_path = path(env["ZOE_HOME"], "etc", "zoe.conf")
        zconf = ConfigParser()
        zconf.read(conf_path)

        ports = []
        for sec in zconf.sections():
            if "port" in zconf[sec]:
                ports.append(int(zconf[sec]["port"]))
        ports = sorted(ports)

        if not ports:
            ports.append(env["ZOE_SERVER_PORT"])
        free_port = ports[0]
        while free_port in ports:
            free_port += 1

        zconf.add_section("agent " + name)
        zconf["agent " + name]["port"] = str(free_port)
        with open(conf_path, 'w') as configfile:
            zconf.write(configfile)

        # Update agent list
        alist[name]["installed"] = "1"
        alist[name]["version"] = a_info["info"]["version"]

        self.write_list(alist)

        print("Agent %s installed correctly" % name)

        # POSTINSTALL
        postinst = path(temp, "zam", "postinst")
        if os.path.isfile(postinst):
            st = os.stat(postinst)
            os.chmod(postinst, st.st_mode | stat.S_IEXEC)
            proc = subprocess.call([postinst,])
            print("Ran postinst script, got code %i" % proc)

        # Store config files list (if any)
        info_conf = path(temp, "zam", "conf")
        if os.path.isfile(info_conf):
            conflist = []
            with open(info_conf, "r") as conffile:
                for c in conffile.read().splitlines():
                    conflist.append(path(env["ZOE_HOME"], c))

            with open(path(ZAM_INFO, name + ".conffiles"), "w+") as stored_conf:
                for c in conflist:
                    stored_conf.write("%s\n" % c)

        # Cleanup
        self.clean()

        # Launch the agent (and register it)
        return self.launch(name, os.path.split(script)[1])

    @Message(tags = ["launch"])
    def launch(self, name, script):
        """ Launch an agent. """
        agent_dir = path(env["ZOE_HOME"], "agents", name)
        if not os.path.isdir(agent_dir):
            print("Agent %s does not exist!" % name)
            return

        print("Launching agent %s..." % name)
        log_path = path(env["ZOE_LOGS"], name + ".log")
        log_file = open(log_path, "w+")
        proc = subprocess.Popen([path(agent_dir, script)],
            stdout=log_file, stderr=log_file)

        pid_path = path(env["ZOE_VAR"], name + ".pid")
        with open(pid_path, "w+") as pf:
            pf.write(str(proc.pid))

        conf_path = path(env["ZOE_HOME"], "etc", "zoe.conf")
        zconf = ConfigParser()
        zconf.read(conf_path)

        # Force the agent to register
        port = zconf["agent " + name]["port"]
        msg = { "dst":"server", 
                "tag":"register",
                "name":name, 
                "host":env["ZOE_SERVER_HOST"], 
                "port":port }

        return zoe.MessageBuilder(msg)

    @Message(tags = ["purge"])
    def purge(self, name):
        """ Remove an agent's configuration files. """
        alist = self.read_list()
        
        # Uninstall the agent
        self.remove(name)

        # Remove config files
        confpath = path(ZAM_INFO, name + ".conffiles")
        if not os.path.isfile(confpath):
            print("Agent %s has no config files" % name)
            return

        with open(confpath, "r") as conflist:
            for c in conflist.read().splitlines():
                print("Removing %s" % c)
                try:
                    os.remove(c)
                except:
                    # Nothing to remove?
                    pass

        os.remove(confpath)

        print("Agent %s purged" % name)

    @Message(tags = ["remove"])
    def remove(self, name):
        """ Uninstall an agent.

            Any additional files (such as configuration files) are kept
            in case the agent is installed again.
        """
        if not self.installed(name):
            print("Agent %s is not installed" % name)
            return

        if self.running(name):
            self.stop(name)

        # Remove from zoe.conf
        conf_path = path(env["ZOE_HOME"], "etc", "zoe.conf")
        zconf = ConfigParser()
        zconf.read(conf_path)

        if "agent " + name in zconf.sections():
            zconf.remove_section("agent " + name)

        with open(conf_path, "w") as configfile:
            zconf.write(configfile)

        # Remove agent files and directories
        alist_path = path(ZAM_INFO, name + ".list")
        with open(alist_path, "r") as alist:
            for l in alist.read().splitlines():
                # Remove final file
                os.remove(l)
                # Remove the tree that was generated in the installation
                dirs = os.path.split(l)
                while dirs[0] != "/":
                    if os.listdir(dirs[0]):
                        break    
                    shutil.rmtree(dirs[0])
                    dirs = os.path.split(dirs[0])

        os.remove(alist_path)

        # Update agent list
        alist = self.read_list()
        alist[name]["installed"] = "0"
        alist[name]["version"] = ""
        self.write_list(alist)

        print("Agent %s uninstalled" % name)

    @Message(tags = ["stop"])
    def stop(self, name):
        """ Stop an agent's execution. """
        pid_path = path(env["ZOE_VAR"], name + ".pid")
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

    @Message(tags = ["update"])
    def update(self, name):
        """ Update an installed agent. """
        if not self.installed(name):
            print("Agent %s is not installed" % name)
            return

        alist = self.read_list()

        self.clean()

        # Get source
        temp = path(ZAM_TEMP, name)
        git_code = self.fetch(name, alist[name]["source"])

        if git_code != 0:
            print("Could not fetch source")
            self.clean()
            return

        # Parse version
        info_path = path(temp, "zam", "info")
        a_info = ConfigParser()
        a_info.read_string(StringIO(
            "[info]\n%s" % open(info_path).read()).read())

        remote_ver = Version(a_info["info"]["version"])
        local_ver = Version(alist[name]["version"])

        if remote_ver <= local_ver:
            print("Agent %s is already up-to-date" % name)
            return

        # PREUPDATE
        preupd = path(temp, "zam", "preupd")
        if os.path.isfile(preupd):
            st = os.stat(preupd)
            os.chmod(preupd, st.st_mode | stat.S_IEXEC)
            proc = subprocess.call([preupd,])
            print("Ran preupd script, got code %i" % proc)

        # UPDATE
        # Move files
        file_list = self.move_files(name, True)

        # Save agent file list
        with open(path(ZAM_INFO, name + ".list"), "w+") as dfile:
            for f in file_list:
                dfile.write("%s\n" % f)

        # Make script executable
        script = path(env["ZOE_HOME"], "agents",
            name, a_info["info"]["script"])
        st = os.stat(script)
        os.chmod(script, st.st_mode | stat.S_IEXEC)

        # Update version
        alist[name]["version"] = str(remote_ver)
        self.write_list(alist)

        # POSTUPDATE
        postupd = path(temp, "zam", "postupd")
        if os.path.isfile(postupd):
            st = os.stat(postupd)
            os.chmod(postupd, st.st_mode | stat.S_IEXEC)
            proc = subprocess.call([postupd,])
            print("Ran postupd script, got code %i" % proc)

        # Cleanup
        self.clean()

        # Restart the agent
        self.stop(name)
        return self.launch(name, os.path.split(script)[1])

    def fetch(self, name, source):
        """ Download the source of the agent to var/zam/name. """
        temp = path(ZAM_TEMP, name)
        alist = self.read_list()

        try:   
            if not source:
                src = alist[name]["source"]
            else:
                src = source
        except:
            return -1

        return subprocess.call(["git", "clone", src, temp])

    def installed(self, name):
        """ Check if an agent is installed or not. """
        alist = self.read_list()

        if name in alist.sections():
            if alist[name]["installed"] == "1":
                return True

        return False

    def move_files(self, name, updating=False):
        """ Move the files and directories to their corresponding ZOE_HOME
            counterpart.

            To be used only by install() and update()

            Returns the destination file list
        """
        source_dir = path(ZAM_TEMP, name)

        # Generate list of source files
        src_list = []
        for d in os.listdir(source_dir):
            if os.path.isdir(path(source_dir, d)) and d not in [".git", "zam"]:
                subdir = path(source_dir, d)
                for root, dirs, files in os.walk(subdir):
                    for f in files:
                        src_list.append(path(root, f))

        if updating:
            # Diff list
            for src in src_list:
                diff_list = []
                stripped = src.replace(source_dir + "/", "")
                diff_list.append(path(env["ZOE_HOME"], stripped))

            # Compare file lists and remove those not present in the update
            alist_path = path(ZAM_INFO, name + ".list")
            with open(alist_path, "r") as alist:
                for l in alist.read().splitlines():
                    if l not in diff_list:
                        # Remove final file
                        os.remove(l)
                        # Remove the generated tree
                        dirs = os.path.split(l)
                        while dirs[0] != "/":
                            if os.listdir(dirs[0]):
                                break    
                            shutil.rmtree(dirs[0])
                            dirs = os.path.split(dirs[0])

        # Move files
        file_list = []
        for src in src_list:
            stripped = src.replace(source_dir + "/", "")
            dst = os.path.dirname(path(env["ZOE_HOME"], stripped))
            
            try:
                os.makedirs(dst)
            except:
                # Tree already exists?
                pass
            
            file_list.append(shutil.copy(src, dst))

        return file_list

    def read_list(self):
        """ Read the agent list.

            Returns ConfigParser object.
        """
        alist = ConfigParser()
        alist.read(ZAM_LIST)

        return alist

    def running(self, name):
        """ Check if an agent is running. """
        # We depend on the .pid files here
        pid_path = path(env["ZOE_VAR"], name + ".pid")

        if os.path.isfile(pid_path):
            return True

        return False

    def write_list(self, lparser):
        """ Write data into agent list. """
        with open(ZAM_LIST, 'w') as listfile:
            lparser.write(listfile)
