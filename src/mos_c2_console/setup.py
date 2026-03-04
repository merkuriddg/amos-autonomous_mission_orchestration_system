from setuptools import setup, find_packages

package_name = 'mos_c2_console'

setup(
    name=package_name,
    version='0.4.0',
    packages=find_packages(),
    package_data={package_name: ['templates/*.html']},
    include_package_data=True,
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'flask'],
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'c2_server = mos_c2_console.c2_server:main',
        ],
    },
)
