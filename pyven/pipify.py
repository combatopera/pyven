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

'Generate setuptools files for a project.arid project.'
from .projectinfo import ProjectInfo, Req, SimpleInstallDeps
from .sourceinfo import SourceInfo
from argparse import ArgumentParser
from pkg_resources import resource_filename
from tempfile import mkdtemp
from venvpool import initlogging, Pool
import logging, os, shutil, subprocess, sys

log = logging.getLogger(__name__)

def pipify(info, version = None):
    release = version is not None
    # Allow release of project without origin:
    description, url = info.descriptionandurl() if release and info.config.github.participant else [None, None]
    config = (-info.config).childctrl()
    config.put('version', scalar = version if release else info.devversion())
    config.put('description', scalar = description)
    config.put('long_description', text = 'long_description()' if release else repr(None))
    config.put('url', scalar = url)
    if not release:
        config.put('author', scalar = None)
    config.put('py_modules', scalar = info.py_modules())
    config.put('install_requires', scalar = info.allrequires())
    config.put('scripts', scalar = info.scripts())
    config.put('console_scripts', scalar = info.console_scripts())
    config.put('universal', number = int({2, 3} <= set(info.config.pyversions)))
    # XXX: Use soak to generate these?
    nametoquote = [
        ['setup.py', 'pystr'],
        ['setup.cfg', 'void'],
    ]
    seen = set()
    for name in allbuildrequires(info):
        if name not in seen:
            seen.add(name)
            config.printf("build requires += %s", name)
    if seen != {'setuptools', 'wheel'}:
        nametoquote.append(['pyproject.toml', 'tomlquote'])
    for name, quote in nametoquote:
        config.printf('" = $(%s)', quote)
        config.processtemplate(
                resource_filename(__name__, name + '.aridt'), # TODO LATER: Make aridity get the resource.
                os.path.abspath(os.path.join(info.projectdir, name)))

def allbuildrequires(info):
    yield 'setuptools'
    yield 'wheel'
    reqs = set()
    for p in SourceInfo(info.projectdir).extpaths:
        reqs.update(p.buildrequires())
    for r in sorted(reqs):
        yield r
    for r in info.config.build.requires:
        yield r

def main():
    initlogging()
    parser = ArgumentParser()
    parser.add_argument('--transient', action = 'store_true')
    parser.add_argument('--version')
    parser.add_argument('projectdir', nargs = '?') # FIXME: When projectdir is passed in its console_scripts are not populated!
    args = parser.parse_args()
    info = ProjectInfo.seek('.') if args.projectdir is None else ProjectInfo(args.projectdir, os.path.join(args.projectdir, ProjectInfo.projectaridname))
    pipify(info, args.version)
    setupcommand(info, sys.version_info.major, args.transient, 'egg_info')

def setupcommand(info, pyversion, transient, *command):
    def setup(absexecutable):
        subprocess.check_call([absexecutable, 'setup.py'] + list(command), cwd = info.projectdir)
    buildreqs = list(allbuildrequires(info))
    if {'setuptools', 'wheel'} == set(buildreqs) and sys.version_info.major == pyversion:
        setup(sys.executable)
    else:
        with Pool(pyversion).readonlyortransient[transient](SimpleInstallDeps(buildreqs)) as venv:
            setup(venv.programpath('python'))

class VolatileReq:

    @property
    def namepart(self):
        return self.info.config.name

    def __init__(self, info):
        self.info = info

    def acceptversion(self, versionstr):
        return self.info.devversion() == versionstr

class InstallDeps:

    @property
    def pypireqs(self):
        return [VolatileReq(i) for i in self.volatileprojects] + self.fetchreqs

    def __init__(self, info, siblings, localrepo):
        self.info = info
        self.siblings = siblings
        self.localrepo = localrepo

    def __enter__(self):
        self.workspace = mkdtemp()
        editableprojects = {}
        volatileprojects = {}
        pypireqs = []
        def adddeps(i, root):
            for r in i.parsedrequires():
                name = r.namepart
                if name in editableprojects or name in volatileprojects:
                    continue
                if self.siblings:
                    siblingpath = r.siblingpath(i.contextworkspace())
                    if os.path.exists(siblingpath):
                        editableprojects[name] = j = ProjectInfo.seek(siblingpath)
                        yield j, True
                        continue
                if self.localrepo is not None:
                    repopath = os.path.join(self.localrepo, "%s.git" % name)
                    if os.path.exists(repopath):
                        if self.siblings:
                            log.warning("Not a sibling, install from repo: %s", name)
                        clonepath = os.path.join(self.workspace, name)
                        subprocess.check_call(['git', 'clone', '--depth', '1', "file://%s" % repopath, clonepath])
                        subprocess.check_call(['git', 'fetch', '--tags'], cwd = clonepath)
                        volatileprojects[name] = j = ProjectInfo.seek(clonepath)
                        yield j, False
                        continue
                if root: # Otherwise pip will handle it.
                    pypireqs.append(r.reqstr)
        infos = [(self.info, True)]
        while infos:
            log.debug("Examine deps of: %s", ', '.join(i.config.name for i, _ in infos))
            nextinfos = []
            for i, isroot in infos:
                nextinfos.extend(adddeps(i, isroot))
            infos = nextinfos
        for i in volatileprojects.values(): # Assume editables already pipified.
            pipify(i)
        self.localreqs = [i.projectdir for i in editableprojects.values()]
        self.volatileprojects = volatileprojects.values()
        self.fetchreqs = list(Req.published(pypireqs))
        return self

    def add(self, *requires):
        self.fetchreqs.extend(Req.parselines(requires))

    def invoke(self, venv):
        venv.install([i.projectdir for i in self.volatileprojects] + [r.reqstr for r in self.fetchreqs])

    def __exit__(self, *exc_info):
        shutil.rmtree(self.workspace)

if '__main__' == __name__:
    main()
