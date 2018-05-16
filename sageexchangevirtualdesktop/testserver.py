#!/usr/bin/python
'''A simple HTTP server to test various aspects of the Sage Integration.

To use:
* run this file (python testserver.py)
* Open a browser and navigate to http://localhost:8080
'''
import os
import uuid

from bottle import request, route, run

from . import sevd

SERVER_NAME = 'localhost'
PORT_NUMBER = 8080
TEST_MERCHANT_ID = os.environ['MERCHANT_ID']
TEST_MERCHANT_KEY = os.environ['MERCHANT_KEY']
APPLICATION_ID = os.environ['APPLICATION_ID']

UUID = None

def html_wrapper(content):
    return '<html><body>%s<div style="position: absolute; top: 0; right: 0"><a href="/">Back to Menu</a></div></body></html>' % content

def get_form(return_url):
    '''Gets the form needed to send user to SEVD interface.'''
    global UUID

    request = sevd.Request()
    request.application = sevd.ApplicationType(app_id=APPLICATION_ID, lang_id='EN')
    request.vault_operation = sevd.VaultOperationType()
    request.vault_operation.merchant = sevd.MerchantType(merchant_id=TEST_MERCHANT_ID, merchant_key=TEST_MERCHANT_KEY)
    request.vault_operation.vault_storage = sevd.VaultStorageType(service='CREATE')
    UUID = sevd.format_uuid(uuid.uuid4().hex)
    request.vault_operation.vault_id = UUID
    #request.ui = sevd.UIType()
    #request.ui.display = sevd.UIDisplayType()
    #request.ui.display.support_link = False

    return html_wrapper(sevd.html_form(request, return_url, "Enter Credit Card Information", target=''))

@route('/')
def default_page():
    return html_wrapper('''<h1>Choose Test</h1>
        <ul>
            <li><a href="/basic">Basic</a> - simple test.</li>
            <li><a href="/withname">With Name</a> - like Basic but adds step to get name and address info.</li>
            <li><a href="/uitest">UI Test</a> - allows for adjusting UI</li>
        </ul>''')

###############################################################################
# BASIC Test
#
# This was the inital test that was created for SEVD integration.
###############################################################################

@route('/basic')
def basic_page():
    global SERVER_NAME, PORT_NUMBER

    return get_form('http://%s:%d/basic/return' % (SERVER_NAME, PORT_NUMBER))

@route('/basic/return')
@route('/basic/return', method="POST")
def basic_return_page():
    global UUID, APPLICATION_ID, TEST_MERCHANT_ID, TEST_MERCHANT_KEY

    vault_status_test = 'Not Run'
    auth_test = 'Not Run'
    void_test = 'Not Run'
    vault_delete_test = 'Not Run'

    # vault_query_test
    response = sevd.execute_vault_status_query(APPLICATION_ID, TEST_MERCHANT_ID, TEST_MERCHANT_KEY, UUID)
    if response.vault_query_response.response.response_indicator in ('A', 'I'):
        vault_status_test = 'Success <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))
        vault_guid = response.vault_query_response.vault_response.guid

        # auth with out UI test
        response = sevd.execute_auth_with_vault(APPLICATION_ID, TEST_MERCHANT_ID, TEST_MERCHANT_KEY, vault_guid, '1.00', '502 W. Pippen Street', 'Whitakers', 'NC', '27891')
        if response.payment_responses.payment_responses.response.response_indicator in ('A', 'I'):
            auth_test = 'Success <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))
            van_reference = response.payment_responses.payment_responses.transaction_response.van_reference

            # void without UI test
            response = sevd.execute_void(APPLICATION_ID, TEST_MERCHANT_ID, TEST_MERCHANT_KEY, van_reference)
            if response.payment_responses.payment_responses.response.response_indicator in ('A', 'I'):
                void_test = 'Success <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))
            else:
                void_test = 'Failed <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))

        else:
            auth_test = 'Failed <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))

        # vault delete test
        response = sevd.execute_vault_delete(APPLICATION_ID, TEST_MERCHANT_ID, TEST_MERCHANT_KEY, vault_guid)
        if response.vault_response.response.response_indicator in ('A', 'I'):
            vault_delete_test = 'Success <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))
        else:
            vault_delete_test = 'Failed <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))

    else:
        vault_status_test = 'Failed <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))

    return html_wrapper("Vault Status Test: %s<br/>Auth. Test: %s<br/>Void Test: %s<br/>Vault Delete Test: : %s" % (vault_status_test, auth_test, void_test, vault_delete_test))

###############################################################################
# WITHNAME Test
#
# Allows specifying the address and name of the customer.
###############################################################################

@route('/withname')
def withname_page():
    global SERVER_NAME, PORT_NUMBER
    return get_form('http://%s:%d/withname/return' % (SERVER_NAME, PORT_NUMBER))

@route('/withname/return')
@route('/withname/return', method="POST")
def withname_return_page():
    return html_wrapper('''<h1>Enter Customer Information</h1>
    <form action="/withname/process" method="post">
        <div>
            <label>First Name: <input type="text" name="first_name"/></label>
            <label>Middle Initial: <input type="text" name="middle_initial" size="2" maxlength="2"/></label>
            <label>Last Name: <input type="text" name="last_name"/></label>
        </div>
        <div>
            <label>Street: <input type="text" name="street1"/></label>
            <label>Street 2 (optional): <input type="text" name="street2"/></label>
            <label>City: <input type="text" name="city"/></label>
            <label>State: <input type="text" name="state"/></label>
            <label>Zip Code: <input type="text" name="zip_code"/></label>
        </div>
        <input type="submit" value="Submit"/>
    </form>
    ''')

@route('/withname/process', method='POST')
def withname_process_page():
    global UUID, APPLICATION_ID, TEST_MERCHANT_ID, TEST_MERCHANT_KEY

    first_name = request.forms.get('first_name', None)
    middle_initial = request.forms.get('middle_initial', None)
    last_name = request.forms.get('last_name', None)

    street1 = request.forms.get('street1', None)
    street2 = request.forms.get('street2', None)
    city = request.forms.get('city', None)
    state = request.forms.get('state', None)
    zip_code = request.forms.get('zip_code', None)

    if street2 == '':
        street2 = None

    if first_name == '':
        first_name = None

    if middle_initial == '':
        middle_initial = None

    if last_name == '':
        last_name = None

    vault_status_test = 'Not Run'
    auth_test = 'Not Run'
    void_test = 'Not Run'
    vault_delete_test = 'Not Run'

    # vault_query_test
    response = sevd.execute_vault_status_query(APPLICATION_ID, TEST_MERCHANT_ID, TEST_MERCHANT_KEY, UUID)
    if response.vault_query_response.response.response_indicator in ('A', 'I'):
        vault_status_test = 'Success <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))
        vault_guid = response.vault_query_response.vault_response.guid

        # auth with out UI test
        response = sevd.execute_auth_with_vault(APPLICATION_ID, TEST_MERCHANT_ID, TEST_MERCHANT_KEY, vault_guid, '1.00', street1, city, state, zip_code, street2=street2, first_name=first_name, last_name=last_name, middle_initial=middle_initial)
        if response.payment_responses.payment_responses.response.response_indicator in ('A', 'I'):
            auth_test = 'Success <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))
            van_reference = response.payment_responses.payment_responses.transaction_response.van_reference

            # void without UI test
            response = sevd.execute_void(APPLICATION_ID, TEST_MERCHANT_ID, TEST_MERCHANT_KEY, van_reference)
            if response.payment_responses.payment_responses.response.response_indicator in ('A', 'I'):
                void_test = 'Success <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))
            else:
                void_test = 'Failed <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))

        else:
            auth_test = 'Failed <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))

        # vault delete test
        response = sevd.execute_vault_delete(APPLICATION_ID, TEST_MERCHANT_ID, TEST_MERCHANT_KEY, vault_guid)
        if response.vault_response.response.response_indicator in ('A', 'I'):
            vault_delete_test = 'Success <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))
        else:
            vault_delete_test = 'Failed <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))

    else:
        vault_status_test = 'Failed <pre>%s</pre>' % sevd.escape(sevd.to_xml_string(response))

    return html_wrapper("Vault Status Test: %s<br/>Auth. Test: %s<br/>Void Test: %s<br/>Vault Delete Test: : %s" % (vault_status_test, auth_test, void_test, vault_delete_test))

###############################################################################
# UI Test
#
# This is not really designed to follow through with processing. Instead this 
# allows various settings to be attempted and to see how they look.
###############################################################################

@route('/uitest')
def uitest_page():
    global UUID

    request = sevd.Request()
    request.application = sevd.ApplicationType(app_id=APPLICATION_ID, lang_id='EN')
    request.vault_operation = sevd.VaultOperationType()
    request.vault_operation.merchant = sevd.MerchantType(merchant_id=TEST_MERCHANT_ID, merchant_key=TEST_MERCHANT_KEY)
    request.vault_operation.vault_storage = sevd.VaultStorageType(service='CREATE')
    UUID = sevd.format_uuid(uuid.uuid4().hex)
    request.vault_operation.vault_id = UUID

    request.ui = sevd.UIType()
    request.ui.theme = sevd.UIThemeType()
    request.ui.theme.header_back_color = '#FFFFFF'
    request.ui.style = sevd.load_style_ui('''<UIStyle>
            <Wizard>
                <BackgroundColor>0000FF</BackgroundColor>
                <BorderStyle>
                    <BorderBottom>1</BorderBottom>
                    <BorderColor>FF0000</BorderColor>
                    <BorderLeft>1</BorderLeft>
                    <BorderRight>1</BorderRight>
                    <BorderTop>1</BorderTop>
                </BorderStyle>
                <FieldStyle>
                    <Color>00FF00</Color>
                    <Family>Verdana</Family>
                    <Size>11</Size>
                </FieldStyle>
                <LabelStyle>
                    <Color>00FF00</Color>
                    <Family>Verdana</Family>
                    <Size>11</Size>
                </LabelStyle>
            </Wizard>
            <WizardStepLeft>
                <BackgroundColor>0000FF</BackgroundColor>
                <BorderStyle>
                    <BorderBottom>1</BorderBottom>
                    <BorderColor>FF0000</BorderColor>
                    <BorderLeft>1</BorderLeft>
                    <BorderRight>1</BorderRight>
                    <BorderTop>1</BorderTop>
                </BorderStyle>
                <FieldStyle>
                    <Color>00FF00</Color>
                    <Family>Verdana</Family>
                    <Size>11</Size>
                </FieldStyle>
                <LabelStyle>
                    <Color>00FF00</Color>
                    <Family>Verdana</Family>
                    <Size>11</Size>
                </LabelStyle>
            </WizardStepLeft>
            <WizardStepRight>
                <BackgroundColor>0000FF</BackgroundColor>
                <BorderStyle>
                    <BorderBottom>2</BorderBottom>
                    <BorderColor>FF0000</BorderColor>
                    <BorderLeft>2</BorderLeft>
                    <BorderRight>2</BorderRight>
                    <BorderTop>2</BorderTop>
                </BorderStyle>
                <FieldStyle>
                    <Color>00FF00</Color>
                    <Family>Verdana</Family>
                    <Size>11</Size>
                </FieldStyle>
                <LabelStyle>
                    <Color>00FF00</Color>
                    <Family>Verdana</Family>
                    <Size>11</Size>
                </LabelStyle>
            </WizardStepRight>
            <WizardSupport>
                <Visible>false</Visible>
                <BackgroundColor>0000FF</BackgroundColor>
                <BorderStyle>
                    <BorderBottom>3</BorderBottom>
                    <BorderColor>FF0000</BorderColor>
                    <BorderLeft>3</BorderLeft>
                    <BorderRight>3</BorderRight>
                    <BorderTop>1000</BorderTop>
                </BorderStyle>
                <FieldStyle>
                    <Color>00FF00</Color >
                    <Family>Verdana</Family>
                    <Size>11</Size>
                </FieldStyle>
                <LabelStyle>
                    <Color>00FF00</Color>
                    <Family>Verdana</Family>
                    <Size>11</Size>
                </LabelStyle>
            </WizardSupport>
            <WizardTitle>
                <BackgroundColor>0000FF</BackgroundColor>
                <BorderStyle>
                    <BorderBottom>0</BorderBottom>
                    <BorderColor>FF0000</BorderColor>
                    <BorderLeft>0</BorderLeft>
                    <BorderRight>0</BorderRight>
                    <BorderTop>0</BorderTop>
                </BorderStyle>
                <FieldStyle>
                    <Color>00FF00</Color>
                    <Family>Verdana</Family>
                    <Size>11</Size>
                </FieldStyle>
                <LabelStyle>
                    <Color>00FF00</Color>
                    <Family>Verdana</Family>
                    <Size>11</Size>
                </LabelStyle>
            </WizardTitle>
            <Buttons>
                <BackgroundColor>0000FF</BackgroundColor>
                <BorderStyle>
                    <BorderBottom>1</BorderBottom>
                    <BorderColor>FF0000</BorderColor>
                    <BorderLeft>1</BorderLeft>
                    <BorderRight>1</BorderRight>
                    <BorderTop>1</BorderTop>
                </BorderStyle>
                <FieldStyle>
                    <Color>00FF00</Color>
                    <Family>Verdana</Family>
                    <Size>12</Size>
                </FieldStyle>
                <LabelStyle>
                    <Color>00FF00</Color>
                    <Family>Verdana</Family>
                    <Size>12</Size>
                </LabelStyle>
            </Buttons>
        </UIStyle>
    ''')

    return html_wrapper(sevd.html_form(request, 'http://%s:%d/uitest' % (SERVER_NAME, PORT_NUMBER), "Enter Credit Card Information"))

def main():
    global SERVER_NAME, PORT_NUMBER
    run(host=SERVER_NAME, port=PORT_NUMBER, debug=True)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('server_name')
    parser.add_argument('-p', help="port, defaults to 8080", type=int)
    args = parser.parse_args()
    SERVER_NAME = args.server_name
    if args.p:
        PORT_NUMBER = args.p

    main()
