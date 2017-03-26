#!/usr/bin/env python3

# Copyright 2013, 2014, 2015, 2016 Andrzej Cichocki

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

import os, subprocess, itertools, pyven, tests

condaversion = '3.16.0'

def main():
    conf = {}
    exec(compile(open('project.info').read(), 'project.info', 'exec'), conf)
    projectdir = os.getcwd()
    os.chdir(os.path.dirname(projectdir))
    for project in itertools.chain(['pyven'], conf['projects']):
        if not os.path.exists(project.replace('/', os.sep)): # Allow a project to depend on a subdirectory of itself.
            subprocess.check_call(['git', 'clone', "https://github.com/combatopera/%s.git" % project])
    os.environ['PATH'] = "%s%s%s" % (os.path.join(os.getcwd(), 'pyven'), os.pathsep, os.environ['PATH'])
    subprocess.check_call(['wget', '--no-verbose', "http://repo.continuum.io/miniconda/Miniconda-%s-Linux-x86_64.sh" % condaversion])
    command = ['bash', "Miniconda-%s-Linux-x86_64.sh" % condaversion, '-b', '-p', 'miniconda']
    subprocess.check_call(command)
    command = [os.path.join('miniconda', 'bin', 'conda'), 'install', '-yq', 'pyflakes', 'nose']
    command.extend(conf['deps'])
    subprocess.check_call(command)
    os.environ['MINICONDA_HOME'] = os.path.join(os.getcwd(), 'miniconda')
    os.chdir(projectdir)
    # Equivalent to running tests.py directly but with one fewer process launch:
    pyven.mainimpl([tests.__file__])

if '__main__' == __name__:
    main()
