from setuptools import setup, find_packages

setup(
    name='heartbeatmonitor',
    version='0.1',
    author='Hunter M. Allen',
    author_email='allenhm@gmail.com',
    license='MIT',
    #packages=find_packages(),
    packages=['heartbeatmonitor'],
    #scripts=['bin/heartbeatmonitor.py'],
    install_requires=['slackclient>=1.2.1'],
    description='Central heartbeat monitoring application for multi-program deployment',
    keywords=['heartbeat', 'monitor'],
)
