from setuptools import setup
import os
from glob import glob

package_name = 'mos_c2_console'

# Collect template and static files
data_files = [
    ('share/ament_index/resource_index/packages',
        ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml']),
]

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=data_files,
    install_requires=['setuptools', 'flask', 'flask-socketio'],
    zip_safe=True,
    maintainer='rick',
    maintainer_email='rick@mavrix.com',
    description='MOS C2 Console — Tactical Map Interface',
    license='Proprietary',
    entry_points={
        'console_scripts': [
            'c2_server = mos_c2_console.c2_server:main',
        ],
    },
    package_data={
        package_name: [
            'templates/*.html',
            'static/*',
        ],
    },
    include_package_data=True,
)
