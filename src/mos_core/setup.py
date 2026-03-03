from setuptools import setup
import os
from glob import glob

package_name = 'mos_core'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # This line installs launch files
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='rick',
    maintainer_email='rick@mavrix.com',
    description='MOS Core - Mission Operating System',
    license='Proprietary',
    entry_points={
        'console_scripts': [
            'asset_registry = mos_core.asset_registry:main',
            'autonomy_manager = mos_core.autonomy_manager:main',
        ],
    },
)
