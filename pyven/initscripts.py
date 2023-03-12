# Copyright 2013, 2014, 2015, 2016, 2017, 2020, 2022 Andrzej Cichocki

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

from .projectinfo import ProjectInfo
from .setuproot import setuptoolsinfo
from aridity.config import ConfigCtrl
from venvpool import initlogging, scan, userbin
import logging, os, sys, venvpool

log = logging.getLogger(__name__)

def _projectinfos():
    cc = ConfigCtrl()
    cc.loadsettings()
    projectsdir = cc.node.projectsdir
    for p in sorted(os.listdir(projectsdir)):
        projectdir = os.path.join(projectsdir, p)
        if os.path.exists(os.path.join(projectdir, ProjectInfo.projectaridname)):
            yield ProjectInfo.seek(projectdir)
        else:
            setuppath = os.path.join(projectdir, 'setup.py')
            if os.path.exists(setuppath):
                if sys.version_info.major < 3:
                    log.debug("Ignore: %s", projectdir)
                else:
                    yield setuptoolsinfo(setuppath)

def main():
    initlogging()
    for info in _projectinfos():
        if not hasattr(info.config, 'name'):
            log.debug("Skip: %s", info.projectdir)
            continue
        if not info.config.executable:
            log.debug("Not executable: %s", info.projectdir)
            continue
        log.info("Scan: %s", info.projectdir)
        scan(info.projectdir, userbin, max(info.config.pyversions), venvpool.__file__)

if ('__main__' == __name__):
    main()
