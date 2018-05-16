'''Sage Exchange Virtual Desktop integration.'''
import re
import uuid
import warnings
import xml.etree.ElementTree as ET

try:
    from django.conf import settings
except ImportError:
    settings = object()
import requests

DEBUG = True
SAGE_SEVD_ENCRYPT_URL = 'https://www.sageexchange.com/sevd/frmenvelope.aspx'
SAGE_SEVD_DECRYPT_URL = 'https://www.sageexchange.com/sevd/frmopenenvelope.aspx'
SAGE_SEVD_PAYMENT_URL = 'https://www.sageexchange.com/sevd/frmpayment.aspx'

COLOR_REGEX = re.compile('^([0-9A-F][0-9A-F][0-9A-F])?([0-9A-F][0-9A-F][0-9A-F])?$', re.IGNORECASE)
HEX_COLOR_REGEX = re.compile('^#[0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F][0-9A-F]$', re.IGNORECASE)

def escape(str_data):
    '''Converts to escaped HTML.'''
    return str_data.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')

def format_uuid(a_uuid):
    '''Formats a uuid into a GUID format that windows prefers.'''
    return ('%s-%s-%s-%s-%s' % (a_uuid[0:8], a_uuid[8:12], a_uuid[12:16], a_uuid[16:20], a_uuid[20:])).strip()

def get_uuid(query_first='vault', app_id=None, merchant_id=None, merchant_key=None):
    '''Return a UUID.

    `query_first` should either be 'vault' or 'payment' depending on how the UUID will be used. NOTE: this may need to change.

    NOTE: UUIDs must be unique. If the UUIDs are not unique the results from
    the last time the UUID was used will be returned. UUIDs are removed from
    Sage Exchange Virtual Desktop after 6 months
    (https://support.sagepayments.com/link/portal/20000/20000/Article/3194/How-long-does-the-TransactionID-stay-in-the-gateway).
    '''
    if query_first:
        if app_id is None:
            app_id = settings.SEVD_APPLICATION_ID
        if merchant_id is None:
            merchant_id = settings.SEVD_MERCHANT_ID
        if merchant_key is None:
            settings.SEVD_MERCHANT_KEY

        u = format_uuid(uuid.uuid4().hex)
        duplicate = True
        while duplicate:
            if query_first == 'vault':
                result = execute_vault_status_query(app_id, merchant_id, merchant_key, u)
                if result.vault_query_response.response.response_code == '411411':
                    duplicate = False
            else:
                result = execute_transaction_status_query(app_id, merchant_id, merchant_key, u)
                if result.transaction_query_responses.transaction_status_query_responses.response.response_code == '411411':
                    duplicate = False
            if duplicate:
                u = format_uuid(uuid.uuid4().hex)

        return u
    else:
        return format_uuid(uuid.uuid4().hex)

##############################################################################
# Property Functions to allow validation of data for XML                     #
##############################################################################

def get_func(name):
    '''Returns a function that returns the value of the property.

    This is the default getter. Probably will be the only one needed.
    '''
    def getter(obj):
        return getattr(obj, name)
    return getter

def string_set_func(name):
    '''Validates every value is either a string or can be converted to a string.'''
    def setter(obj, value):
        if not isinstance(value, str) and value is not None:
            try:
                str(value)
            except:
                raise ValueError('%s: Unable to convert value of type %s to a str.' % (name, type(value).__name__))
        setattr(obj, name, value)
    return setter

def int_set_func(name):
    '''Validates every value is either an integer or can be converted to an integer.'''
    def setter(obj, value):
        if not isinstance(value, int) and value is not None:
            try:
                int(value)
            except:
                raise ValueError('%s: Unable to convert value of type %s to an int.' % (name, type(value).__name__))
            if re.match(r'^-?\d+$', str(value)) == None:
                raise ValueError('%s: Value "%s" does not meet requirements for an int.' % (name, str(value)))
        setattr(obj, name, value)
    return setter

def double_set_func(name):
    '''Validates every value is either a double or can be converted to a double.

    NOTE: this might be better to validate using a regex because of casing specifications in xs:double.
    '''
    def setter(obj, value):
        if not isinstance(value, float) and value is not None:
            try:
                float(value)
            except:
                raise ValueError('%s: Unable to convert value of type %s to a double (python float).' % (name, type(value).__name__))
        setattr(obj, name, value)
    return setter

def boolean_set_func(name):
    '''Validates every value to be either a valid bool or "true" or "false".'''
    def setter(obj, value):
        if not isinstance(value, bool) and str(value).strip() != 'true' and str(value).strip() != 'false' and value is not None:
            raise ValueError('%s: Not a valid boolean value.')
        setattr(obj, name, value)
    return setter

def class_set_func(name, cls):
    '''Validates that every value is an instance of the specified cls (class).

    NOTE: this is a special case and accepts two parameters. All other SEVDChild.valid_values functions must only accept a single parameter: name.
    '''
    def setter(obj, value):
        if not isinstance(value, cls) and value is not None:
            raise ValueError('%s: Value must be an instance of %s.' % (name, cls.__name__))
        setattr(obj, name, value)
    return setter

def multiple_class_set_func(name, cls):
    '''Validates that every value is an instance or a list of instances of the specified class.

    NOTE: this is a special case and accepts two parameters.
    '''
    def setter(obj, value):
        if isinstance(value, (list, tuple)):
            for val in value:
                if not isinstance(val, cls):
                    raise ValueError('%s: %s is not an instance of %s' % (name, type(val).__name__, cls.__name__))
        elif not isinstance(value, cls) and value is not None:
            raise ValueError('%s: Value must be an instance of %s.' % (name, cls.__name__))
        setattr(obj, name, value)
    return setter

def regex_set_func(regex):
    if not isinstance(regex, re._pattern_type):
        regex = re.compile(regex)
    def set_func(name):
        def setter(obj, value):
            if regex.match(str(value).strip()) == None and value is not None:
                raise ValueError('%s: Value must match pattern %s.' % (name, regex.pattern))
            setattr(obj, name, value)
        return setter
    return set_func

def required_regex_set_func(regex):
    '''This is a special case where the field should be required but an empty string '' is allowed as the value.'''
    if not isinstance(regex, re._pattern_type):
        regex = re.compile(regex)
    def set_func(name):
        def setter(obj, value):
            if value is None:
                value = ''
            if regex.match(str(value).strip()) == None:
                raise ValueError('%s: Value must match pattern %s.' % (name, regex.pattern))
            setattr(obj, name, value)
        return setter
    return set_func

class SEVDChild(object):
    '''Represents a child element of the class.'''
    tag_name = ''
    member_name = ''
    sevd_class = None
    required = False
    multiple = False
    valid_values = None

    def __init__(self, tag_name, member_name, sevd_class=None, required=False, multiple=False, valid_values=None):
        self.tag_name = tag_name
        self.member_name = member_name
        self.sevd_class = sevd_class
        self.required = required
        self.multiple = multiple
        self.valid_values = valid_values


class BaseSEVDObjectMeta(type):
    '''Allows us to create descriptors on the class so we can do extra fancy validation.'''
    def __new__(cls, name, parents, dct):
        for child in dct['xml_children']:
            # In order to ensure that we are properly following the XSD we
            # need to validate that every property that is set matches
            # either the expected class or a valid value. To do this we use
            # properties and set up a hidden member to store the actual value.
            # All of these properties should be allowed to be set to None
            # meaning that no value is currently specified. If the element is
            # required then it will be caught at a later point in the process.
            # Specifying a specific validation setter is as simple as passing
            # a function in the SEVDChild.valid_values member. If no function
            # is specified then we assume it should validate as a string
            # unless SEVDChild.sevd_class is specified in which case we assume
            # that all values should be an instance of the specified class.
            # If both SEVDChild.sevd_class and SEVDChild.valid_values are set
            # the SEVDChild.valid_values will be ignored. All setter functions
            # should raise a ValueError if there is a problem with the value.

            private_member_name = '_xml_%s' % child.member_name

            if child.multiple == True:
                # TODO: handle this special case where we expect a list of items instead of a normal value...
                if child.sevd_class:
                    dct[child.member_name] = property(get_func(private_member_name), multiple_class_set_func(private_member_name, child.sevd_class))
                else:
                    raise NotImplementedError("Oops I didn't want to make this. %s %s" % (child.member_name, child.tag_name))
                    #dct[child.member_name] = property(get_func(private_member_name), multiple_set_func(private_member_name))

            elif child.sevd_class != None:
                # set up the property to validate the correct instance.
                dct[child.member_name] = property(get_func(private_member_name), class_set_func(private_member_name, child.sevd_class))

            elif child.valid_values is not None:
                # set up the property to validate using the specified function.
                dct[child.member_name] = property(get_func(private_member_name), child.valid_values(private_member_name))

            else:
                # by default set up the property to validate as a string
                dct[child.member_name] = property(get_func(private_member_name), string_set_func(private_member_name))

            # always set private member variable value to None at creation.
            dct[private_member_name] = None

        return super(BaseSEVDObjectMeta, cls).__new__(cls, name, parents, dct)


class BaseSEVDObject(object, metaclass=BaseSEVDObjectMeta):

    # the element to render this object as
    xml_element = ''
    # the sub-elements to render for this class
    xml_children = []

    def __init__(self, **kwargs):
        for child in self.xml_children:
            # set the inital value
            setattr(self, child.member_name, kwargs.get(child.member_name, None))

    def to_xml(self, tag_name=None):
        '''Converts the instance to an XML element using ElementTree.'''
        elem = ET.Element(tag_name or self.xml_element)
        for child in self.xml_children:

            if isinstance(getattr(self, child.member_name), BaseSEVDObject):
                if getattr(self, child.member_name) is not None:
                    sub_elem = getattr(self, child.member_name).to_xml(child.tag_name)
                    elem.append(sub_elem)
            elif isinstance(getattr(self, child.member_name), (list, tuple)):
                if child.sevd_class is not None:
                    for item in getattr(self, child.member_name):
                        # if this raises and exception then there was an error with an item in the list.
                        sub_elem = item.to_xml(child.tag_name)
                        elem.append(sub_elem)
                else:
                    #TODO: add logic here. Expect that it is a list of values
                    raise NotImplementedError()
            else:
                if getattr(self, child.member_name) is not None:
                    sub_elem = ET.SubElement(elem, child.tag_name)
                    if isinstance(getattr(self, child.member_name), bool):
                        sub_elem.text = 'true' if getattr(self, child.member_name) else 'false'
                    else:
                        sub_elem.text = getattr(self, child.member_name)
                elif child.required:
                    raise Exception('Missing value: %s' % child.tag_name)

        return elem

    def from_xml(self, elem):
        '''Converts from an XML Element to an instance of this object.'''
        if elem.tag != self.xml_element:
            warnings.warn("Element received <%s> does not match expected tag name %s." % (elem.tag, self.xml_element))

        # keep track of every element we successfully parse so we can throw warnings about those we have not.
        parsed_elements = []

        for child in self.xml_children:
            if child.sevd_class is not None:
                els = elem.findall(child.tag_name)
                if len(els) == 1 and (len(child.sevd_class.xml_children) == 0 or len(els[0]) > 0):
                    obj = child.sevd_class()
                    obj.xml_element = child.tag_name
                    setattr(self, child.member_name, obj)
                    obj.from_xml(els[0])
                    parsed_elements.append(els[0])
                elif len(els) > 1:
                    objs = []
                    for el in els:
                        if len(child.sevd_class.xml_children) == 0 or len(el) > 0:
                            obj = child.sevd_class()
                            obj.xml_element = child.tag_name
                            obj.from_xml(el)
                            objs.append(obj)
                            parsed_elements.append(el)
                    setattr(self, child.member_name, objs)
                elif len(els) == 1:
                    # if we get here we have an empty element <tag /> meaning that we ignore it but we want to track that we have seen it.
                    parsed_elements.append(els[0])
            else:
                els = elem.findall(child.tag_name)
                if len(els) == 1:
                    setattr(self, child.member_name, els[0].text)
                    parsed_elements.append(els[0])
                elif len(els) > 1:
                    vals = []
                    for el in els:
                        vals.append(el.text)
                        parsed_elements.append(el)
                    setattr(self, child.member_name, objs)

        # check for unparsed elements (generally means we are missing features)
        for el in elem:
            if el not in parsed_elements:
                warnings.warn('Tag "%s" was not parsed. Child of "%s" tag. Additional children were also unparsed.' % (el.tag, elem.tag))


class ApplicationType(BaseSEVDObject):
    '''

    <xs:complexType name="ApplicationType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="ApplicationID" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="LanguageID" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Application'
    xml_children = [
        SEVDChild('ApplicationID', 'app_id', required=True),
        SEVDChild('LanguageID', 'lang_id'),
    ]

    def __init__(self, **kwargs):
        super(ApplicationType, self).__init__(**kwargs)
        if self.app_id is None and hasattr(settings, 'SEVD_APPLICATION_ID'):
            self.app_id = settings.SEVD_APPLICATION_ID
        if self.lang_id is None:
            self.lang_id = 'EN'


class MerchantType(BaseSEVDObject):
    '''

    <xs:complexType name="MerchantType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="MerchantID" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="MerchantKey" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Merchant'
    xml_children = [
        SEVDChild('MerchantID', 'merchant_id', required=True),
        SEVDChild('MerchantKey', 'merchant_key', required=True),
    ]

    def __init__(self, **kwargs):
        super(MerchantType, self).__init__(**kwargs)
        if self.merchant_id is None and hasattr(settings, 'SEVD_MERCHANT_ID'):
            self.merchant_id = settings.SEVD_MERCHANT_ID
        if self.merchant_key is None and hasattr(settings, 'SEVD_MERCHANT_KEY'):
            self.merchant_key = settings.SEVD_MERCHANT_KEY


class AddressType(BaseSEVDObject):
    '''

    <xs:complexType name="AddressType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="AddressLine1" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="AddressLine2" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="City" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="State" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="ZipCode" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Country" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="EmailAddress" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Telephone" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Fax" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Address'
    xml_children = [
        SEVDChild('AddressLine1', 'street1'),
        SEVDChild('AddressLine2', 'street2'),
        SEVDChild('City', 'city'),
        SEVDChild('State', 'state'),
        SEVDChild('ZipCode', 'zip_code'),
        SEVDChild('Country', 'country'),
        SEVDChild('EmailAddress', 'email'),
        SEVDChild('Telephone', 'phone'),
        SEVDChild('Fax', 'fax'),
    ]


class NameType(BaseSEVDObject):
    '''

    <xs:complexType name="NameType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="FirstName" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="MI" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="LastName" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Name'
    xml_children = [
        SEVDChild('FirstName', 'first_name'),
        SEVDChild('MI', 'middle_initial'),
        SEVDChild('LastName', 'last_name'),
    ]


class CompanyType(BaseSEVDObject):
    '''

    <xs:complexType name="CompanyType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Name" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Address" type="AddressType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Company'
    xml_children = [
        SEVDChild('Name', 'name'),
        SEVDChild('Address', 'address', AddressType),
    ]


class PersonType(BaseSEVDObject):
    '''

    <xs:complexType name="PersonType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Name" type="NameType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Address" type="AddressType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Company" type="CompanyType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Person'
    xml_children = [
        SEVDChild('Name', 'name', NameType),
        SEVDChild('Address', 'address', AddressType),
        SEVDChild('Company', 'company', CompanyType),
    ]


class PersonsType(BaseSEVDObject):
    '''

    <xs:complexType name="ArrayOfPersonType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="unbounded" name="PersonType" nillable="true" type="PersonType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Persons'
    xml_children = [
        SEVDChild('PersonType', 'persons', PersonType, multiple=True),
    ]


class Level2Type(BaseSEVDObject):
    '''

    <xs:complexType name="Level2Type">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="CustomerNumber" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="TaxAmount" type="xs:double"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Level2'
    xml_children = [
        SEVDChild('CustomerNumber', 'customer_number', required=True),
        SEVDChild('TaxAmount', 'tax_amount', required=True, valid_values=double_set_func),
    ]


class Level3LineItemType(BaseSEVDObject):
    '''

    <xs:complexType name="Level3LineItemType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="CommodityCode" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Description" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="ProductCode" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Quantity" type="xs:int"/>
            <xs:element minOccurs="0" maxOccurs="1" name="UnitOfMeasure" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="UnitCost" type="xs:double"/>
            <xs:element minOccurs="1" maxOccurs="1" name="TaxAmount" type="xs:double"/>
            <xs:element minOccurs="1" maxOccurs="1" name="TaxRate" type="xs:double"/>
            <xs:element minOccurs="1" maxOccurs="1" name="DiscountAmount" type="xs:double"/>
            <xs:element minOccurs="0" maxOccurs="1" name="AlternateTaxIdentifier" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TaxTypeApplied" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="DiscountIndicator" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="NetGrossIndicator" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="ExtendedItemAmount" type="xs:double"/>
            <xs:element minOccurs="0" maxOccurs="1" name="DebitCreditIndicator" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Level3LineItem'
    xml_children = [
        SEVDChild('CommodityCode', 'commodity_code', required=True),
        SEVDChild('Description', 'description', required=True),
        SEVDChild('ProductCode', 'product_code', required=True),
        SEVDChild('Quantity', 'quantity', required=True, valid_values=int_set_func),
        SEVDChild('UnitOfMeasure', 'unit_of_measure', required=True),
        SEVDChild('UnitCost', 'unit_cost', required=True, valid_values=double_set_func),
        SEVDChild('TaxAmount', 'tax_amount', required=True, valid_values=double_set_func),
        SEVDChild('TaxRate', 'tax_rate', required=True, valid_values=double_set_func),
        SEVDChild('DiscountAmount', 'discount_amount', required=True, valid_values=double_set_func),
        SEVDChild('AlternateTaxIdentifier', 'alternate_tax_identifier', required=True),
        SEVDChild('TaxTypeApplied', 'tax_type_applied', required=True),
        SEVDChild('DiscountIndicator', 'discount_indicator', required=True),
        SEVDChild('NetGrossIndicator', 'net_gross_indicator', required=True),
        SEVDChild('ExtendedItemAmount', 'extended_item_amount', required=True, valid_values=double_set_func),
        SEVDChild('DebitCreditIndicator', 'debit_credit_indicator', required=True),
    ]

class Level3LineItems(BaseSEVDObject):
    '''

    <xs:complexType name="ArrayOfLevel3LineItemType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="unbounded" name="Level3LineItemType" nillable="true" type="Level3LineItemType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'LineItems'
    xml_children = [
        SEVDChild('Level3LineItemType', 'level3_line_item', Level3LineItemType, required=True, multiple=True),
    ]


class Level3Type(BaseSEVDObject):
    '''

    <xs:complexType name="Level3Type">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Level2" type="Level2Type"/>
            <xs:element minOccurs="1" maxOccurs="1" name="ShippingAmount" type="xs:double"/>
            <xs:element minOccurs="0" maxOccurs="1" name="DestinationZipCode" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="DestinationCountryCode" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VATNumber" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="DiscountAmount" type="xs:double"/>
            <xs:element minOccurs="1" maxOccurs="1" name="DutyAmount" type="xs:double"/>
            <xs:element minOccurs="1" maxOccurs="1" name="NationalTaxAmount" type="xs:double"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VATInvoiceNumber" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="VATTaxAmount" type="xs:double"/>
            <xs:element minOccurs="1" maxOccurs="1" name="VATTaxRate" type="xs:double"/>
            <xs:element minOccurs="0" maxOccurs="1" name="LineItems" type="ArrayOfLevel3LineItemType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Level3'
    xml_children = [
        SEVDChild('Level2', 'level2', Level2Type, required=True),
        SEVDChild('ShippingAmount', 'shipping_amount', required=True, valid_values=double_set_func),
        SEVDChild('DestinationZipCode', 'destination_zip_code', required=True),
        SEVDChild('DestinationCountryCode', 'destination_country', required=True),
        SEVDChild('VATNumber', 'vat_number', required=True),
        SEVDChild('DiscountAmount', 'discount_amount', required=True, valid_values=double_set_func),
        SEVDChild('DutyAmount', 'duty_amount', required=True, valid_values=double_set_func),
        SEVDChild('NationalTaxAmount', 'national_tax_amount', required=True, valid_values=double_set_func),
        SEVDChild('VATInvoiceNumber', 'vat_invoice_number', required=True),
        SEVDChild('VATTaxAmount', 'vat_tax_amount', required=True, valid_values=double_set_func),
        SEVDChild('VATTaxRate', 'vat_tax_rate', required=True, valid_values=double_set_func),
        SEVDChild('LineItems', 'line_items', Level3LineItems, required=False),
    ]


def transaction_type_set_func(name):
    def setter(obj, value):
        if str(value).strip() not in TransactionBaseType.TRANSACTION_TYPES and value is not None:
            raise ValueError('%s: "%s" is not a valid Transaction Type. Please refer to the documentation for a list.')
        setattr(obj, name, value)
    return setter


class TransactionBaseType(BaseSEVDObject):
    '''

    <xs:complexType name="TransactionBaseType">
        <xs:sequence>
            <xs:element minOccurs="1" maxOccurs="1" name="TransactionID" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="TransactionType" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Reference1" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Reference2" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Amount" type="xs:double"/>
            <xs:element minOccurs="0" maxOccurs="1" name="AuthCode" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VANReference" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    TRANSACTION_TYPES = [
        '01', # Sale, no UI
        '02', # Authorization, no UI
        '03', # Capture, no UI
        '04', # Void, no UI
        '05', # Force, no UI
        '06', # Credit, no UI
        '07', # Credit without Reference, no UI

        '11', # Sale, with UI
        '12', # Authorization, with UI
        '13', # Capture, with UI
        '15', # Force, with UI
        '16', # Credit, with UI
        '17', # Credit without Reference, with UI
    ]
    xml_element = 'TransactionBase'
    xml_children = [
        SEVDChild('TransactionID', 'trans_id', required=True),
        SEVDChild('TransactionType', 'trans_type', required=True, valid_values=transaction_type_set_func),
        SEVDChild('Reference1', 'ref1'),
        SEVDChild('Reference2', 'ref2'),
        SEVDChild('Amount', 'amount', valid_values=double_set_func),
        SEVDChild('AuthCode', 'auth_code'),
        SEVDChild('VANReference', 'van_reference'),
    ]


class TransactionStatusQueryType(BaseSEVDObject):
    '''

    <xs:complexType name="TransactionStatusQueryType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Merchant" type="MerchantType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionID" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'TransactionStatusQuery'
    xml_children = [
        SEVDChild('Merchant', 'merchant', MerchantType, required=True),
        SEVDChild('TransactionID', 'trans_id', required=True),
    ]


class TransactionStatusQueriesType(BaseSEVDObject):
    '''

    <xs:complexType name="ArrayOfTransactionStatusQueryType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="unbounded" name="TransactionStatusQueryType" nillable="true" type="TransactionStatusQueryType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'TransactionStatusQueries'
    xml_children = [
        SEVDChild('TransactionStatusQueryType', 'transaction_status_queries', TransactionStatusQueryType, multiple=True)
    ]


def schedule_set_func(name):
    def setter(obj, value):
        if str(value).strip() not in RecurringType.SCHEDULE_OPTIONS and value is not None:
            raise ValueError('%s: "%s" is not a valid Schedule. Please refer to the documentation for a list.')
        setattr(obj, name, value)
    return setter

def nonbusiness_day_set_func(name):
    def setter(obj, value):
        if str(value).strip() not in RecurringType.NONBUSINESS_DAY_OPTIONS and value is not None:
            raise ValueError('%s: "%s" is not a valid Non Business Day. Please refer to the documentation for a list.')
        setattr(obj, name, value)
    return setter


class RecurringType(BaseSEVDObject):
    '''

    <xs:complexType name="RecurringType">
        <xs:sequence>
            <xs:element minOccurs="1" maxOccurs="1" name="Schedule" type="ScheduleType"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Interval" type="xs:int"/>
            <xs:element minOccurs="1" maxOccurs="1" name="DayOfMonth" type="xs:int"/>
            <xs:element minOccurs="0" maxOccurs="1" name="StartDate" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Amount" type="xs:double"/>
            <xs:element minOccurs="1" maxOccurs="1" name="TimesToProcess" type="xs:int"/>
            <xs:element minOccurs="1" maxOccurs="1" name="NonBusinessDay" type="NonBusinessDayType"/>
        </xs:sequence>
    </xs:complexType>
    <xs:simpleType name="ScheduleType">
        <xs:restriction base="xs:string">
            <xs:enumeration value="MONTHLY"/>
            <xs:enumeration value="DAILY"/>
        </xs:restriction>
    </xs:simpleType>
    <xs:simpleType name="NonBusinessDayType">
        <xs:restriction base="xs:string">
            <xs:enumeration value="THATDAY"/>
            <xs:enumeration value="BEFORE"/>
            <xs:enumeration value="AFTER"/>
        </xs:restriction>
    </xs:simpleType>
    '''
    SCHEDULE_OPTIONS = ['DAILY', 'MONTHLY']
    NONBUSINESS_DAY_OPTIONS = [
        'THATDAY', # transaction is processed that day
        'BEFORE', # transaction is processed the day before
        'AFTER', # transaction is processed on the next business day
    ]
    xml_element = 'Recurring'
    xml_children = [
        SEVDChild('Schedule', 'schedule', required=True, valid_values=schedule_set_func),
        SEVDChild('Interval', 'interval', valid_values=int_set_func),
        SEVDChild('DayOfMonth', 'day_of_month', valid_values=int_set_func),
        SEVDChild('StartDate', 'start_date'),
        SEVDChild('Amount', 'amount', valid_values=double_set_func),
        SEVDChild('TimesToProcess', 'times_to_process', valid_values=int_set_func),
        SEVDChild('NonBusinessDay', 'non_business_day', valid_values=nonbusiness_day_set_func),
    ]


class RecurringStatusQueryType(BaseSEVDObject):
    '''

    <xs:complexType name="RecurringStatusQueryType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Merchant" type="MerchantType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="RecurringID" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="StartDate" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="EndDate" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'RecurringStatusQuery'
    xml_children = [
        SEVDChild('Merchant', 'merchant', MerchantType, required=True),
        SEVDChild('RecurringID', 'recur_id', required=True),
        SEVDChild('StartDate', 'start_date', required=True),
        SEVDChild('EndDate', 'end_date', required=True),
    ]


class RecurringStatusQueriesType(BaseSEVDObject):
    '''

    <xs:complexType name="ArrayOfRecurringStatusQueryType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="unbounded" name="RecurringStatusQueryType" nillable="true" type="RecurringStatusQueryType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'RecurringStatusQueries'
    xml_children = [
        SEVDChild('RecurringStatusQueryType', 'recurring_status_queries', RecurringStatusQueryType, multiple=True)
    ]


def vault_service_set_func(name):
    def setter(obj, value):
        if str(value).strip() not in VaultStorageType.VAULT_SERVICE_OPTIONS and value is not None:
            raise ValueError('%s: "%s" is not a valid Vault Service. Please refer to the documentation for a list.')
        setattr(obj, name, value)
    return setter


class VaultStorageType(BaseSEVDObject):
    '''

    <xs:complexType name="VaultStorageType">
        <!-- In the original XSD this is a sequence. However, documentation shows examples where order does not matter. -->
        <xs:all>
            <xs:element minOccurs="0" maxOccurs="1" name="GUID" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Service" type="VaultServiceType"/>
        </xs:all>
    </xs:complexType>
    <xs:simpleType name="VaultServiceType">
        <xs:restriction base="xs:string">
            <xs:enumeration value="CREATE"/>
            <xs:enumeration value="UPDATE"/>
            <xs:enumeration value="RETRIEVE"/>
            <xs:enumeration value="DELETE"/>
        </xs:restriction>
    </xs:simpleType>
    '''
    VAULT_SERVICE_OPTIONS = ['CREATE', 'UPDATE', 'RETRIEVE', 'DELETE']
    xml_element = 'VaultStorage'
    xml_children = [
        SEVDChild('GUID', 'guid'),
        SEVDChild('Service', 'service', required=True, valid_values=vault_service_set_func),
    ]


class VaultOperationType(BaseSEVDObject):
    '''

    <xs:complexType name="VaultOperationType">
        <!-- In the original XSD this is a sequence. However, documentation shows examples where order does not matter. -->
        <xs:all>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultID" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Merchant" type="MerchantType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultStorage" type="VaultStorageType"/>
        </xs:all>
    </xs:complexType>
    '''
    xml_element = 'VaultOperation'
    xml_children = [
        SEVDChild('VaultID', 'vault_id'),
        SEVDChild('Merchant', 'merchant', MerchantType, required=True),
        SEVDChild('VaultStorage', 'vault_storage', VaultStorageType, required=True),
    ]


class VaultAccountType(BaseSEVDObject):
    '''

    <xs:complexType name="VaultAccountType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Company" type="CompanyType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Contact" type="PersonType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'VaultAccountType'
    xml_children = [
        SEVDChild('Company', 'company', CompanyType, required=True),
        SEVDChild('Contact', 'contact', PersonType, required=True),
    ]


class AccountQueryType(BaseSEVDObject):
    '''

    <xs:complexType name="AccountQueryType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Merchant" type="MerchantType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'AccountQuery'
    xml_children = [
        SEVDChild('Merchant', 'merchant', MerchantType, required=True),
    ]


class VaultStatusQueryType(BaseSEVDObject):
    '''

    <xs:complexType name="VaultStatusQueryType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Merchant" type="MerchantType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultID" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'VaultStatusQuery'
    xml_children = [
        SEVDChild('Merchant', 'merchant', MerchantType),
        SEVDChild('VaultID', 'vault_id'),
    ]


class UIFieldType(BaseSEVDObject):
    '''

    <xs:complexType name="UIFieldType">
        <xs:sequence>
            <xs:element minOccurs="1" maxOccurs="1" name="Enabled" type="xs:boolean"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Visible" type="xs:boolean"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'UIField'
    xml_children = [
        SEVDChild('Enabled', 'enabled', valid_values=boolean_set_func),
        SEVDChild('Visible', 'visible', valid_values=boolean_set_func),
    ]


class UINameType(BaseSEVDObject):
    '''

    <xs:complexType name="UINameType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="FirstName" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="MI" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="LastName" type="UIFieldType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Name'
    xml_children = [
        SEVDChild('FirstName', 'first_name', UIFieldType),
        SEVDChild('MI', 'middle_initial', UIFieldType),
        SEVDChild('LastName', 'last_name', UIFieldType),
    ]


class UIAddressType(BaseSEVDObject):
    '''

    <xs:complexType name="UIAddressType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="AddressLine1" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="AddressLine2" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="City" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="State" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="ZipCode" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Country" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="EmailAddress" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Telephone" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Fax" type="UIFieldType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Address'
    xml_children = [
        SEVDChild('AddressLine1', 'street1', UIFieldType),
        SEVDChild('AddressLine2', 'street2', UIFieldType),
        SEVDChild('City', 'city', UIFieldType),
        SEVDChild('State', 'state', UIFieldType),
        SEVDChild('ZipCode', 'zip_code', UIFieldType),
        SEVDChild('Country', 'country', UIFieldType),
        SEVDChild('EmailAddress', 'email', UIFieldType),
        SEVDChild('Telephone', 'phone', UIFieldType),
        SEVDChild('Fax', 'fax', UIFieldType),
    ]


class UIPersonType(BaseSEVDObject):
    '''

    <xs:complexType name="UIPersonType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Name" type="UINameType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Address" type="UIAddressType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'UIPersonType'
    xml_children = [
        SEVDChild('Name', 'name', UINameType),
        SEVDChild('Address', 'address', UIAddressType),
    ]


class UITransactionBaseType(BaseSEVDObject):
    '''

    <xs:complexType name="UITransactionBaseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Reference1" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="SubtotalAmount" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TaxAmount" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="ShippingAmount" type="UIFieldType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="AuthCode" type="UIFieldType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'UITransactionBaseType'
    xml_children = [
        SEVDChild('Reference1', 'reference1', UIFieldType),
        SEVDChild('SubtotalAmount', 'subtotal_amount', UIFieldType),
        SEVDChild('TaxAmount', 'tax_amount', UIFieldType),
        SEVDChild('ShippingAmount', 'shipping_amount', UIFieldType),
        SEVDChild('AuthCode', 'auth_code', UIFieldType),
    ]


class VaultOperationUIType(BaseSEVDObject):
    '''

    <xs:complexType name="VaultOperationUIType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="AccountNumber" type="UIFieldType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'VaultOperationUIType'
    xml_children = [
        SEVDChild('AccountNumber', 'account_number', UIFieldType)
    ]


class SinglePaymentUIType(BaseSEVDObject):
    '''

    <xs:complexType name="SinglePaymentUIType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionBase" type="UITransactionBaseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Customer" type="UIPersonType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'SinglePaymentUIType'
    xml_children = [
        SEVDChild('TransactionBase', 'transaction_base', UITransactionBaseType),
        SEVDChild('Customer', 'customer', UIPersonType),
    ]


class UIBorderStyleType(BaseSEVDObject):
    '''
    NOTE: Not defined in original XSD. SPS says they do not have XSD for it.
    <xs:complexType name="UIBorderStyleType">
        <xs:sequence>
            <xs:element minOccurs="1" maxOccurs="1" name="BorderBottom" type="xs:int"/>
            <xs:element minOccurs="1" maxOccurs="1" name="BorderColor" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="BorderLeft" type="xs:int"/>
            <xs:element minOccurs="1" maxOccurs="1" name="BorderRight" type="xs:int"/>
            <xs:element minOccurs="1" maxOccurs="1" name="BorderTop" type="xs:int"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'UIBorderStyleType'
    xml_children = [
        SEVDChild('BorderBottom', 'border_bottom', required=True, valid_values=int_set_func),
        SEVDChild('BorderColor', 'border_color', required=True, valid_values=regex_set_func(COLOR_REGEX)),
        SEVDChild('BorderLeft', 'border_left', required=True, valid_values=int_set_func),
        SEVDChild('BorderRight', 'border_right', required=True, valid_values=int_set_func),
        SEVDChild('BorderTop', 'border_top', required=True, valid_values=int_set_func),
    ]


class UIFieldStyleType(BaseSEVDObject):
    '''
    NOTE: Not defined in original XSD. SPS says they do not have XSD for it.
    <xs:complexType name="UIFieldStyleType">
        <xs:sequence>
            <xs:element minOccurs="1" maxOccurs="1" name="Color" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Family" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Size" type="xs:int"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'UIFieldStyleType'
    xml_children = [
        SEVDChild('Color', 'color', required=True, valid_values=required_regex_set_func(COLOR_REGEX)),
        SEVDChild('Family', 'family', required=True),
        SEVDChild('Size', 'size', required=True, valid_values=int_set_func),
    ]


class UIWizardType(BaseSEVDObject):
    '''
    NOTE: Not defined in original XSD. SPS says they do not have XSD for it.
    <xs:complexType name="UIWizardType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="BackgroundColor" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="BorderStyle" type="UIBorderStyleType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="FieldStyle" type="UIFieldStyleType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="LabelStyle" type="UIFieldStyleType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'UIWizardType'
    xml_children = [
        SEVDChild('BackgroundColor', 'background_color', valid_values=regex_set_func(COLOR_REGEX)),
        SEVDChild('BorderStyle', 'border_style', UIBorderStyleType),
        SEVDChild('FieldStyle', 'field_style', UIFieldStyleType),
        SEVDChild('LabelStyle', 'label_style', UIFieldStyleType),
    ]


class UIWizardSupportType(BaseSEVDObject):
    '''
    NOTE: Not defined in original XSD. SPS says they do not have XSD for it.
    <xs:complexType name="UIWizardSupportType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Visible" type="xs:boolean"/>
            <xs:element minOccurs="0" maxOccurs="1" name="BackgroundColor" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="BorderStyle" type="UIBorderStyleType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="FieldStyle" type="UIFieldStyleType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="LabelStyle" type="UIFieldStyleType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'UIWizardSupportType'
    xml_children = [
        SEVDChild('Visible', 'visible', valid_values=boolean_set_func),
        SEVDChild('BackgroundColor', 'background_color', valid_values=regex_set_func(COLOR_REGEX)),
        SEVDChild('BorderStyle', 'border_style', UIBorderStyleType),
        SEVDChild('FieldStyle', 'field_style', UIFieldStyleType),
        SEVDChild('LabelStyle', 'label_style', UIFieldStyleType),
    ]


class UIStyleType(BaseSEVDObject):
    '''
    NOTE: Defined improperly in original XSD. SPS says they do not have XSD for it. See UIThemeType.
    <xs:complexType name="UIStyleType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Wizard" type="UIWizardType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="WizardStepLeft" type="UIWizardType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="WizardStepRight" type="UIWizardType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="WizardSupport" type="UIWizardSupportType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="WizardTitle" type="UIWizardType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Buttons" type="UIWizardType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'UIStyleType'
    xml_children = [
        SEVDChild('Wizard', 'wizard', UIWizardType),
        SEVDChild('WizardStepLeft', 'wizard_step_left', UIWizardType),
        SEVDChild('WizardStepRight', 'wizard_step_right', UIWizardType),
        SEVDChild('WizardSupport', 'wizard_support', UIWizardSupportType),
        SEVDChild('WizardTitle', 'wizard_title', UIWizardType),
        SEVDChild('Buttons', 'buttons', UIWizardType),
    ]


class UIDisplayType(BaseSEVDObject):
    '''

    <xs:complexType name="UIDisplayType">
        <xs:sequence>
            <xs:element minOccurs="1" maxOccurs="1" name="Header" type="xs:boolean"/>
            <xs:element minOccurs="1" maxOccurs="1" name="SupportLink" type="xs:boolean"/>
            <xs:element minOccurs="1" maxOccurs="1" name="CheckPayment" type="xs:boolean"/>
            <xs:element minOccurs="1" maxOccurs="1" name="CardPayment" type="xs:boolean"/>
            <xs:element minOccurs="1" maxOccurs="1" name="SELogo" type="xs:boolean"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'UIDisplayType'
    xml_children = [
        SEVDChild('Header', 'header', valid_values=boolean_set_func),
        SEVDChild('SupportLink', 'support_link', valid_values=boolean_set_func),
        SEVDChild('CheckPayment', 'check_payment', valid_values=boolean_set_func),
        SEVDChild('CardPayment', 'card_payment', valid_values=boolean_set_func),
        SEVDChild('SELogo', 'se_logo', valid_values=boolean_set_func),
    ]


class UIThemeType(BaseSEVDObject):
    '''
    NOTE: this is actually defined as UIStyle in the XSD available from SPS.
    <xs:complexType name="UIThemeType">
        <xs:sequence>
            <xs:element minOccurs="1" maxOccurs="1" name="MainFontColor" type="HexColorType"/>
            <xs:element minOccurs="1" maxOccurs="1" name="MainBackColor" type="HexColorType"/>
            <xs:element minOccurs="1" maxOccurs="1" name="HeaderBackColor" type="HexColorType"/>
            <xs:element minOccurs="1" maxOccurs="1" name="TotalsBoxBackColor" type="HexColorType"/>
            <xs:element minOccurs="1" maxOccurs="1" name="DividerBackColor" type="HexColorType"/>
        </xs:sequence>
    </xs:complexType>
    <xs:simpleType name="HexColorType">
        <xs:restriction base="xs:string">
            <xs:pattern value="#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]"/>
        </xs:restriction>
    </xs:simpleType>
    '''
    xml_element = 'UIThemeType'
    xml_children = [
        SEVDChild('MainFontColor', 'main_font_color', valid_values=regex_set_func(HEX_COLOR_REGEX)),
        SEVDChild('MainBackColor', 'main_back_color', valid_values=regex_set_func(HEX_COLOR_REGEX)),
        SEVDChild('HeaderBackColor', 'header_back_color', valid_values=regex_set_func(HEX_COLOR_REGEX)),
        SEVDChild('TotalsBoxBackColor', 'totals_box_back_color', valid_values=regex_set_func(HEX_COLOR_REGEX)),
        SEVDChild('DividerBackColor', 'divider_back_color', valid_values=regex_set_func(HEX_COLOR_REGEX)),
    ]


class UIType(BaseSEVDObject):
    '''

    <xs:complexType name="UIType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="UIStyle" type="UIStyleType"/> <!-- this is not defined in original schema, added by ddorothy -->
            <xs:element minOccurs="0" maxOccurs="1" name="Display" type="UIDisplayType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Theme" type="UIThemeType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="SinglePayment" type="SinglePaymentUIType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultOperation" type="VaultOperationUIType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'UIType'
    xml_children = [
        SEVDChild('UIStyle', 'style', UIStyleType),
        SEVDChild('Display', 'display', UIDisplayType),
        SEVDChild('Theme', 'theme', UIThemeType),
        SEVDChild('SinglePayment', 'single_payment', SinglePaymentUIType),
        SEVDChild('VaultOperation', 'vault_operation', VaultOperationUIType),
    ]


class PostbackType(BaseSEVDObject):
    '''

    <xs:complexType name="PostbackType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="HttpsUrl" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'PostBack'
    xml_children = [
        SEVDChild('HttpsUrl', 'url', required=True),
    ]


class PaymentType(BaseSEVDObject):
    '''

    <xs:complexType name="PaymentType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Merchant" type="MerchantType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionBase" type="TransactionBaseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Customer" type="PersonType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="ShippingRecipient" type="PersonType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Level2" type="Level2Type"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Level3" type="Level3Type"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Recurring" type="RecurringType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultStorage" type="VaultStorageType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Postback" type="PostbackType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'PaymentType'
    xml_children = [
        SEVDChild('Merchant', 'merchant', MerchantType, required=True),
        SEVDChild('TransactionBase', 'transaction_base', TransactionBaseType, required=True),
        SEVDChild('Customer', 'customer', PersonType),
        SEVDChild('ShippingRecipient', 'shipping_recipient', PersonType),
        SEVDChild('Level2', 'level2', Level2Type),
        SEVDChild('Level3', 'level3', Level3Type),
        SEVDChild('VaultStorage', 'vault_storage', VaultStorageType),
        SEVDChild('Recurring', 'recurring', RecurringType),
        SEVDChild('Postback', 'postback', PostbackType),
    ]


class Payments(BaseSEVDObject):
    '''

    <xs:complexType name="ArrayOfPaymentType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="unbounded" name="PaymentType" nillable="true" type="PaymentType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Payments'
    xml_children = [
        SEVDChild('PaymentType', 'payment_type', PaymentType, multiple=True),
    ]


def batch_payment_set_func(name):
    def setter(obj, value):
        if str(value).strip() not in BatchType.BATCH_PAYMENT_OPTIONS and value is not None:
            raise ValueError('%s: "%s" is not a valid Batch Payment. Please refer to the documentation for a list.')
        setattr(obj, name, value)
    return setter


class BatchType(BaseSEVDObject):
    '''

    <xs:complexType name="BatchType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Merchant" type="MerchantType"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Net" type="xs:double"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Count" type="xs:int"/>
            <xs:element minOccurs="1" maxOccurs="1" name="BatchPayment" type="BatchPaymentType"/>
        </xs:sequence>
    </xs:complexType>
    <xs:simpleType name="BatchPaymentType">
        <xs:restriction base="xs:string">
            <xs:enumeration value="CREDITCARD"/>
            <xs:enumeration value="PURCHASECARD"/>
        </xs:restriction>
    </xs:simpleType>
    '''
    BATCH_PAYMENT_OPTIONS = ['CREDITCARD', 'PURCHASECARD']
    xml_element = 'BatchType'
    xml_children = [
        SEVDChild('Merchant', 'merchant', MerchantType, required=True),
        SEVDChild('Net', 'net', valid_values=double_set_func),
        SEVDChild('Count', 'count', valid_values=int_set_func),
        SEVDChild('BatchPayment', 'batch_payment', required=True, valid_values=batch_payment_set_func),
    ]

# Appears to be wrongly implemented.
#class Batch(BaseSEVDObject):
#    xml_element = 'Batch'
#    xml_children = [
#        SEVDChild('BatchType', 'batch_type', BatchType, multiple=True),
#    ]


class Request(BaseSEVDObject):
    '''

    <xs:element name="Request_v1" nillable="true" type="Request_v1"/>
    <xs:complexType name="Request_v1">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Application" type="ApplicationType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="IsSplitPayment" type="xs:boolean"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Payments" type="ArrayOfPaymentType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Batch" type="BatchType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionStatusQueries" type="ArrayOfTransactionStatusQueryType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="RecurringStatusQueries" type="ArrayOfRecurringStatusQueryType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultStatusQuery" type="VaultStatusQueryType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultOperation" type="VaultOperationType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultAccount" type="VaultAccountType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="UI" type="UIType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="AccountQuery" type="AccountQueryType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Postback" type="PostbackType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Request_v1'
    xml_children = [
        SEVDChild('Application', 'application', ApplicationType),
        SEVDChild('IsSplitPayment', 'is_split_payment', valid_values=boolean_set_func),
        SEVDChild('Payments', 'payments', Payments),
        SEVDChild('Batch', 'batch', BatchType),
        SEVDChild('TransactionStatusQueries', 'transaction_status_queries', TransactionStatusQueriesType),
        SEVDChild('RecurringStatusQueries', 'recurring_status_queries', RecurringStatusQueriesType),
        SEVDChild('VaultStatusQuery', 'vault_status_query', VaultStatusQueryType),
        SEVDChild('VaultOperation', 'vault_operation', VaultOperationType),
        SEVDChild('VaultAccount', 'vault_account', VaultAccountType),
        SEVDChild('UI', 'ui', UIType),
        SEVDChild('AccountQuery', 'account_query', AccountQueryType),
        SEVDChild('Postback', 'postback', PostbackType)
    ]

#
# Responses
#


class ResponseType(BaseSEVDObject):
    '''

    <xs:complexType name="ResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="ResponseIndicator" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="ResponseCode" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="ResponseMessage" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Response'
    xml_children = [
        SEVDChild('ResponseIndicator', 'response_indicator'),
        SEVDChild('ResponseCode', 'response_code'),
        SEVDChild('ResponseMessage', 'response_message'),
    ]


class ResponsesType(BaseSEVDObject):
    '''

    <xs:complexType name="ArrayOfResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="unbounded" name="ResponseType" nillable="true" type="ResponseType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Responses'
    xml_children = [
        SEVDChild('ResponseType', 'responses', ResponseType, multiple=True),
    ]


class VaultResponseType(BaseSEVDObject):
    '''

    <xs:complexType name="VaultResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Response" type="ResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="GUID" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="ExpirationDate" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Last4" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="PaymentDescription" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="PaymentTypeID" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'VaultResponse'
    xml_children = [
        SEVDChild('Response', 'response', ResponseType),
        SEVDChild('GUID', 'guid'),
        SEVDChild('ExpirationDate', 'expiration_date'),
        SEVDChild('Last4', 'last4'),
        SEVDChild('PaymentDescription', 'payment_description'),
        SEVDChild('PaymentTypeID', 'payment_type_id'),
    ]


class RecurringResponseType(BaseSEVDObject):
    '''

    <xs:complexType name="RecurringResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="RecurringID" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'RecurringResponse'
    xml_children = [
        SEVDChild('RecurringID', 'recurring_id'),
    ]


class TransactionResponseType(BaseSEVDObject):
    '''

    <xs:complexType name="TransactionResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="AuthCode" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="AVSResult" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="CVVResult" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VANReference" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionID" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Last4" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="PaymentDescription" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Amount" type="xs:double"/>
            <xs:element minOccurs="0" maxOccurs="1" name="PaymentTypeID" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Reference1" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionDate" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="AuxiliaryData" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="EntryMode" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="TaxAmount" type="xs:double"/>
            <xs:element minOccurs="1" maxOccurs="1" name="ShippingAmount" type="xs:double"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'TransactionResponse'
    xml_children = [
        SEVDChild('AuthCode', 'auth_code'),
        SEVDChild('AVSResult', 'avs_result'),
        SEVDChild('CVVResult', 'cvv_result'),
        SEVDChild('VANReference', 'van_reference'),
        SEVDChild('TransactionID', 'transaction_id'),
        SEVDChild('Last4', 'last4'),
        SEVDChild('PaymentDescription', 'payment_description'),
        SEVDChild('Amount', 'amount', required=True, valid_values=double_set_func),
        SEVDChild('PaymentTypeID', 'payment_type_id'),
        SEVDChild('Reference1', 'reference1'),
        SEVDChild('TransactionDate', 'transaction_date'),
        SEVDChild('AuxiliaryData', 'auxiliary_data'),
        SEVDChild('EntryMode', 'entry_mode'),
        SEVDChild('TaxAmount', 'tax_amount', required=True, valid_values=double_set_func),
        SEVDChild('ShippingAmount', 'shipping_amount', required=True, valid_values=double_set_func),
    ]


class TransactionResponsesType(BaseSEVDObject):
    '''

    <xs:complexType name="ArrayOfTransactionResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="unbounded" name="TransactionResponseType" nillable="true" type="TransactionResponseType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'TransactionResponses'
    xml_children = [
        SEVDChild('TransactionResponseType', 'transaction_responses', TransactionResponseType, multiple=True),
    ]


class PaymentResponseType(BaseSEVDObject):
    '''

    <xs:complexType name="PaymentResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Response" type="ResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultResponse" type="VaultResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="RecurringResponse" type="RecurringResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionResponse" type="TransactionResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Customer" type="PersonType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'PaymentResponseType'
    xml_children = [
        SEVDChild('Response', 'response', ResponseType),
        SEVDChild('VaultResponse', 'vault_response', VaultResponseType),
        SEVDChild('RecurringResponse', 'recurring_response', RecurringResponseType),
        SEVDChild('TransactionResponse', 'transaction_response', TransactionResponseType),
        SEVDChild('Customer', 'customer', PersonType),
    ]


class PaymentResponsesType(BaseSEVDObject):
    '''

    <xs:complexType name="ArrayOfPaymentResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="unbounded" name="PaymentResponseType" nillable="true" type="PaymentResponseType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'PaymentResponses'
    xml_children = [
        SEVDChild('PaymentResponseType', 'payment_responses', PaymentResponseType, multiple=True)
    ]


class BatchResponseType(BaseSEVDObject):
    '''

    <xs:complexType name="BatchResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Response" type="ResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="BatchNumber" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="BatchReference" type="xs:string"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Net" type="xs:double"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Count" type="xs:int"/>
            <xs:element minOccurs="1" maxOccurs="1" name="BatchPayment" type="BatchPaymentType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'BatchResponse'
    xml_children = [
        SEVDChild('Response', 'response', ResponseType),
        SEVDChild('BatchNumber', 'batch_number'),
        SEVDChild('BatchReference', 'batch_reference'),
        SEVDChild('Net', 'net', required=True, valid_values=double_set_func),
        SEVDChild('Count', 'count', required=True, valid_values=int_set_func),
        SEVDChild('BatchPayment', 'batch_payment', required=True, valid_values=batch_payment_set_func),
    ]


class TransactionSettlementStatusType(BaseSEVDObject):
    '''

    <xs:complexType name="TransactionSettlementStatusType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionType" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="SettlementType" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="SettlementDate" type="xs:string"/>
            <xs:element minOccurs="0" maxOccurs="1" name="BatchReference" type="xs:string"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'TransactionSettlementStatus'
    xml_children = [
        SEVDChild('TransactionType', 'transaction_type'),
        SEVDChild('SettlementType', 'settlement_type'),
        SEVDChild('SettlementDate', 'settlement_date'),
        SEVDChild('BatchReference', 'batch_reference'),
    ]


class TransactionSettlementStatusesType(BaseSEVDObject):
    '''

    <xs:complexType name="ArrayOfTransactionSettlementStatusType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="unbounded" name="TransactionSettlementStatusType" nillable="true" type="TransactionSettlementStatusType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'TransactionSettlementStatuses'
    xml_children = [
        SEVDChild('TransactionSettlementStatusType', 'transation_settlement_statuses', TransactionSettlementStatusType, multiple=True),
    ]


class TransactionStatusQueryResponseType(BaseSEVDObject):
    '''
    <xs:complexType name="TransactionStatusQueryResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Response" type="ResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultResponse" type="VaultResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="RecurringResponse" type="RecurringResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionResponse" type="TransactionResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionSettlementStatus" type="TransactionSettlementStatusType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Customer" type="PersonType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'TransactionStatusQueryResponseType'
    xml_children = [
        SEVDChild('Response', 'response', ResponseType),
        SEVDChild('VaultResponse', 'vault_response', VaultResponseType),
        SEVDChild('RecurringResponse', 'recurring_response', RecurringResponseType),
        SEVDChild('TransactionResponse', 'transaction_response', TransactionResponseType),
        SEVDChild('TransactionSettlementStatus', 'transaction_settlement_status', TransactionSettlementStatusType),
        SEVDChild('Customer', 'customer', PersonType),
    ]


class TransactionStatusQueryResponsesType(BaseSEVDObject):
    '''

    <xs:complexType name="ArrayOfTransactionStatusQueryResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="unbounded" name="TransactionStatusQueryResponseType" nillable="true" type="TransactionStatusQueryResponseType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'TransactionStatusQueryResponses'
    xml_children = [
        SEVDChild('TransactionStatusQueryResponseType', 'transaction_status_query_responses', TransactionStatusQueryResponseType, multiple=True)
    ]

class RecurringStatusQueryResponseType(BaseSEVDObject):
    '''

    <xs:complexType name="RecurringStatusQueryResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Responses" type="ArrayOfResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionResponses" type="ArrayOfTransactionResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionSettlementStatuses" type="ArrayOfTransactionSettlementStatusType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Customers" type="ArrayOfPersonType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'RecurringStatusQueryResponseType'
    xml_children = [
        SEVDChild('Responses', 'responses', ResponsesType),
        SEVDChild('TransactionResponses', 'transaction_responses', TransactionResponsesType),
        SEVDChild('TransactionSettlementStatuses', 'transaction_settlement_statuses', TransactionSettlementStatusesType),
        SEVDChild('Customers', 'customers', PersonsType),
    ]


class RecurringStatusQueryResponsesType(BaseSEVDObject):
    '''

    <xs:complexType name="ArrayOfRecurringStatusQueryResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="unbounded" name="RecurringStatusQueryResponseType" nillable="true" type="RecurringStatusQueryResponseType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'RecurringStatusQueryResponses'
    xml_children = [
        SEVDChild('RecurringStatusQueryResponseType', 'recurring_status_query', RecurringStatusQueryResponseType, multiple=True)
    ]


class VaultStatusQueryResponseType(BaseSEVDObject):
    '''

    <xs:complexType name="VaultStatusQueryResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Response" type="ResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultResponse" type="VaultResponseType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'VaultStatusQueryResponse'
    xml_children = [
        SEVDChild('Response', 'response', ResponseType),
        SEVDChild('VaultResponse', 'vault_response', VaultResponseType),
    ]


class VaultAccountResponseType(BaseSEVDObject):
    '''

    <xs:complexType name="VaultAccountResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Response" type="ResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultAccount" type="VaultAccountType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Merchant" type="MerchantType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'VaultAccountResponse'
    xml_children = [
        SEVDChild('Response', 'response', ResponseType),
        SEVDChild('VaultAccount', 'vault_account', VaultAccountType),
        SEVDChild('Merchant', 'merchant', MerchantType),
    ]


class AccountQueryResponseType(BaseSEVDObject):
    '''

    <xs:complexType name="AccountQueryResponseType">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="Response" type="ResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Merchant" type="MerchantType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="Services" type="ArrayOfString"/>
            <xs:element minOccurs="1" maxOccurs="1" name="Active" type="xs:boolean"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'AccountQueryResponse'
    xml_children = [
        SEVDChild('Response', 'response', ResponseType),
        SEVDChild('Merchant', 'merchant', MerchantType),
        SEVDChild('Services', 'services'), # TODO: unclear how this should work.
        SEVDChild('Active', 'active', required=True, valid_values=boolean_set_func),
    ]


class Response(BaseSEVDObject):
    '''

    <xs:element name="Response_v1" nillable="true" type="Response_v1"/>
    <xs:complexType name="Response_v1">
        <xs:sequence>
            <xs:element minOccurs="0" maxOccurs="1" name="PaymentResponses" type="ArrayOfPaymentResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="BatchResponse" type="BatchResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="TransactionStatusQueryResponses" type="ArrayOfTransactionStatusQueryResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="RecurringStatusQueryResponses" type="ArrayOfRecurringStatusQueryResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultStatusQueryResponse" type="VaultStatusQueryResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultResponse" type="VaultResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="VaultAccountResponse" type="VaultAccountResponseType"/>
            <xs:element minOccurs="0" maxOccurs="1" name="AccountQueryResponse" type="AccountQueryResponseType"/>
        </xs:sequence>
    </xs:complexType>
    '''
    xml_element = 'Response_v1'
    xml_children = [
        SEVDChild('PaymentResponses', 'payment_responses', PaymentResponsesType),
        SEVDChild('BatchResponse', 'batch_response', BatchResponseType),
        SEVDChild('TransactionStatusQueryResponses', 'transaction_query_responses', TransactionStatusQueryResponsesType),
        SEVDChild('RecurringStatusQueryResponses', 'recurring_query_responses', RecurringStatusQueryResponsesType),
        SEVDChild('VaultStatusQueryResponse', 'vault_query_response', VaultStatusQueryResponseType),
        SEVDChild('VaultResponse', 'vault_response', VaultResponseType),
        SEVDChild('VaultAccountResponse', 'vault_account_response', VaultAccountResponseType),
        SEVDChild('AccountQueryResponse', 'account_query_response', AccountQueryResponseType),
    ]

'''
<xs:complexType name="ArrayOfString">
    <xs:sequence>
        <xs:element minOccurs="0" maxOccurs="unbounded" name="string" nillable="true" type="xs:string"/>
    </xs:sequence>
</xs:complexType>
<xs:element name="Validation" nillable="true" type="Validation"/>
<xs:complexType name="Validation"/>
</xs:schema>
'''

def trim_xml(xml_str):
    if '<' in xml_str and '>' in xml_str:
        while not xml_str.startswith('<'):
            xml_str = xml_str[1:]
        while not xml_str.endswith('>'):
            xml_str = xml_str[:-1]
        return xml_str

def to_xml_string(sage_request):
    global DEBUG
    result = '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(sage_request.to_xml(), 'unicode', short_empty_elements=False).replace('<Request_v1>', '<Request_v1 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">')
    if DEBUG:
        print(result)
    return result

def load_style_ui(ui_xml):
    '''Loads UIStyleType element from a string of XML.'''
    style = UIStyleType()
    style.xml_element = 'UIStyle'
    style.from_xml(ET.XML(ui_xml))
    return style

def encrypt_request(sage_request):
    '''Encrypts a request by calling the Sage Exchange encrypt API.'''
    response = requests.post(SAGE_SEVD_ENCRYPT_URL, data={'request': to_xml_string(sage_request)})
    content = response.content.decode('utf-8')
    while not content.startswith('<'):
        content = content[1:]
    return content
    #doc = ET.XML(response.content)
    #token = doc.find('Token').text
    #data = doc.find('Data').text
    #return token, data

def decrypt_response(xml_response):
    '''Decrypts a response by calling the Sage Exchange decrypt API.'''
    response = requests.post(SAGE_SEVD_DECRYPT_URL, data={'request': xml_response})
    content = trim_xml(response.content.decode('utf-8'))

    return content

def html_form(sage_request, redirect_url, button_value, target='_blank'):
    '''Creates a form for posting to the Sage Vault.'''
    template = '''\
    <form method="POST" action="%(url)s" target="%(target)s">
        <input type="hidden" name="request" value="%(request)s"/>
        <input type="hidden" name="redirect_url" value="%(redirect_url)s"/>
        <input type="hidden" name="consumer_initiated" value="true"/>
        <input type="submit" value="%(button_value)s"/>
    </form>'''

    response = requests.post(SAGE_SEVD_ENCRYPT_URL, data={'request': to_xml_string(sage_request)})
    # remove any nasty characters we cannot interpret
    content = trim_xml(response.content.decode('utf-8'))

    return template % {
        'url': SAGE_SEVD_PAYMENT_URL,
        'request': escape(content),
        'redirect_url': redirect_url,
        'button_value': button_value,
        'target': target,
    }

def execute_vault_delete(app_id, merchant_id, merchant_key, vault_guid, query_first='vault', lang_id='EN'):
    '''Sends a VaultOperation requesting that a card identified by `vault_guid` be deleted.'''
    request = Request()
    request.application = ApplicationType(app_id=app_id, lang_id=lang_id)
    request.vault_operation = VaultOperationType()
    request.vault_operation.merchant = MerchantType(merchant_id=merchant_id, merchant_key=merchant_key)
    request.vault_operation.vault_storage = VaultStorageType(service='DELETE', guid=vault_guid)
    UUID = get_uuid(query_first, app_id, merchant_id, merchant_key)
    request.vault_operation.vault_id = UUID

    response = requests.post(SAGE_SEVD_PAYMENT_URL, data={'request': to_xml_string(request)})
    content = trim_xml(response.content.decode('utf-8'))

    sevd_response = Response()
    sevd_response.from_xml(ET.XML(content.encode('utf8')))
    return sevd_response

def execute_vault_status_query(app_id, merchant_id, merchant_key, vault_id, lang_id='EN'):
    '''Sends a VaultStatusQuery to get the status of a previous VaultOperation.'''
    request = Request()
    request.application = ApplicationType(app_id=app_id, lang_id=lang_id)
    request.vault_status_query = VaultStatusQueryType()
    request.vault_status_query.merchant = MerchantType(merchant_id=merchant_id, merchant_key=merchant_key)
    request.vault_status_query.vault_id = vault_id

    response = requests.post(SAGE_SEVD_PAYMENT_URL, data={'request': to_xml_string(request)})
    content = trim_xml(response.content.decode('utf-8'))

    sevd_response = Response()
    sevd_response.from_xml(ET.XML(content.encode('utf8')))
    return sevd_response

def execute_transaction_status_query(app_id, merchant_id, merchant_key, trans_id, lang_id='EN'):
    request = Request()
    request.application = ApplicationType(app_id=app_id, lang_id=lang_id)
    request.transaction_status_queries = TransactionStatusQueriesType()
    request.transaction_status_queries.transaction_status_queries = TransactionStatusQueryType()
    request.transaction_status_queries.transaction_status_queries.merchant = MerchantType(merchant_id=merchant_id, merchant_key=merchant_key)
    request.transaction_status_queries.transaction_status_queries.trans_id = trans_id

    response = requests.post(SAGE_SEVD_PAYMENT_URL, data={'request': to_xml_string(request)})
    content = trim_xml(response.content.decode('utf-8'))

    sevd_response = Response()
    sevd_response.from_xml(ET.XML(content.encode('utf8')))
    return sevd_response

def execute_auth_with_vault(app_id, merchant_id, merchant_key, vault_guid, amount, street1, city, state, zip_code, street2=None, country=None, first_name=None, last_name=None, middle_initial=None, query_first='payment', lang_id='EN'):
    '''Performs an Authorization on a card in the vault.'''
    request = Request()
    request.application = ApplicationType(app_id=app_id, lang_id=lang_id)
    request.payments = Payments()
    request.payments.payment_type = PaymentType()
    request.payments.payment_type.merchant = MerchantType(merchant_id=merchant_id, merchant_key=merchant_key)
    request.payments.payment_type.customer = PersonType()

    # handle when name is passed in
    if first_name is not None or last_name is not None or middle_initial is not None:
        request.payments.payment_type.customer.name = NameType()
        if first_name is not None:
            request.payments.payment_type.customer.name.first_name = first_name
        if last_name is not None:
            request.payments.payment_type.customer.name.last_name = last_name
        if middle_initial is not None:
            request.payments.payment_type.customer.name.middle_initial = middle_initial

    request.payments.payment_type.customer.address = AddressType()
    request.payments.payment_type.customer.address.street1 = street1
    if street2 is not None:
        request.payments.payment_type.customer.address.street2 = street2
    request.payments.payment_type.customer.address.city = city
    request.payments.payment_type.customer.address.state = state
    request.payments.payment_type.customer.address.zip_code = zip_code
    if country is not None:
        request.payments.payment_type.customer.address.country = country
    request.payments.payment_type.transaction_base = TransactionBaseType()
    request.payments.payment_type.transaction_base.trans_id = get_uuid(query_first, app_id, merchant_id, merchant_key)
    request.payments.payment_type.transaction_base.trans_type = '02' # AUTH NO UI
    request.payments.payment_type.transaction_base.amount = amount
    request.payments.payment_type.vault_storage = VaultStorageType()
    request.payments.payment_type.vault_storage.service = 'RETRIEVE'
    request.payments.payment_type.vault_storage.guid = vault_guid

    response = requests.post(SAGE_SEVD_PAYMENT_URL, data={'request': to_xml_string(request)})
    content = trim_xml(response.content.decode('utf-8'))

    sevd_response = Response()
    sevd_response.from_xml(ET.XML(content.encode('utf8')))
    return sevd_response

def execute_void(app_id, merchant_id, merchant_key, transaction_id, query_first='payment', lang_id='EN'):
    '''Performs a void on an existing transaction.'''
    request = Request()
    request.application = ApplicationType(app_id=app_id, lang_id=lang_id)
    request.payments = Payments()
    request.payments.payment_type = PaymentType()
    request.payments.payment_type.merchant = MerchantType(merchant_id=merchant_id, merchant_key=merchant_key)
    request.payments.payment_type.transaction_base = TransactionBaseType()
    request.payments.payment_type.transaction_base.trans_id = get_uuid(query_first, app_id, merchant_id, merchant_key)
    request.payments.payment_type.transaction_base.trans_type = '04'
    request.payments.payment_type.transaction_base.van_reference = transaction_id

    response = requests.post(SAGE_SEVD_PAYMENT_URL, data={'request': to_xml_string(request)})
    content = trim_xml(response.content.decode('utf-8'))

    sevd_response = Response()
    sevd_response.from_xml(ET.XML(content.encode('utf8')))
    return sevd_response
