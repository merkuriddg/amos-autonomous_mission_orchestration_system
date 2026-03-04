from setuptools import setup, find_packages
setup(
    name='mos_ew',
    version='9.0.0',
    packages=find_packages(),
    install_requires=['setuptools'],
    data_files=[
        ('share/mos_ew', ['package.xml']),
        ('share/mos_ew/config', ['config/ew_config.yaml']),
    ],
    entry_points={'console_scripts': [
        'ew_manager = mos_ew.ew_manager:main',
        'sigint_collector = mos_ew.sigint_collector:main',
        'cyber_ops = mos_ew.cyber_ops:main',
        'sdr_bridge = mos_ew.sdr_bridge:main',
        'rf_analyzer = mos_ew.rf_analyzer:main',
    ]},
)
