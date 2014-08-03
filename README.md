Zoe Agent Manager
=================

An agent manager for Zoe.

**status:** In development / testing

Requirements
------------

This agent requires **git** in order to work.

Installation
------------

- Clone or download the source code from this repository and move the `agents` directory into `ZOE_HOME/`

- And add the following to the **etc/zoe.conf** file (you can choose the port):

```
[agent zam]
port = YOUR_PORT
```

- Open a terminal in the directory in which you downloaded the source and run the following:

```shell
$ export ZOE_HOME=PATH_TO_YOUR_ZOE_INSTALLATION

$ chmod +x zam/preinst

$ zam/preinst
```

This will download the dependencies and create the configuration directories.

- Next time you start the server, the agent should be up and running.

What can the agent do?
----------------------

The `etc/zam/` directory contains the agent's configuration files, including a list of agents and their files.

- The `etc/zam/list` file is a list of agents for which the source URL is known and their status (installed, version).

- The `etc/zam/info` directory can contain two types of files: the `*.conffiles` contain a list of configuration files for the agent. These files will only be removed if the agent is uninstalled using `purge`. The `*.list` contain a list of regular files for the agent. These files are removed when uninstalling an agent normally.

Now, for a proper list of actions:

- `add` an agent to the repository (without installing)
- `clean` the temporary directory
- `install` an agent
- `launch` an agent (done automatically when an agent is installed)
- `purge` an agent, removing/uninstalling it and all its configuration files
- `remove/uninstall` an agent
- `remove` an agent from the agent list
- `stop` a running agent
- `update` an agent

For examples and more information on the commands, please [check the wiki](https://github.com/rmed/zoe_agent_manager/wiki).

That's nice, but how do I make my agent installable?
----------------------------------------------------

Again, [check the wiki](https://github.com/rmed/zoe_agent_manager/wiki/Making-an-installable-agent) :)
