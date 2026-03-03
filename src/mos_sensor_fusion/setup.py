from setuptools import setup

package_name = 'mos_sensor_fusion'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='rick',
    maintainer_email='rick@mavrix.com',
    description='MOS Sensor Fusion',
    license='Proprietary',
    entry_points={
        'console_scripts': [],
    },
)
