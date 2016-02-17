#!/usr/bin/env python

# Copyright 2014 Andrzej Cichocki

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

import os, subprocess
from tests import Files

def main():
    while not (os.path.exists('.hg') or os.path.exists('.svn')):
        os.chdir('..')
    agcommand = ['ag', '--noheading', '--nobreak']
    paths = list(Files.findfiles('.py', '.pyx', '.h', '.cpp', '.ui'))
    for tag in 'XXX', 'TODO', 'FIXME':
        subprocess.call(agcommand + [tag + ' LATER'] + paths)
        subprocess.call(agcommand + [tag + '(?! LATER)'] + paths)

if '__main__' == __name__:
    main()
