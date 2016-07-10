#-----------------------------------------------------------------------------
# Copyright (c) 2005-2016, PyInstaller Development Team.
#
# Distributed under the terms of the GNU General Public License with exception
# for distributing bootloader.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

import os
import sys

from PyInstaller import log as logging
from PyInstaller.utils.hooks import \
    django_find_root_dir, django_dottedstring_imports, collect_data_files, \
    collect_submodules, get_module_file_attribute, is_package

logger = logging.getLogger(__name__)

hiddenimports = []
datas = []

root_dir = django_find_root_dir()
if root_dir:
    logger.info('Django root directory %s', root_dir)

    # Include hidden imports from the project settings, and their data files.
    for mod in django_dottedstring_imports(root_dir):
        if '.'.join(mod.split('.')[:-1]) in hiddenimports:
            continue  # Already seen
        if is_package(mod):
            logger.info('Collecting submodules and data for package: %s' % mod)
            hiddenimports.extend(collect_submodules(mod))
            datas.extend(collect_data_files(mod))
        else:
            hiddenimports.append(mod)

    # Include all submodules and data files from your project.
    package = os.path.basename(root_dir)
    logger.info('Collecting submodules and data for package: %s' % package)
    hiddenimports += collect_submodules(package)
    datas += collect_data_files(package)

    # Include all submodules and data files from Django. Some hidden imports
    # and data files might not be referenced and therefore discovered (e.g.
    # locales, app and project templates, etc.)
    logger.info('Collecting submodules and data for package: django')
    hiddenimports.extend(collect_submodules('django'))
    datas.extend(collect_data_files('django'))

    # Include known Django hidden imports from the standard Python library.
    if sys.version_info.major == 3:
        # Python 3.x
        hiddenimports.extend([
            'http.cookies',
            'html.parser',
        ])
    else:
        # Python 2.x
        hiddenimports.extend([
            'Cookie',
            'HTMLParser',
        ])

    # Include all discovered Django migrations as `.py` data files. It is not
    # enough to have only the collected `.pyc` modules.
    for package in hiddenimports:
        if package.endswith('.migrations'):
            logger.info(
                'Collecting migrations as data files for package: %s' %
                package)
            bits = package.split('.')
            datas += collect_data_files(
                bits[0],
                include_py_files=True,
                subdir=os.path.sep.join(bits[1:]))

else:
    logger.warn('No Django root directory could be found!')
