from setuptools import setup
import os
from glob import glob

package_name = 'mos_core'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        (os.path.join('share', package_name, 'config'), ['config/hal_config.yaml']),
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # This line installs launch files
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools', 'pyyaml'],
    zip_safe=True,
    maintainer='rick',
    maintainer_email='rick@mavrix.com',
    description='MOS Core - Mission Operating System',
    license='Proprietary',
    entry_points={
        'console_scripts': [
            'asset_registry = mos_core.asset_registry:main',
            'autonomy_manager = mos_core.autonomy_manager:main',
            'sustainment_monitor = mos_core.sustainment_monitor:main',
            'ai_decision_engine = mos_core.ai_decision_engine:main',
            'geofence_manager = mos_core.geofence_manager:main',
            'tak_bridge = mos_core.tak_bridge:main',
            'awacs_controller = mos_core.awacs_controller:main',
            'mavlink_bridge = mos_core.mavlink_bridge:main',
        ],
    },
)
