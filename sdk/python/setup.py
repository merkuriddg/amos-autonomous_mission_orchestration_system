"""AMOS Plugin SDK — installable package for third-party plugin development."""

from setuptools import setup, find_packages

setup(
    name="amos-sdk",
    version="0.1.0",
    description="Plugin SDK for the AMOS Autonomous Mission Orchestration System",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Merkuri DG",
    author_email="dev@merkuri.one",
    url="https://github.com/merkuriddg/amos-autonomous_mission_orchestration_system",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "PyYAML>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    keywords="amos robotics c2 plugin sdk drone ugv uuv",
)
