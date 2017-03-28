#!/usr/bin/env python

# Copyright 2013, 2014, 2015, 2016, 2017 Andrzej Cichocki

# This file is part of pyven.
#
# pyven is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyven is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pyven.  If not, see <http://www.gnu.org/licenses/>.

import os, sys, subprocess, itertools
from pyvenimpl import licheck, miniconda

class Launcher:

    @staticmethod
    def getenv(projectpaths):
        key = 'PYTHONPATH'
        env = os.environ.copy()
        try:
            currentpaths = [env[key]] # No need to actually split.
        except KeyError:
            currentpaths = []
        env[key] = os.pathsep.join(itertools.chain(projectpaths, currentpaths))
        return env

    def __init__(self, pyversion, projectpaths):
        self.pathtopython = os.path.join(miniconda.pyversiontominiconda[pyversion].home(), 'bin', 'python')
        self.env = self.getenv(projectpaths)

    def replace(self, args):
        os.execvpe(self.pathtopython, [self.pathtopython] + args, self.env)

    def check_call(self, args):
        subprocess.check_call([self.pathtopython] + args, env = self.env)

def main():
    context = os.path.dirname(os.path.realpath(sys.argv[1]))
    while True:
        confpath = os.path.join(context, licheck.infoname)
        if os.path.exists(confpath):
            break
        parent = os.path.dirname(context)
        if parent == context:
            raise Exception(licheck.infoname)
        context = parent
    conf = licheck.loadprojectinfo(confpath)
    getlauncher(context, conf['projects'], conf['pyversions'][0]).replace(sys.argv[1:])

def getlauncher(projectdir, projects, pyversion):
    workspace = os.path.dirname(projectdir)
    return Launcher(pyversion, (os.path.join(workspace, project.replace('/', os.sep)) for project in projects))

if '__main__' == __name__:
    main()
