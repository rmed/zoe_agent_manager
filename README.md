Zoe Agent Manager
=================

An agent manager for Zoe.

**status:** In development / testing

Requirements
------------

This agent requires **git** in order to work.

Installation
------------

In order to install the agent, clone or download the source code in this repository and move the following files and directories accordingly (paths relative to the Zoe root):

```
manager/ ~> agents/manager
conf/agents_repo.conf ~> etc/agents_repo.conf
```

Edit the **etc/agents_repo.conf** file and add the following:

```
data = ZOE_HOME/agents/manager;ZOE_HOME/etc/agents_repo.conf
```

Where *ZOE_HOME* is the absolute path to the root directory in which Zoe is located.

And add the following to the **etc/zoe.conf** file (you can choose the port):

```
[agent manager]
port = YOUR_PORT
```

Next time you start the server, the agent will be up and running.

What can the agent do?
----------------------

First of all, the *etc/agents_repo.conf* file will contain information on the agents you install (such as name, where to find the source code for installation, version, etc.)

Now, for a proper list of actions:

- **Add** an agent to the repository (without installing)
- **Clean** the temporary directory
- **Install** an agent (need to add it first!)
- **Launch** an agent (done automatically when an agent is installed)
- **Purge** an agent's data files (if any)
- **Remove** an agent from the repository
- **Stop** a running agent
- **Uninstall** an agent

For examples and more information on the commands, please check the wiki.

That's nice, but how do I make my agent installable?
----------------------------------------------------

Again, check the wiki :)
