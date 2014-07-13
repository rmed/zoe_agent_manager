#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Zoe Agent Installer - https://github.com/RMed/zoe_agent_installer
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
import subprocess
import zoe
from zoe.deco import *


@Agent(name = "installer")
class InstallerAgent:
    """ Installer Agent

        This agent receives messages of the form:

        agent=agent_name&source=agent_source

        Where *agent_name* is the name of the agent and *agent_source*
        the git repository from which to download the agent. It can be
        presented in two ways:

        - user/agent : GitHub repository
        - git://path_to_repo : regular git repository
    """

    @Message(tags = ["install"])
    def install(self, ag_name, ag_source):
        """ Install new agent from source. """
        temp = os.environ['ZOE_HOME'] + "temp/" + ag_name
        fetch_source = subprocess.call(["git", "clone", ag_source, temp])

        if fetch_source != 0:
            self._listener.log("installer", "info",
                "Could not fetch source from " + ag_source)
            return

        agent_info = configparser.ConfigParser()
        agent_info.read(os.path.join(temp, "agent.zoe"))

        for dest in agent_info['INSTALL']:
            shutil.copytree(
                os.path.join(temp + agent_info['INSTALL'][dest]),
                os.path.join(os.environ['ZOE_HOME'], dest))      
