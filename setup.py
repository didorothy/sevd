#!/usr/bin/env python
from distutils.core import setup

setup(
    name="sageexchangevirtualdesktop",
    version="1.0",
    description="Python bindings for Sage Exchange Virtual Desktop.",
    author="Positive Action for Christ",
    author_email="netadmin@positiveaction.org",
    url="https://positiveaction.org",
    packages=["sageexchangevirtualdesktop", "sageexchangevirtualdesktop.templatetags"],
    package_data={'sageexchangevirtualdesktop': ['schema.xsd',]},
    #ext_package='sageexchangevirtualdesktop',
    install_requires=['requests'],
)