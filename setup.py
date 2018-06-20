#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = [
    "frutils>=0.2.0",
    "requests>=2.13.0",
    "stevedore>=1.28.0",
    "six>=1.11.0",
]

extra_requirements = {"cli": ["Click>=6.7", "click-log>=0.2.1"]}

test_requirements = ["pytest==3.6.0"]

setup(
    name="frkl",
    version="0.3.0",
    description="Elastic dictionaries and configuration",
    long_description=readme + "\n\n" + history,
    author="Markus Binsteiner",
    author_email="makkus@frkl.io",
    url="https://gitlab.com/frkl/frkl",
    packages=["frkl"],
    package_dir={"frkl": "frkl"},
    entry_points={
        "console_scripts": ["frkl=frkl.cli:cli"],
        "frkl.frk": [
            "expand_url=frkl.processors:UrlAbbrevProcessor",
            "read=frkl.processors:EnsureUrlProcessor",
            "deserialize=frkl.processors:EnsurePythonObjectProcessor",
            "frklize=frkl.processors:FrklProcessor",
            "render_template=frkl.processors:Jinja2TemplateProcessor",
            "regex=frkl.processors:RegexProcessor",
            "load_additional_configs=frkl.processors:LoadMoreConfigsProcessor",
            "to_yaml=frkl.processors:ToYamlProcessor",
            "merge=frkl.processors:MergeProcessor",
            "id=frkl.processors:IdProcessor",
            "inject=frkl.processors:DictInjectionProcessor",
            "split=frkl.processors:YamlTextSplitProcessor",
        ],
        "frkl.collector": ["merge=frkl.callbacks:MergeResultCallback"],
        "frkl.frklists": [
             "default=frkl.frklist:DefaultFrklist"
         ]

    },
    include_package_data=True,
    install_requires=requirements,
    extra_require=extra_requirements,
    license="GNU General Public License v3",
    zip_safe=False,
    keywords="frkl",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
    ],
    test_suite="tests",
    tests_require=test_requirements,
)
