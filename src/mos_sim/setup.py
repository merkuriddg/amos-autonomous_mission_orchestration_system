from setuptools import setup

package_name = 'mos_sim'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='mos',
    description='MOS Simulated Platoon',
    entry_points={
        'console_scripts': [
            'simulated_platoon = mos_sim.simulated_platoon:main',
            'sensor_fusion = mos_sim.sensor_fusion:main',
        ],
    },
)
