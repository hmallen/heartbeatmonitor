from setuptools import setup

with open('README.md', 'r') as fh:
    long_description = fh.read()

setup(
    name='heartbeatmonitor',
    version='0.1a23',
    author='Hunter M. Allen',
    author_email='allenhm@gmail.com',
    license='MIT',
    #packages=find_packages(),
    packages=['heartbeatmonitor'],
    #scripts=['bin/heartbeatmonitor.py'],
    install_requires=['python-dateutil>=2.7.3',
                      'slackclient>=1.2.1',
                      'json_datetime_converter>=0.1a2'],
    description='Central heartbeat monitoring application for multi-program deployment.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/hmallen/heartbeatmonitor',
    keywords=['heartbeat', 'monitor'],
    classifiers=(
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ),
)
