# Copyright 2013 BrewPi
# This file is part of BrewPi.

# BrewPi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# BrewPi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with BrewPi.  If not, see <http://www.gnu.org/licenses/>.


import pprint
import os
import sys
from time import sleep

try:
    import psutil
except ImportError:
    print "BrewPi requires psutil to run, please install it with 'sudo apt-get install python-psutil"
    sys.exit(1)

import BrewPiSocket
import BrewPiUtil as util


class BrewPiProcess:
    """
    This class represents a running BrewPi process.
    It allows other instances of BrewPi to see if there would be conflicts between them.
    It can also use the socket to send a quit signal or the pid to kill the other instance.
    """
    def __init__(self):
        self.pid = None  # pid of process
        self.cfg = None  # config file of process, full path
        self.port = None  # serial port the process is connected to
        self.sock = None  # BrewPiSocket object which the process is connected to

    def as_dict(self):
        """
        Returns: member variables as a dictionary
        """
        return self.__dict__

    def quit(self):
        """
        Sends a friendly quit message to this BrewPi process over its socket to aks the process to exit.
        """
        if self.sock is not None:
            conn = self.sock.connect()
            if conn:
                conn.send('quit')
                conn.close()  # do not shutdown the socket, other processes are still connected to it.
                print "Quit message sent to BrewPi instance with pid %s!" % self.pid
            else:
                print "Could not connect to socket of BrewPi process, maybe it just started and is not listening yet."
                print "Could not send quit message to BrewPi instance with pid %d!" % self.pid

    def kill(self):
        """
        Kills this BrewPiProcess with force, use when quit fails.
        """
        process = psutil.Process(self.pid)  # get psutil process my pid
        try:
            process.kill()
            print "SIGKILL sent to BrewPi instance with pid %d!" % self.pid
        except psutil.error.AccessDenied:
            print >> sys.stderr, "Cannot kill process %d, you need root permission to do that." % self.pid
            print >> sys.stderr, "Is the process running under the same user?"

    def conflict(self, otherProcess):
        if self.pid == otherProcess.pid:
            return 0  # this is me! I don't have a conflict with myself
        if otherProcess.cfg == self.cfg:
            return 1
        if otherProcess.port == self.port:
            return 1
        if [otherProcess.sock.type, otherProcess.sock.file, otherProcess.sock.host, otherProcess.sock.port] == \
                [self.sock.type, self.sock.file, self.sock.host, self.sock.port]:
            return 1
        return 0


class BrewPiProcesses():
    """
    This class can get all running BrewPi instances on the system as a list of BrewPiProcess objects.
    """
    def __init__(self):
        self.list = []

    def update(self):
        """
        Update the list of BrewPi processes by receiving them from the system with psutil.
        Returns: list of BrewPiProcess objects
        """
        bpList = []
        matching = [p for p in psutil.process_iter() if any('python' in p.name and 'brewpi.py'in s for s in p.cmdline)]
        for p in matching:
            bp = self.parseProcess(p)
            bpList.append(bp)
        self.list = bpList
        return self.list

    def parseProcess(self, process):
        """
        Converts a psutil process into a BrewPiProcess object by parsing the config file it has been called with.
        Params: a psutil.Process object
        Returns: BrewPiProcess object
        """
        bp = BrewPiProcess()
        bp.pid = process._pid

        cfg = [s for s in process.cmdline if '.cfg' in s]  # get config file argument
        if cfg:
            cfg = cfg[0]  # add full path to config file
        bp.cfg = util.readCfgWithDefaults(cfg)

        bp.port = bp.cfg['port']
        bp.sock = BrewPiSocket.BrewPiSocket(bp.cfg)
        return bp

    def get(self):
        """
        Returns a non-updated list of BrewPiProcess objects
        """
        return self.list

    def me(self):
        """
        Get a BrewPiProcess object of the process this function is called from
        """
        myPid = os.getpid()
        myProcess = psutil.Process(myPid)
        return self.parseProcess(myProcess)

    def findConflicts(self, process):
        """
        Finds out if the process given as argument will conflict with other running instances of BrewPi

        Params:
        process: a BrewPiProcess object that will be compared with other running instances

        Returns:
        bool: True means there are conflicts, False means no conflict
        """
        for p in self.list:
            if process.pid == p.pid:  # skip the process itself
                continue
            elif process.conflict(p):
                return 1
        return 0

    def as_dict(self):
        """
        Returns the list of BrewPiProcesses as a list of dicts, except for the process calling this function
        """
        outputList = []
        myPid = os.getpid()
        self.update()
        for p in self.list:
            if p.pid == myPid:  # do not send quit message to myself
                continue
            outputList.append(p.as_dict())
        return outputList

    def __repr__(self):
        """
        Print BrewPiProcesses as a dict when passed to a print statement
        """
        return repr(self.as_dict())

    def quitAll(self):
        """
        Ask all running BrewPi processes to exit
        """
        myPid = os.getpid()
        self.update()
        for p in self.list:
            if p.pid == myPid:  # do not send quit message to myself
                continue
            else:
                p.quit()

    def killAll(self):
        """
        Kill all running BrewPi processes with force by sending a sigkill signal.
        """
        myPid = os.getpid()
        self.update()
        for p in self.list:
            if p.pid == myPid:  # do not commit suicide
                continue
            else:
                p.kill()


def testKillAll():
    """
    Test function that prints the process list, sends a kill signal to all processes and prints the updated list again.
    """
    allScripts = BrewPiProcesses()
    allScripts.update()
    print ("Running instances of BrewPi before killing them:")
    pprint.pprint(allScripts)
    allScripts.killAll()
    allScripts.update()
    print ("Running instances of BrewPi before after them:")
    pprint.pprint(allScripts)


def testQuitAll():
    """
    Test function that prints the process list, sends a quit signal to all processes and prints the updated list again.
    """
    allScripts = BrewPiProcesses()
    allScripts.update()
    print ("Running instances of BrewPi before asking them to quit:")
    pprint.pprint(allScripts)
    allScripts.quitAll()
    sleep(2)
    allScripts.update()
    print ("Running instances of BrewPi after asking them to quit:")
    pprint.pprint(allScripts)
