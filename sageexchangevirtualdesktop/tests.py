"""Unittests."""

from decimal import Decimal
import os.path
import re
from unittest import TestCase
import warnings
import xml.etree.ElementTree as ET

import lxml.etree

from . import sevd

# we are trying to parse the XSD once.
try:
    with open(os.path.join(os.path.dirname(__file__), 'schema.xsd'), 'rb') as f:
        XML_SCHEMA = lxml.etree.XML(f.read())
    XML_PARSER = lxml.etree.XMLParser(schema=lxml.etree.XMLSchema(XML_SCHEMA))
except Exception as ex:
    warnings.warn('Could not open schema. %s' % ex)
    XML_SCHEMA = None
    XML_PARSER = None

def validate_xml_with_xsd(xml):
    '''If we could successfully get the XML_PARSER object then this will throw exceptions for invalid XML.'''
    global XML_PARSER
    if XML_PARSER is not None:
        lxml.etree.fromstring(xml, parser=XML_PARSER)

class TestColorRegex(TestCase):
    def test_color_regex(self):
        # test expected strings
        self.assertNotEqual(sevd.COLOR_REGEX.match(''), None)
        self.assertNotEqual(sevd.COLOR_REGEX.match('213'), None)
        self.assertNotEqual(sevd.COLOR_REGEX.match('AFE'), None)
        self.assertNotEqual(sevd.COLOR_REGEX.match('bcd'), None)
        self.assertNotEqual(sevd.COLOR_REGEX.match('123456'), None)
        self.assertNotEqual(sevd.COLOR_REGEX.match('AF3E45'), None)
        self.assertNotEqual(sevd.COLOR_REGEX.match('ef8ee0'), None)

        # test expected failures
        self.assertEqual(sevd.COLOR_REGEX.match('1'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('F'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('d'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('12'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('AF'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('ed'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('1245'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('AFEe'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('ed4b'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('12678'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('AFE13'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('edabc'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('1234567'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('AFEFDE3'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('edffeeaa'), None)

        self.assertEqual(sevd.COLOR_REGEX.match('RRR'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('AFGGEE'), None)
        self.assertEqual(sevd.COLOR_REGEX.match('zze'), None)


class TestGetterSetter(TestCase):

    def create_class(self, set_func):
        '''Creates a class used to test setter functions.'''
        private_name = '_prop'
        class X(object):
            _prop = None
            prop = property(sevd.get_func(private_name), set_func(private_name))

        return X

    def test_get_func(self):
        private_name = '_prop'
        class X(object):
            _prop = None
            prop = property(sevd.get_func(private_name), lambda o,v: setattr(o, private_name, v))

        x = X()
        self.assertEqual(x.prop, None)
        x.prop = None
        self.assertEqual(x.prop, None)
        x.prop = 'Test'
        self.assertEqual(x.prop, 'Test')

    def test_string_set_func(self):
        X = self.create_class(sevd.string_set_func)

        x = X()
        self.assertEqual(x.prop, None)
        x.prop = None
        self.assertEqual(x.prop, None)
        x.prop = 'test'
        self.assertEqual(x.prop, 'test')
        x.prop = 12
        self.assertEqual(x.prop, 12)

    def test_int_set_func(self):
        X = self.create_class(sevd.int_set_func)

        x = X()
        self.assertEqual(x.prop, None)
        x.prop = None
        self.assertEqual(x.prop, None)

        x.prop = 12
        x.prop = '39'

        self.assertRaises(ValueError, setattr, x, 'prop', 'test')
        self.assertRaises(ValueError, setattr, x, 'prop', 12.1223)
        self.assertRaises(ValueError, setattr, x, 'prop', x)

    def test_double_set_func(self):
        X = self.create_class(sevd.double_set_func)

        x = X()
        self.assertEqual(x.prop, None)
        x.prop = None
        self.assertEqual(x.prop, None)

        x.prop = 1.2322
        x.prop = 3.323e122
        x.prop = '3.2343'
        x.prop = '2.3332E10'

        self.assertRaises(ValueError, setattr, x, 'prop', 'test')

    def test_boolean_set_func(self):
        X = self.create_class(sevd.boolean_set_func)

        x = X()
        self.assertEqual(x.prop, None)
        x.prop = None
        self.assertEqual(x.prop, None)

        x.prop = 'true'
        x.prop = 'false'
        x.prop = True
        x.prop = False

        self.assertRaises(ValueError, setattr, x, 'prop', 'test')
        self.assertRaises(ValueError, setattr, x, 'prop', 2.343)
        self.assertRaises(ValueError, setattr, x, 'prop', 3)

    def test_class_set_func(self):
        class X(object):
            _prop = None
            prop = property(sevd.get_func('_prop'), sevd.class_set_func('_prop', Decimal))

        x = X()

        self.assertEqual(x.prop, None)
        x.prop = None
        self.assertEqual(x.prop, None)

        x.prop = Decimal(1.2)
        x.prop = Decimal('1.232')

        self.assertRaises(ValueError, setattr, x, 'prop', 'Test')
        self.assertRaises(ValueError, setattr, x, 'prop', 1.23)
        self.assertRaises(ValueError, setattr, x, 'prop', 35)
        self.assertRaises(ValueError, setattr, x, 'prop', True)

    def test_regex_set_func(self):
        clss = [
            self.create_class(sevd.regex_set_func('^[ABC]+$')),
            self.create_class(sevd.regex_set_func(re.compile('^[ABC]+$'))),
        ]

        for cls in clss:
            x = cls()

            self.assertEqual(x.prop, None)
            x.prop = None
            self.assertEqual(x.prop, None)

            x.prop = 'ABBBBA'
            x.prop = 'ABBCC'

            self.assertRaises(ValueError, setattr, x, 'prop', 'DkJS')
            self.assertRaises(ValueError, setattr, x, 'prop', '')
            self.assertRaises(ValueError, setattr, x, 'prop', 1)
            self.assertRaises(ValueError, setattr, x, 'prop', 23.55)
            self.assertRaises(ValueError, setattr, x, 'prop', True)

    def test_required_regex_set_func(self):
        clss = [
            self.create_class(sevd.required_regex_set_func('^[ABC]*$')),
            self.create_class(sevd.required_regex_set_func(re.compile('^[ABC]*$'))),
        ]

        for cls in clss:
            x = cls()

            self.assertEqual(x.prop, None)
            x.prop = None
            self.assertEqual(x.prop, '')

            x.prop = ''
            x.prop = 'ABBBBA'
            x.prop = 'ABBCC'

            self.assertRaises(ValueError, setattr, x, 'prop', 'DkJS')
            self.assertRaises(ValueError, setattr, x, 'prop', 1)
            self.assertRaises(ValueError, setattr, x, 'prop', 23.55)
            self.assertRaises(ValueError, setattr, x, 'prop', True)

    def test_transaction_type_set_func(self):
        X = self.create_class(sevd.transaction_type_set_func)

        x = X()

        self.assertEqual(x.prop, None)
        x.prop = None
        self.assertEqual(x.prop, None)

        for val in sevd.TransactionBaseType.TRANSACTION_TYPES:
            x.prop = val

        self.assertRaises(ValueError, setattr, x, 'prop', 'AB')
        self.assertRaises(ValueError, setattr, x, 'prop', 123)
        self.assertRaises(ValueError, setattr, x, 'prop', 4.54)
        self.assertRaises(ValueError, setattr, x, 'prop', True)

    def test_schedule_set_func(self):
        X = self.create_class(sevd.schedule_set_func)

        x = X()

        self.assertEqual(x.prop, None)
        x.prop = None
        self.assertEqual(x.prop, None)

        for val in sevd.RecurringType.SCHEDULE_OPTIONS:
            x.prop = val

        self.assertRaises(ValueError, setattr, x, 'prop', 'AB')
        self.assertRaises(ValueError, setattr, x, 'prop', 123)
        self.assertRaises(ValueError, setattr, x, 'prop', 4.54)
        self.assertRaises(ValueError, setattr, x, 'prop', True)

    def test_nonbusiness_day_set_func(self):
        X = self.create_class(sevd.nonbusiness_day_set_func)

        x = X()

        self.assertEqual(x.prop, None)
        x.prop = None
        self.assertEqual(x.prop, None)

        for val in sevd.RecurringType.NONBUSINESS_DAY_OPTIONS:
            x.prop = val

        self.assertRaises(ValueError, setattr, x, 'prop', 'AB')
        self.assertRaises(ValueError, setattr, x, 'prop', 123)
        self.assertRaises(ValueError, setattr, x, 'prop', 4.54)
        self.assertRaises(ValueError, setattr, x, 'prop', True)

    def test_vault_service_set_func(self):
        X = self.create_class(sevd.vault_service_set_func)

        x = X()

        self.assertEqual(x.prop, None)
        x.prop = None
        self.assertEqual(x.prop, None)

        for val in sevd.VaultStorageType.VAULT_SERVICE_OPTIONS:
            x.prop = val

        self.assertRaises(ValueError, setattr, x, 'prop', 'AB')
        self.assertRaises(ValueError, setattr, x, 'prop', 123)
        self.assertRaises(ValueError, setattr, x, 'prop', 4.54)
        self.assertRaises(ValueError, setattr, x, 'prop', True)

    def test_batch_payment_set_func(self):
        X = self.create_class(sevd.batch_payment_set_func)

        x = X()

        self.assertEqual(x.prop, None)
        x.prop = None
        self.assertEqual(x.prop, None)

        for val in sevd.BatchType.BATCH_PAYMENT_OPTIONS:
            x.prop = val

        self.assertRaises(ValueError, setattr, x, 'prop', 'AB')
        self.assertRaises(ValueError, setattr, x, 'prop', 123)
        self.assertRaises(ValueError, setattr, x, 'prop', 4.54)
        self.assertRaises(ValueError, setattr, x, 'prop', True)


class TestXML(TestCase):

    def test_sale_request_parse(self):
        content = '''<?xml version="1.0" encoding="utf-16"?>
        <Request_v1 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>5ea9747c-12a4-46af-970f-f8a92f6d4f65</TransactionID>
                        <TransactionType>11</TransactionType>
                        <Reference1>INV# 886478943</Reference1>
                        <Amount>1892.59</Amount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>Jane</FirstName>
                            <MI> </MI>
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>67890 Road</AddressLine1>
                            <AddressLine2></AddressLine2>
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>jane.doe@sagepayments.com</EmailAddress>
                            <Telephone></Telephone>
                            <Fax></Fax>
                        </Address>
                    </Customer>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-16'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-16')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>e856a127-8527-431c-807f-6efacd8bdf83</TransactionID>
                        <TransactionType>01</TransactionType>
                        <Reference1>INV# 451777674</Reference1>
                        <Amount>2152.92</Amount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>John</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>12345 Street</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>john.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                    <VaultStorage>
                        <GUID>dd83d7559a274fb2b66e774a4febced7</GUID>
                        <Service>RETRIEVE</Service>
                    </VaultStorage>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>e856a127-8527-431c-807f-6efacd8bdf83</TransactionID>
                        <TransactionType>11</TransactionType>
                        <Reference1>INV# 451777674</Reference1>
                        <Amount>2152.92</Amount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>John</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>12345 Street</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>john.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                    <VaultStorage>
                        <Service>CREATE</Service>
                    </VaultStorage>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_authorization_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>5ea9747c-12a4-46af-970f-f8a92f6d4f65</TransactionID>
                        <TransactionType>12</TransactionType>
                        <Reference1>INV# 886478943</Reference1>
                        <Amount>1892.59</Amount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>Jane</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>67890 Road</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>jane.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>e856a127-8527-431c-807f-6efacd8bdf83</TransactionID>
                        <TransactionType>02</TransactionType>
                        <Reference1>INV# 451777674</Reference1>
                        <Amount>2152.92</Amount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>John</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>12345 Street</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>john.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                    <VaultStorage>
                        <GUID>dd83d7559a274fb2b66e774a4febced7</GUID>
                        <Service>RETRIEVE</Service>
                    </VaultStorage>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_capture_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>0405aa29-9be2-4c46-b8b0-b103e25a39b6</TransactionID>
                        <TransactionType>13</TransactionType>
                        <Amount>4577.52</Amount>
                        <VANReference>CBK9A0j650</VANReference>
                    </TransactionBase>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>0405aa29-9be2-4c46-b8b0-b103e25a39b6</TransactionID>
                        <TransactionType>03</TransactionType>
                        <Amount>4577.52</Amount>
                        <VANReference>CBK9A0j650</VANReference>
                    </TransactionBase>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_force_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>5ea9747c-12a4-46af-970f-f8a92f6d4f65</TransactionID>
                        <TransactionType>15</TransactionType>
                        <Reference1>INV# 886478943</Reference1>
                        <Amount>1892.59</Amount>
                        <AuthCode>123456</AuthCode>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>Jane</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>67890 Road</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>jane.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>e856a127-8527-431c-807f-6efacd8bdf83</TransactionID>
                        <TransactionType>05</TransactionType>
                        <Reference1>INV# 451777674</Reference1>
                        <Amount>2152.92</Amount>
                        <AuthCode>123456</AuthCode>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>John</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>12345 Street</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>john.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                    <VaultStorage>
                        <GUID>dd83d7559a274fb2b66e774a4febced7</GUID>
                        <Service>RETRIEVE</Service>
                    </VaultStorage>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_level2_sale_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>5ea9747c-12a4-46af-970f-f8a92f6d4f65</TransactionID>
                        <TransactionType>11</TransactionType>
                        <Reference1>INV# 886478943</Reference1>
                        <Amount>1892.59</Amount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>Jane</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>67890 Road</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>jane.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                    <Level2>
                        <CustomerNumber>123456789012</CustomerNumber>
                        <TaxAmount>92.59</TaxAmount>
                    </Level2>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_void_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>782ad8d0-0dd2-4763-8d64-cc9fddfad441</TransactionID>
                        <TransactionType>04</TransactionType>
                        <VANReference>ABL9LKQaI0</VANReference>
                    </TransactionBase>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_credit_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>0405aa29-9be2-4c46-b8b0-b103e25a39b6</TransactionID>
                        <TransactionType>16</TransactionType>
                        <Amount>4577.52</Amount>
                        <VANReference>CBK9A0j650</VANReference>
                    </TransactionBase>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>0405aa29-9be2-4c46-b8b0-b103e25a39b6</TransactionID>
                        <TransactionType>06</TransactionType>
                        <Amount>4577.52</Amount>
                        <VANReference>CBK9A0j650</VANReference>
                    </TransactionBase>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_batch_inquiry_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Batch>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
                <Net>-1</Net>
                <Count>-1</Count>
                <BatchPayment>CREDITCARD</BatchPayment>
            </Batch>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_batch_close_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Batch>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
                <Net>2561.23</Net>
                <Count>5</Count>
                <BatchPayment>CREDITCARD</BatchPayment>
            </Batch>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Batch>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
                <Net>0</Net>
                <Count>0</Count>
                <BatchPayment>CREDITCARD</BatchPayment>
            </Batch>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_vault_operation_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <VaultOperation>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
                <VaultStorage>
                    <Service>CREATE</Service>
                </VaultStorage>
                <VaultID>2341234-12431243-2341235</VaultID>
            </VaultOperation>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <VaultOperation>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
                <VaultStorage>
                    <Service>UPDATE</Service>
                    <GUID>sfdas-ee3u38d-dagdi3-efad83</GUID>
                </VaultStorage>
                <VaultID>2341234-12431243-2341235</VaultID>
            </VaultOperation>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <VaultOperation>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
                <VaultStorage>
                    <Service>DELETE</Service>
                    <GUID>sfdas-ee3u38d-dagdi3-efad83</GUID>
                </VaultStorage>
                <VaultID>2341234-12431243-2341235</VaultID>
            </VaultOperation>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <VaultOperation>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
                <VaultStorage>
                    <Service>RETRIEVE</Service>
                    <GUID>sfdas-ee3u38d-dagdi3-efad83</GUID>
                </VaultStorage>
                <VaultID>2341234-12431243-2341235</VaultID>
            </VaultOperation>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <VaultOperation>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
                <VaultStorage>
                    <Service>UPDATE</Service>
                    <GUID>sfdas-ee3u38d-dagdi3-efad83</GUID>
                </VaultStorage>
                <VaultID>2341234-12431243-2341235</VaultID>
            </VaultOperation>
            <UI>
                <VaultOperation>
                    <AccountNumber>
                        <Enabled>true</Enabled>
                        <Visible>false</Visible>
                    </AccountNumber>
                </VaultOperation>
            </UI>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <VaultOperation>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
                <VaultStorage>
                    <Service>UPDATE</Service>
                    <GUID>sfdas-ee3u38d-dagdi3-efad83</GUID>
                </VaultStorage>
                <VaultID>2341234-12431243-2341235</VaultID>
            </VaultOperation>
            <UI>
                <VaultOperation>
                    <AccountNumber>
                        <Enabled>false</Enabled>
                        <Visible>true</Visible>
                    </AccountNumber>
                </VaultOperation>
            </UI>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_vault_account_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <VaultAccount>
                <Company>
                    <Name>Test Account - Vault</Name>
                    <Address>
                        <AddressLine1>12345 Street</AddressLine1>
                        <City>Brownsville</City>
                        <State>Texas</State>
                        <ZipCode>78520</ZipCode>
                        <EmailAddress>none@sagepayments.com</EmailAddress>
                        <Telephone>956-548-9400</Telephone>
                        <Fax>956-548-9416</Fax>
                    </Address>
                </Company>
                <Contact>
                    <Name>
                        <FirstName>John</FirstName>
                        <LastName>Doe</LastName>
                    </Name>
                    <Address />
                    <Company>
                        <Address />
                    </Company>
                </Contact>
            </VaultAccount>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_account_query_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <AccountQuery>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
            </AccountQuery>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_transaction_status_query_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <TransactionStatusQueries>
                <TransactionStatusQueryType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionID>sdfasdf089273412903479a87sa</TransactionID>
                </TransactionStatusQueryType>
            </TransactionStatusQueries>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_vault_status_query_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <VaultStatusQuery>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
                <VaultID>sdfasdf089273412903479a87sa</VaultID>
            </VaultStatusQuery>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_multipayment_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>5ea9747c-12a4-46af-970f-f8a92f6d4f65</TransactionID>
                        <TransactionType>11</TransactionType>
                        <Reference1>INV# 886478943</Reference1>
                        <Amount>1892.59</Amount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>Jane</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>67890 Road</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>jane.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                </PaymentType>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>4fa9747c-13a2-46af-970f-f8a92f5d4f61</TransactionID>
                        <TransactionType>11</TransactionType>
                        <Reference1>INV# 7563456</Reference1>
                        <Amount>50.50</Amount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>John</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>4567 Street</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>john.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_splitpayment_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <IsSplitPayment>true</IsSplitPayment>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>5ea9747c-12a4-46af-970f-f8a92f6d4f65</TransactionID>
                        <TransactionType>12</TransactionType>
                        <Reference1>INV# 886478943</Reference1>
                        <Amount>1.00</Amount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>Jane</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>67890 Road</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>jane.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                </PaymentType>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999990</MerchantID>
                        <MerchantKey>D8H8M8F6K7A7</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>5ea9747c-12a4-46af-970f-f8a92f6d4f65</TransactionID>
                        <TransactionType>12</TransactionType>
                        <Reference1>INV# 886478943</Reference1>
                        <Amount>1.00</Amount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>John</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>67890 Road</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>jane.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                </PaymentType>
            </Payments>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    def test_user_interface_request_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>5ea9747c-12a4-46af-970f-f8a92f6d4f65</TransactionID>
                        <TransactionType>12</TransactionType>
                        <Reference1>INV# 886478943</Reference1>
                        <Amount>1.00</Amount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>Jane</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>67890 Road</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>jane.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                </PaymentType>
            </Payments>
            <UI>
                <Display>
                    <Header>true</Header>
                    <SupportLink>false</SupportLink>
                    <CheckPayment>false</CheckPayment>
                    <CardPayment>true</CardPayment>
                    <SELogo>true</SELogo>
                </Display>
                <Theme>
                    <MainFontColor>#800000</MainFontColor>
                    <MainBackColor>#FFF8DC</MainBackColor>
                    <HeaderBackColor>#D2691E</HeaderBackColor>
                    <TotalsBoxBackColor>#DEB887</TotalsBoxBackColor>
                    <DividerBackColor>#CD853F</DividerBackColor>
                </Theme>
                <SinglePayment>
                    <TransactionBase>
                        <Reference1>
                            <Enabled>false</Enabled>
                            <Visible>false</Visible>
                        </Reference1>
                        <SubtotalAmount>
                            <Enabled>false</Enabled>
                            <Visible>true</Visible>
                        </SubtotalAmount>
                        <TaxAmount>
                            <Enabled>true</Enabled>
                            <Visible>true</Visible>
                        </TaxAmount>
                        <ShippingAmount>
                            <Enabled>false</Enabled>
                            <Visible>false</Visible>
                        </ShippingAmount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </FirstName>
                            <LastName>
                                <Enabled>false</Enabled>
                                <Visible>false</Visible>
                            </LastName>
                        </Name>
                        <Address>
                            <AddressLine1>
                                <Enabled>false</Enabled>
                                <Visible>false</Visible>
                            </AddressLine1>
                            <City>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </City>
                            <State>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </State>
                            <ZipCode>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </ZipCode>
                            <Country>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </Country>
                            <EmailAddress>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </EmailAddress>
                            <Telephone>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </Telephone>
                        </Address>
                    </Customer>
                </SinglePayment>
            </UI>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <VaultOperation>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
                <VaultStorage>
                    <Service>UPDATE</Service>
                    <GUID>sfdas-ee3u38d-dagdi3-efad83</GUID>
                </VaultStorage>
                <VaultID>2341234-12431243-2341235</VaultID>
            </VaultOperation>
            <UI>
                <Display>
                    <Header>true</Header>
                    <SupportLink>false</SupportLink>
                    <CheckPayment>false</CheckPayment>
                    <CardPayment>true</CardPayment>
                    <SELogo>true</SELogo>
                </Display>
                <Theme>
                    <MainFontColor>#800000</MainFontColor>
                    <MainBackColor>#FFF8DC</MainBackColor>
                    <HeaderBackColor>#D2691E</HeaderBackColor>
                    <TotalsBoxBackColor>#DEB887</TotalsBoxBackColor>
                    <DividerBackColor>#CD853F</DividerBackColor>
                </Theme>
                <VaultOperation>
                    <AccountNumber>
                        <Enabled>false</Enabled>
                        <Visible>false</Visible>
                    </AccountNumber>
                </VaultOperation>
            </UI>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <Payments>
                <PaymentType>
                    <Merchant>
                        <MerchantID>999999999999</MerchantID>
                        <MerchantKey>AAAAAAAAAAA</MerchantKey>
                    </Merchant>
                    <TransactionBase>
                        <TransactionID>5ea9747c-12a4-46af-970f-f8a92f6d4f65</TransactionID>
                        <TransactionType>12</TransactionType>
                        <Reference1>INV# 886478943</Reference1>
                        <Amount>1.00</Amount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>Jane</FirstName>
                            <MI />
                            <LastName>Doe</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>67890 Road</AddressLine1>
                            <AddressLine2 />
                            <City>South Padre Island</City>
                            <State>Texas</State>
                            <ZipCode>78597</ZipCode>
                            <Country>USA</Country>
                            <EmailAddress>jane.doe@sagepayments.com</EmailAddress>
                            <Telephone />
                            <Fax />
                        </Address>
                    </Customer>
                </PaymentType>
            </Payments>
            <UI>
                <UIStyle>
                    <Wizard>
                        <BackgroundColor>FFFFFF</BackgroundColor>
                        <BorderStyle>
                            <BorderBottom>0</BorderBottom>
                            <BorderColor>01a3d6</BorderColor>
                            <BorderLeft>0</BorderLeft>
                            <BorderRight>0</BorderRight>
                            <BorderTop>0</BorderTop>
                        </BorderStyle>
                        <FieldStyle>
                            <Color>000000</Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </FieldStyle>
                        <LabelStyle>
                            <Color></Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </LabelStyle>
                    </Wizard>
                    <WizardStepLeft>
                        <BackgroundColor>FFFFFF</BackgroundColor>
                        <BorderStyle>
                            <BorderBottom>1</BorderBottom>
                            <BorderColor>cfeef8</BorderColor>
                            <BorderLeft>1</BorderLeft>
                            <BorderRight>1</BorderRight>
                            <BorderTop>1</BorderTop>
                        </BorderStyle>
                        <FieldStyle>
                            <Color>000000</Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </FieldStyle>
                        <LabelStyle>
                            <Color></Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </LabelStyle>
                    </WizardStepLeft>
                    <WizardStepRight>
                        <BackgroundColor>cfeef8</BackgroundColor>
                        <BorderStyle>
                            <BorderBottom>2</BorderBottom>
                            <BorderColor>cfeef8</BorderColor>
                            <BorderLeft>2</BorderLeft>
                            <BorderRight>2</BorderRight>
                            <BorderTop>2</BorderTop>
                        </BorderStyle>
                        <FieldStyle>
                            <Color>000000</Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </FieldStyle>
                        <LabelStyle>
                            <Color></Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </LabelStyle>
                    </WizardStepRight>
                    <WizardSupport>
                        <Visible>false</Visible>
                        <BackgroundColor>ffffff</BackgroundColor>
                        <BorderStyle>
                            <BorderBottom>3</BorderBottom>
                            <BorderColor>ffffff</BorderColor>
                            <BorderLeft>3</BorderLeft>
                            <BorderRight>3</BorderRight>
                            <BorderTop>1000</BorderTop>
                        </BorderStyle>
                        <FieldStyle>
                            <Color>ffffff</Color >
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </FieldStyle>
                        <LabelStyle>
                            <Color></Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </LabelStyle>
                    </WizardSupport>
                    <WizardTitle>
                        <BackgroundColor>FFFFFF</BackgroundColor>
                        <BorderStyle>
                            <BorderBottom>2</BorderBottom>
                            <BorderColor>01a3d6</BorderColor>
                            <BorderLeft>2</BorderLeft>
                            <BorderRight>2</BorderRight>
                            <BorderTop>2</BorderTop>
                        </BorderStyle>
                        <FieldStyle>
                            <Color>000000</Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </FieldStyle>
                        <LabelStyle>
                            <Color></Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </LabelStyle>
                    </WizardTitle>
                    <Buttons>
                        <BackgroundColor>01a3d6</BackgroundColor>
                        <BorderStyle>
                            <BorderBottom>1</BorderBottom>
                            <BorderColor>01a3d6</BorderColor>
                            <BorderLeft>1</BorderLeft>
                            <BorderRight>1</BorderRight>
                            <BorderTop>1</BorderTop>
                        </BorderStyle>
                        <FieldStyle>
                            <Color>000000</Color>
                            <Family>Verdana</Family>
                            <Size>12</Size>
                        </FieldStyle>
                        <LabelStyle>
                            <Color>000000</Color>
                            <Family>Verdana</Family>
                            <Size>12</Size>
                        </LabelStyle>
                    </Buttons>
                </UIStyle>
                <SinglePayment>
                    <TransactionBase>
                        <Reference1>
                            <Enabled>false</Enabled>
                            <Visible>false</Visible>
                        </Reference1>
                        <SubtotalAmount>
                            <Enabled>false</Enabled>
                            <Visible>true</Visible>
                        </SubtotalAmount>
                        <TaxAmount>
                            <Enabled>true</Enabled>
                            <Visible>true</Visible>
                        </TaxAmount>
                        <ShippingAmount>
                            <Enabled>false</Enabled>
                            <Visible>false</Visible>
                        </ShippingAmount>
                    </TransactionBase>
                    <Customer>
                        <Name>
                            <FirstName>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </FirstName>
                            <LastName>
                                <Enabled>false</Enabled>
                                <Visible>false</Visible>
                            </LastName>
                        </Name>
                        <Address>
                            <AddressLine1>
                                <Enabled>false</Enabled>
                                <Visible>false</Visible>
                            </AddressLine1>
                            <City>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </City>
                            <State>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </State>
                            <ZipCode>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </ZipCode>
                            <Country>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </Country>
                            <EmailAddress>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </EmailAddress>
                            <Telephone>
                                <Enabled>false</Enabled>
                                <Visible>true</Visible>
                            </Telephone>
                        </Address>
                    </Customer>
                </SinglePayment>
            </UI>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Request_v1 xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <Application>
                <ApplicationID>DEMO</ApplicationID>
                <LanguageID>EN</LanguageID>
            </Application>
            <VaultOperation>
                <Merchant>
                    <MerchantID>999999999999</MerchantID>
                    <MerchantKey>AAAAAAAAAAA</MerchantKey>
                </Merchant>
                <VaultStorage>
                    <Service>UPDATE</Service>
                    <GUID>sfdas-ee3u38d-dagdi3-efad83</GUID>
                </VaultStorage>
                <VaultID>2341234-12431243-2341235</VaultID>
            </VaultOperation>
            <UI>
                <UIStyle>
                    <Wizard>
                        <BackgroundColor>FFFFFF</BackgroundColor>
                        <BorderStyle>
                            <BorderBottom>0</BorderBottom>
                            <BorderColor>01a3d6</BorderColor>
                            <BorderLeft>0</BorderLeft>
                            <BorderRight>0</BorderRight>
                            <BorderTop>0</BorderTop>
                        </BorderStyle>
                        <FieldStyle>
                            <Color>000000</Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </FieldStyle>
                        <LabelStyle>
                            <Color></Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </LabelStyle>
                    </Wizard>
                    <WizardStepLeft>
                        <BackgroundColor>FFFFFF</BackgroundColor>
                        <BorderStyle>
                            <BorderBottom>1</BorderBottom>
                            <BorderColor>cfeef8</BorderColor>
                            <BorderLeft>1</BorderLeft>
                            <BorderRight>1</BorderRight>
                            <BorderTop>1</BorderTop>
                        </BorderStyle>
                        <FieldStyle>
                            <Color>000000</Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </FieldStyle>
                        <LabelStyle>
                            <Color></Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </LabelStyle>
                    </WizardStepLeft>
                    <WizardStepRight>
                        <BackgroundColor>cfeef8</BackgroundColor>
                        <BorderStyle>
                            <BorderBottom>2</BorderBottom>
                            <BorderColor>cfeef8</BorderColor>
                            <BorderLeft>2</BorderLeft>
                            <BorderRight>2</BorderRight>
                            <BorderTop>2</BorderTop>
                        </BorderStyle>
                        <FieldStyle>
                            <Color>000000</Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </FieldStyle>
                        <LabelStyle>
                            <Color></Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </LabelStyle>
                    </WizardStepRight>
                    <WizardSupport>
                        <Visible>false</Visible>
                        <BackgroundColor>ffffff</BackgroundColor>
                        <BorderStyle>
                            <BorderBottom>3</BorderBottom>
                            <BorderColor>ffffff</BorderColor>
                            <BorderLeft>3</BorderLeft>
                            <BorderRight>3</BorderRight>
                            <BorderTop>1000</BorderTop>
                        </BorderStyle>
                        <FieldStyle>
                            <Color>ffffff</Color >
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </FieldStyle>
                        <LabelStyle>
                            <Color></Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </LabelStyle>
                    </WizardSupport>
                    <WizardTitle>
                        <BackgroundColor>FFFFFF</BackgroundColor>
                        <BorderStyle>
                            <BorderBottom>2</BorderBottom>
                            <BorderColor>01a3d6</BorderColor>
                            <BorderLeft>2</BorderLeft>
                            <BorderRight>2</BorderRight>
                            <BorderTop>2</BorderTop>
                        </BorderStyle>
                        <FieldStyle>
                            <Color>000000</Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </FieldStyle>
                        <LabelStyle>
                            <Color></Color>
                            <Family>Verdana</Family>
                            <Size>11</Size>
                        </LabelStyle>
                    </WizardTitle>
                    <Buttons>
                        <BackgroundColor>01a3d6</BackgroundColor>
                        <BorderStyle>
                            <BorderBottom>1</BorderBottom>
                            <BorderColor>01a3d6</BorderColor>
                            <BorderLeft>1</BorderLeft>
                            <BorderRight>1</BorderRight>
                            <BorderTop>1</BorderTop>
                        </BorderStyle>
                        <FieldStyle>
                            <Color>000000</Color>
                            <Family>Verdana</Family>
                            <Size>12</Size>
                        </FieldStyle>
                        <LabelStyle>
                            <Color>000000</Color>
                            <Family>Verdana</Family>
                            <Size>12</Size>
                        </LabelStyle>
                    </Buttons>
                </UIStyle>
                <VaultOperation>
                    <AccountNumber>
                        <Enabled>false</Enabled>
                        <Visible>false</Visible>
                    </AccountNumber>
                </VaultOperation>
            </UI>
        </Request_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        req = sevd.Request()
        req.from_xml(ET.XML(content.encode('utf-8')))
        req.to_xml()

    # TODO: test responses (not sure how at this point)
    def test_vault_status_response_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Response_v1>
            <VaultStatusQueryResponse>
                <Response>
                    <ResponseIndicator>A</ResponseIndicator>
                    <ResponseMessage>SUCCESS</ResponseMessage>
                </Response>
                <VaultResponse>
                    <Response>
                        <ResponseIndicator>A</ResponseIndicator>
                        <ResponseMessage>SUCCESS</ResponseMessage>
                    </Response>
                    <GUID>74e7b7c14839486484071a91f4367bd6</GUID>
                    <ExpirationDate>0716</ExpirationDate>
                    <Last4>XXXXXXXXXXXX1111</Last4>
                    <PaymentDescription>411111XXXXXX1111</PaymentDescription>
                    <PaymentTypeID>4</PaymentTypeID>
                </VaultResponse>
            </VaultStatusQueryResponse>
        </Response_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        response = sevd.Response()
        response.from_xml(ET.XML(content.encode('utf-8')))
        response.to_xml()

    def test_authorization_response_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Response_v1>
            <PaymentResponses>
                <PaymentResponseType>
                    <Response>
                        <ResponseIndicator>A</ResponseIndicator>
                        <ResponseCode>000001</ResponseCode>
                        <ResponseMessage>APPROVED 000001</ResponseMessage>
                    </Response>
                    <TransactionResponse>
                        <AuthCode>000001</AuthCode>
                        <CVVResult>M</CVVResult>
                        <VANReference>F7KFBmgfX0</VANReference>
                        <TransactionID>8aa39248-0c47-4a57-bcae-9b90048107e0</TransactionID>
                        <Last4>XXXXXXXXXXXX1111</Last4>
                        <PaymentDescription>411111XXXXXX1111</PaymentDescription>
                        <Amount>1</Amount>
                        <PaymentTypeID>4</PaymentTypeID>
                        <TransactionDate>7/20/2015 11:47:41 AM</TransactionDate>
                        <EntryMode>K</EntryMode>
                        <TaxAmount>0</TaxAmount>
                        <ShippingAmount>0</ShippingAmount>
                    </TransactionResponse>
                    <Customer>
                        <Name>
                            <FirstName>David</FirstName>
                            <MI>I</MI>
                            <LastName>Dorothy</LastName>
                        </Name>
                        <Address>
                            <AddressLine1>502 W. Pippen Street</AddressLine1>
                            <AddressLine2>PO BOX 700</AddressLine2>
                            <City>Whitakers</City>
                            <State>NC</State>
                            <ZipCode>27891</ZipCode>
                        </Address>
                        <Company />
                    </Customer>
                </PaymentResponseType>
            </PaymentResponses>
        </Response_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        response = sevd.Response()
        response.from_xml(ET.XML(content.encode('utf-8')))
        response.to_xml()

    def test_authorization_void_response_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Response_v1>
            <PaymentResponses>
                <PaymentResponseType>
                    <Response>
                        <ResponseIndicator>A</ResponseIndicator>
                        <ResponseMessage>APPROVED</ResponseMessage>
                    </Response>
                    <TransactionResponse>
                        <CVVResult>P</CVVResult>
                        <VANReference>F7KFBmgfX0</VANReference>
                        <TransactionID>00bf05dd-4406-47d1-a033-66eabd08be1a</TransactionID>
                        <Last4>XXXXXXXXXXXX1111</Last4>
                        <PaymentDescription>411111XXXXXX1111</PaymentDescription>
                        <Amount>0</Amount>
                        <PaymentTypeID>4</PaymentTypeID>
                        <Reference1>ID7KFBmgfZ</Reference1>
                        <TransactionDate>7/20/2015 11:47:42 AM</TransactionDate>
                        <EntryMode>K</EntryMode>
                        <TaxAmount>0</TaxAmount>
                        <ShippingAmount>0</ShippingAmount>
                    </TransactionResponse>
                    <Customer>
                        <Name>
                            <FirstName>David Dorothy</FirstName>
                        </Name>
                        <Address>
                            <AddressLine1>502 W. Pippen Street</AddressLine1>
                            <City>Whitakers</City>
                            <State>NC</State>
                            <ZipCode>27891</ZipCode>
                        </Address>
                        <Company />
                    </Customer>
                </PaymentResponseType>
            </PaymentResponses>
        </Response_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        response = sevd.Response()
        response.from_xml(ET.XML(content.encode('utf-8')))
        response.to_xml()

    def test_vault_delete_response_parse(self):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <Response_v1>
            <VaultResponse>
                <Response>
                    <ResponseIndicator>A</ResponseIndicator>
                    <ResponseMessage>SUCCESS</ResponseMessage>
                </Response>
                <GUID>74e7b7c14839486484071a91f4367bd6</GUID>
            </VaultResponse>
        </Response_v1>
        '''
        validate_xml_with_xsd(content.encode('utf-8'))
        response = sevd.Response()
        response.from_xml(ET.XML(content.encode('utf-8')))
        response.to_xml()

    #def test_sale_response_parse(self):
    #    content = '''
    #    '''


if __name__ == '__main__':
    import unittest
    unittest.main()
