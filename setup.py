from setuptools import setup, find_packages

setup(
    name="HeartbeatMonitor",
    version="0.1",
    #packages=find_packages(),
    #scripts=['heartbeatmonitor.py'],
    packages=['heartbeatmonitor'],
    package_dir={'heartbeatmonitor': 'heartbeatmonitor'},

    install_requires=['slackclient>=1.2.1'],

    # metadata for upload to PyPI
    author="Hunter M. Allen",
    author_email="allenhm@gmail.com",
    description="Central heartbeat monitoring application for multi-program deployment",
    license="Creative Commons Attribution-Noncommercial-Share Alike license",
)
