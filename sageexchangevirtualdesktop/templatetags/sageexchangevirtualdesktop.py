'''
Created on Apr 23, 2014

@author: ddorothy
'''
import uuid

from django import template
from django.conf import settings

from .. import sevd

register = template.Library()

@register.simple_tag
def vault_form():
    request = sevd.Request()
    request.application = sevd.ApplicationType()
    request.vault_operation = sevd.VaultOperationType()
    request.vault_operation.merchant = sevd.MerchantType()
    request.vault_operation.vault_storage = sevd.VaultStorageType(service='CREATE')
    request.vault_operation.vault_id = sevd.get_uuid()
    request.postback = sevd.PostbackType(url=settings.SEVD_VAULT_CREATE_POSTBACK_URL)
    
    return sevd.html_form(request, settings.SEVD_VAULT_CREATE_RETURN_URL, settings.SEVD_VAULT_CREATE_BUTTON_TEXT)
