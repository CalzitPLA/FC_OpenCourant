from setuptools import setup, find_packages
import os
import sys

# Read version from version.py
version_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                          "freecad", "ORfemn", "version.py")
with open(version_path) as fp:
    exec(fp.read())

# Define package data
package_data = {
    'freecad.ORfemn': [
        '*.json',
        'resources/icons/*.svg',
        'resources/translations/*.ts',
        'resources/translations/*.qm',
    ]
}

setup(name='freecad.ORfemn',
      version=str(__version__),
      packages=find_packages(),
      package_data=package_data,
      include_package_data=True,
      maintainer="Nicholas Herrmann",
      maintainer_email="nicholas.herrmann@proton.me",
      url="https://hexascan.de",
      description="OpenRadioss Workbench for FreeCAD",
      long_description=open('README.md').read(),
      long_description_content_type='text/markdown',
      install_requires=[],
      python_requires='>=3.6',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
          'Operating System :: POSIX :: Linux',
          'Programming Language :: Python :: 3',
          'Topic :: Scientific/Engineering',
          'Topic :: Scientific/Engineering :: Physics',
      ],
      entry_points={
          'console_scripts': [],
      })
