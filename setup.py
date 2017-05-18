#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'Click==6.7',
    'six==1.10.0',
    'requests==2.13.0',
    'jinja2==2.9.6',
    'stevedore==1.18.0'
]

test_requirements = [
    'pytest==2.9.2'
]

setup(
    name='frkl',
    version='0.1.0',
    description="Elastic configuration files",
    long_description=readme + '\n\n' + history,
    author="Markus Binsteiner",
    author_email='makkus@posteo.de',
    url='https://github.com/makkus/frkl',
    packages=[
        'frkl',
    ],
    package_dir={'frkl':
                 'frkl'},
    entry_points={
        'console_scripts': [
            'frkl=frkl.cli:cli'
        ],
        'frkl.frk': [
            'expand_url=frkl:UrlAbbrevProcessor',
            'read=frkl:EnsureUrlProcessor',
            'deserialize=frkl:EnsurePythonObjectProcessor',
            'frklize=frkl:FrklProcessor',
            'render_template=frkl:Jinja2TemplateProcessor',
            'regex=frkl:RegexProcessor',
            'load=frkl:LoadMoreConfigsProcessor',
            'to_yaml=frkl:ToYamlProcessor',
            'merge=frkl:MergeProcessor'
        ]
    },
    include_package_data=True,
    install_requires=requirements,
    license="GNU General Public License v3",
    zip_safe=False,
    keywords='frkl',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
