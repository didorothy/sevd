Sage Exchange Virtual Desktop
=============================

This is a Django app that provides integration with Sage Exchange Virtual
Desktop. The specific intent is to be able to store cards information in the
Sage Vault and to be able to Authorize and Charge cards stored in the Vault.

Not all SEVD functions are currently implemented with easy to use functions
but the module should allow a custom request to be built and sent without
having to start from scratch.

NOTE: this code was originally written for SEVD 1.0. Updates have been made
      to allow it to work with SEVD 2.0 but the style portions of the code are
      no longer supported by SEVD 2.0.


Requirements
------------

Django 1.5 or greater (required when used in a Django project)
requests - http://docs.python-requests.org/en/latest/
lxml - for unittests
bottle - for testserver


Use
---

To use this module, install it, use the template tags to render a form to send
the user to the SEVD site, and then handle processing on the return page.


Tests
-----

Unfortunately, some testing of the integration requires human interaction.
Thus there is a test server set up to allow you to run manual tests outside
of Django.

Some tests can be run from the command line that help to ensure
that parsed XML matches with the XSD, all XML data is converted into object
data, and that the objects are able to successfully render out to XML.

To run the test server:

    python -m sageexchangevirtualdesktop.testserver <hostname>

To run the CLI unittests:

    python -m sageexchangevirtualdesktop.tests


License
-------

All code has been produced for Positive Action for Christ.

MIT License

Copyright (c) 2018 Positive Action for Christ

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.