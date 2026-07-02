import logging
import base64
import os
from PIL import Image
from django.shortcuts import get_object_or_404
from infraon.sitepackage.basecontroller import BaseController
from infraon.sitepackage.utils.utility import *
from app.common.cmdb.controllers import *
from app.common.cmdb.models import *
from app.common.cmdb.serializers import *
from infraon.permissions import *
from app.common.audits.controllers import AuditController
from mongoengine.queryset.visitor import Q
from app.common.roles.models import ModuleRoleMap
from app.common.roles.serializers import GroupSerializer, ModuleRoleSerializer
from app.common.users.models import GroupProfile
import app.logmanagement.log_integration.rison as rison
from infraon.sitepackage.interfaces.elasticsearch.infraonelasticsearch import *
from infraon.sitepackage.exporthelper.export_helper import *
from infraon.elasticsearch_config import *
from app.logmanagement.log_integration.models import *
from app.logmanagement.log_integration.serializers import *
from app.logmanagement.log_pipeline.models import *
import json
import re
from collections import defaultdict
from infraon.sitepackage.interfaces.infraonai import *
from app.common.bot_config.serializers import InfraonAIKeySettingSerializer
from app.common.bot_config.models import InfraonAIKeySettings
from app.common.bot_config.controllers import BotConfigController
from app.common.users.serializers import UserProfileSerializer
from app.ims.correlation_rule.models import CorrelationRules
from app.ims.correlation_rule.serializers import CorrelationRuleSerializer
from app.ims.purge_configuration.models import *
from datetime import datetime
import asyncio
from infraon.bot_config import Log_MANAGEMENT_NQL_TEMPLATE,BASIC_NQL_PROMPT,Nql_ECS_KEY_DICT,NQL_FAULT_TOLERANCE_PROMPT
from urllib.parse import quote
import zipfile
from math import ceil
from typing import List, Dict,Union,Set,Optional
from app.logmanagement.log_agent_config.models import LogAgentConfig
from app.logmanagement.log_agent_config.serializers import LogAgentConfigSerializer
from app.managementportal.customer.models import Customer
from app.managementportal.customer.serializers import CustomerListSerializer, CustomerEntityListSerializer

logger = logging.getLogger(__name__)
class LogIntegrationController(BaseController):
    elasticObj = InfraonElasticsearch()
    queueObj = InfraonQueue()
    ai_obj = InfraonAI()
    bot_config = BotConfigController()
    NQL_Module_ID = MODULES_APP_KEY_KEY_MAP.get('logmangement_nql')  # ID=155
    CMDB_modals = CMDBCi()
    """
        Log Integration Module
    """

    def get_log_url(self, request):
        """
        Function used form url of Kibana Tool
        :param request:object received on web server.
        :return : kibana url.
        """
        try:
            logger.info("Enter into get_log_url function on LogIntegrationController Controller.")
            url=f"/s/infraon_{self.get_organization_id(request)}/app/discover/"
            target_path = request.GET.get('module_path',url)
            fullUrl = self.construct_kibana_url(request, target_path)
            return fullUrl
        except Exception as err:
            logger.exception(
                "Method get_log_url on LogIntegrationController Controller:%s (%s)" % (err, type(err)))
            return Response(self.get_return_object("error", {}, "Error.err_fail"),
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def rison_encode(self, data):
        try:
            if isinstance(data, dict):
                items = ','.join([f"{self.rison_encode(key)}:{self.rison_encode(value)}" for key, value in data.items()])
                return f"({items})"
            elif isinstance(data, list):
                items = '!'.join([self.rison_encode(item) for item in data])
                return f"!({items})"
            elif isinstance(data, str):
                return f"'{data}'"
            elif isinstance(data, bool):
                return '!t' if data else '!f'
            elif data is None:
                return 'null'
            else:
                return str(data)
        except Exception as err:
            logger.error(
                "Method rison_encode on LogIntegrationController Controller:%s (%s)" % (err, type(err)))

    def construct_kibana_url(self, request, target_path):
        # space_id = ''
        try:
            organization_id = self.get_organization_id(request)
            log_visualization_proxy_url = get_settings("LOG_MGMT_PROXY_VISUALIZATION_URL")
            log_default_password = get_settings("LOG_MGMT_DEFAULT_PASSWORD")
            if target_path.find('monitoring') > -1:
                username = get_settings("LOG_MGMT_SUPER_USER")
                password = get_settings("LOG_MGMT_SUPER_USER_PASSWORD")
            else:
                username = str(request.user.username)
                password = '%s_%s_%s'%(username, organization_id,log_default_password)
            auth_string = f"{username}:{password}"
            asset_id = request.GET.get('assetId')
            encoded_bytes = base64.b64encode(auth_string.encode('utf-8'))
            authHeader = encoded_bytes.decode("utf-8") if isinstance(encoded_bytes, (bytes, bytearray)) else str(encoded_bytes)
            space_id = self.get_space_data_from_role(request.user_group_id, username)
            final_target_path = "/infraon" + target_path
            if space_id:
                final_target_path = "/infraon/s/" + space_id + target_path
            targetUrl = '%s%s'%(log_visualization_proxy_url, final_target_path)
            url_filter={
                'filters': [],
                'refreshInterval': {'pause': True, 'value': 60000},
                'time': {'from': 'now-1d/d', 'to': 'now'},
            }
            _g = rison.dumps(url_filter)
            filters = {}
            # if self.is_msp_customer_user(request) or self.is_multi_customer_user(request):
            post_data = {}
            if request.method == "POST":
                post_data = self.get_post_data(request)
            is_multi_customer_user = self.is_multi_customer_user(request)
            # customer id
            post_data = self.get_post_data(request)
            # customer_id = ''
            # customer_entity_id = ''
            # filters["customer_id"] = []
            # filters["customer_entity_id"] = []
            customer_data = self.get_customer_entity_filter_condition(request, return_dict=True)
            customer_id = customer_data.get('customer_id',"")
            if isinstance(customer_id, list):
                customer_id = customer_id
            customer_entity_id = customer_data.get('customer_entity_id',"")
            if isinstance(customer_entity_id, list):
                customer_entity_id = customer_entity_id
            if customer_id not in self.noneList:
                filters["customer_id"] = customer_id
                if customer_entity_id not in self.noneList:
                    filters["customer_entity_id"] = customer_entity_id
            ra = getattr(request, "auth", "")
            user_auth_token = ra.decode() if isinstance(ra, (bytes, bytearray)) else str(ra)
            filters["auth_token"] = 'infraonDNS' + ' ' + user_auth_token
            if asset_id:
                asset_obj = CMDBCi.objects.get(ci_id=asset_id)
                serializer = CMDBCiListSerializer(asset_obj)
                ser_data = serializer.data
                ip_address = ser_data.get('ip_address','')
                filters["asset_ip"] = [ip_address]
                filter_query = self.get_ip_query_string(ip_address)
                all_logs = self.elasticObj.get_latest_elasticsearch_data('*',filter_query)
                if all_logs:
                    log_data = all_logs[0]
                    index = log_data.get('_index')
                    data_views = self.get_data_views(request,'kibana_url')
                    for data_view in data_views:
                        index_pattern = data_view.get('title', '')
                        regex_pattern = f"^{index_pattern.replace('*', '.*')}$"
                        if re.match(regex_pattern, index):
                            filters["data_view_id"] = data_view.get('id')
                            break       
                if organization_id not in self.noneList:filters["organization_id"] = organization_id
                if self.is_msp_customer_user(request):
                    if customer_id not in self.noneList: filters['customer_id'] = customer_id
                    if customer_entity_id not in self.noneList: filters['customer_entity_id'] = customer_entity_id
            if target_path.find('monitoring') > -1: 
                kibana_url = f"{targetUrl}?auth={authHeader}"
            else:
                kibana_url = f"{targetUrl}?auth={authHeader}&filters={filters}&_g={_g}"    
            return kibana_url
        except Exception as err:
            logger.error(
                "Method construct_kibana_url on LogIntegrationController Controller:%s (%s)" % (err, type(err)))
            
    def get_ip_query_string(self,search_filter):
        """
        Function to get search query string for getting logs from elasticsearch
        :param search_filter: value received from common search field of UI
        :param filter_query: constructed filter query for filtering data in elasticsearch
        """
        try:
            logger.info("Enter into get_ip_query_string function on LogIntegrationController.")
            filter_query = {}
            filter_query['query'] = {}
            filter_query['query']['match'] = {}
            filter_query['query']['match']['host.ip'] = search_filter

            logger.info("Exit from get_search_query_string function on LogIntegrationController.")
            return filter_query
        except Exception as e:
            logger.error("Method get_ip_query_string on LogIntegrationController:%s (%s)" % (e, type(e)))
            return {}

    def sync_log_management_data(self, request_type, data, url):
        """
        function to sync log management data
        :request_type: type of requests POST/GET/DELETE/PUT
        :data: payload data
        :url: url
        :return: response of api
        """
        response_data = {}
        try:
            logger.info("Enter into sync_log_management_data function on LogIntegrationController.")
            base_url = get_settings("LOG_MGMT_VISUALIZATION_URL")
            elastic_hosts = get_settings("LOG_HOSTS")
            user_name = get_settings("LOG_MGMT_SUPER_USER")
            password = get_settings("LOG_MGMT_SUPER_USER_PASSWORD")
            auth_string = f"{user_name}:{password}"
            encoded_auth_string = base64.b64encode(auth_string.encode()).decode()
            if url.find('user') > -1:
                base_url = elastic_hosts[0]
            trigger_sync_url = base_url + url
            payload = json.dumps(data)
            headers = {
                'Accept': 'application/json',
                'Authorization': f'Basic {encoded_auth_string}',
                'Content-Type': 'application/json',
                'kbn-xsrf': 'true',
                'elastic-api-version': '2023-10-31'
            }
            if request_type.upper() == 'GET':
                response = requests.request(request_type,trigger_sync_url,headers=headers,verify=False
            )
            elif request_type == 'DELETE':
                response = requests.request(request_type, trigger_sync_url, headers=headers, verify=False)
            else:
                payload = json.dumps(data)
                response = requests.request(request_type, trigger_sync_url, headers=headers, data=payload, verify=False)
            response_data = {'ok': response.ok, 'reason': response.reason, 'status_code': response.status_code, 'data': response.content}
            logger.info("Response from Tool: %s" % response.text)
            logger.info("Exit into sync_log_management_data function on LogIntegrationController.")
        except requests.exceptions.ConnectionError as exp:
            logger.error("Log Management Role/User Update Failed [Connection Error]. Data to Update - %s - %s" % (str(payload), exp))
            response_data = {'ok': False, 'reason': 'Connection Error', 'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR, 'data': {}}
        except Exception as exception:
            logger.error(
                "Method sync_log_management_data in LogIntegrationController: exception %s - %s" % (
                    exception, type(exception)))
            response_data = {'ok': False, 'reason': 'Connection Error', 'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR, 'data': {}}
        return response_data

    def set_permission_value(self, module_value):
        """
        function to set log permission value
        :module_value : permission key and value
        :return : permission value
        """
        try:
            logger.info("Enter into set_permission_value function on LogIntegrationController.")
            value_list = []
            for key, value in module_value.items():
                if key == 'all' and value:
                    value_list = ['all']
                elif key == 'view' and value:
                    value_list = ['read']
                else:
                    value_list
            logger.info("Exit into set_permission_value function on LogIntegrationController.")
            return value_list
        except Exception as e:
            logger.error('Error in set_permission_value on LogIntegrationController: %s (%s)' % (e, type(e)))
            return value_list
    
    def save_logmgmt_role(self, role_data, selected_permissions, username='', space_id="*"):
        """
        function to save log management role data
        :role_data: role data
        :return: log management response
        """
        celery_params = {}
        try:
            logger.info("Enter into save_logmgmt_role function on LogIntegrationController.")
            role_url = get_settings("LOG_MGMT_ROLE_URL")
            role_name = role_data.get('role_name').replace(' ', '_') +"_"+ username
            url = f"{role_url}/{role_name}"
            request_type = "PUT"
            feature = {}
            for module_key, module_value in selected_permissions.items():
                if module_key in LOG_MGMT_MODULES_LIST:
                    value_list = self.set_permission_value(module_value)
                    feature.update({LOG_MGMT_MODULES_DICT.get(module_key): value_list})
            feature.update({'stackAlerts' : ['all'], 'uptime' : ['all'], 'savedObjectsTagging': ['all'], 'advancedSettings': ['all'], 'savedObjectsManagement': ['all'], 'apm':['all']}) 
            data = {"elasticsearch": {"cluster": ["all"], "indices": [{"names": ["*"], "privileges": ["all"], "field_security": {
                    "grant": ["*"]}, "allow_restricted_indices": False}]}, 'kibana' : [{"spaces": [space_id], "feature": feature}]}
            celery_params['request_type'] = request_type
            celery_params['data'] = data
            celery_params['url'] = url
            logger.info("Exit into save_logmgmt_role function on LogIntegrationController.")
        except Exception as exception:
            logger.error("Method save_logmgmt_role in LogIntegrationController: exception %s - %s" % (exception, type(exception)))
        return celery_params

    def delete_logmgmt_role(self, role_data, username):
        """
        function to delete log management role
        :role_data: role data
        :return: response data
        """
        celery_params = {}
        try:
            logger.info("Enter into delete_logmgmt_role function on LogIntegrationController.")
            role_url = get_settings("LOG_MGMT_ROLE_URL")
            role_name = role_data.replace(' ', '_') +"_"+ username
            url = f"{role_url}/{role_name}"
            request_type = "DELETE"
            celery_params['request_type'] = request_type
            celery_params['data'] = {}
            celery_params['url'] = url
            logger.info("Exit into delete_logmgmt_role function on LogIntegrationController.")
        except Exception as exception:
            logger.error("Method delete_logmgmt_role in LogIntegrationController: exception %s - %s" % (exception, type(exception)))
        return celery_params
    
    def check_logmgmt_module_perm(self, role_id):
        """
        function to check log management permission exists or not
        :role_id : role id
        :return : logmgmt_perm_exists flag
        """
        logmgmt_perm_exists = False
        try:
            logger.info("Enter into check_logmgmt_module_perm function on LogIntegrationController.")
            module_info = ModuleRoleMap.objects.filter(group_id=role_id, module_name__in=LOG_MGMT_MODULES_LIST)
            serializer = ModuleRoleSerializer(module_info, many=True)
            module_role_data = serializer.data
            for role in module_role_data:
                role_permission  = role.get('permission')
                for key, value in role_permission.items():
                    if (key == 'view' or key == 'all') and value:
                        logmgmt_perm_exists = True
                        return logmgmt_perm_exists
            logger.info("Exit into check_logmgmt_module_perm function on LogIntegrationController.")
            return logmgmt_perm_exists
        except Exception as e:
            logger.error('Error in check_logmgmt_module_perm on LogIntegrationController: %s (%s)' % (e, type(e)))
            return logmgmt_perm_exists
    
    def save_log_management_user(self, user_data, organization_id):
        """
        Function to save log management user
        :param user_data: User data
        return: log user data
        """
        data = {}
        celery_params = {}
        try:
            logger.info("Enter into save_log_management_user function on LogIntegrationController.")
            role = GroupProfile.objects.get(organization=organization_id,is_deleted=False,group_id=user_data.get('group_id'))
            role_name = role.role_name.replace(' ', '_')
            role_name = role_name +"_"+ user_data.get('username')
            user_url = get_settings("LOG_MGMT_USER_URL")
            url = f"{user_url}/{user_data.get('username')}"
            password = f"{user_data.get('username')}_{organization_id}_{get_settings('LOG_MGMT_DEFAULT_PASSWORD')}"     
            data = {'full_name': user_data.get('full_name'), 'username': user_data.get('username'),
                    'email': user_data.get('email'), 'roles': [role_name], "password": password}
            request_type = "POST"
            celery_params['request_type'] = request_type
            celery_params['data'] = data
            celery_params['url'] = url
            logger.info("Exit from save_log_management_user on LogIntegrationController")
        except Exception as e:
            logger.error("Method save_log_management_user on LogIntegrationController:%s (%s)" % (e, type(e)))
        return celery_params
    
    def delete_log_management_user(self, user_name):
        """
        function to delete log management role
        :role_data: role data
        :return: response data
        """
        celery_params = {}
        try:
            logger.info("Enter into delete_log_management_user function on LogIntegrationController.")
            user_url = get_settings("LOG_MGMT_USER_URL")
            url = f"{user_url}/{user_name}"
            request_type = "DELETE"
            celery_params['request_type'] = request_type
            celery_params['data'] = {}
            celery_params['url'] = url
            logger.info("Exit into delete_log_management_user function on LogIntegrationController.")
        except Exception as exception:
            logger.error("Method delete_log_management_user in LogIntegrationController: exception %s - %s" % (exception, type(exception)))
        return celery_params
    
    def set_cmdb_filter(self, request):
        """
        Function to set cmdb filters
        :return : cmdb value
        """
        filtered_list = []
        try:
            logger.info(
                "Enter into set_cmdb_filter function on LogIntegrationController.")
            organization_id = self.get_organization_id(request)
            filter_cond = Q(is_deleted=False, organization=organization_id, object_type="Node", is_logmanagement_enabled=True,is_enabled=True)
            post_data = self.get_post_data(request)
            customer_id =""
            customer_entity_id =""
            if request.customer_id not in self.noneList:
                customer_id = request.customer_id
            if post_data.get("customer_id","") not in self.noneList:
                customer_id = post_data.get("customer_id","")
            if request.customer_entity_id not in self.noneList:
                customer_entity_id = request.customer_entity_id
            if post_data.get("customer_entity_id","") not in self.noneList:
                customer_entity_id = post_data.get("customer_entity_id","")
            if isinstance(customer_id, list):
                customer_id = customer_id[0]
            if isinstance(customer_entity_id, list):
                customer_entity_id = customer_entity_id[0]
            if customer_id not in self.noneList:
                filter_cond = filter_cond & Q(customer_id=customer_id)
            if customer_entity_id not in self.noneList:
                filter_cond = filter_cond & Q(customer_id=customer_id)
            
            visibility_filter = self.get_cmdb_visibility_filter(request, organization_id=organization_id)
            if visibility_filter:
                filter_cond = filter_cond & visibility_filter
                #filter_cond = visibility_filter & Q(is_deleted=False,object_type="Node", is_logmanagement_enabled=True,is_enabled=True)
            assets = list(CMDBCi.objects.filter(filter_cond).values_list('ip_address'))
            if assets:
                filtered_list = list(filter(None, assets))
            else:
                filtered_list = ['0.0.0.0']
            filter_query = self.create_log_sever_filter_query(
                request,
                filtered_list,
                customer_id=customer_id,
                customer_entity_id=customer_entity_id
            )
            logger.info(
                "Exit from set_cmdb_filter function on LogIntegrationController .")
            lic_data = self.get_org_license_data(organization_id)
            lic_status = lic_data.get('keys_dict',{}).get("LOG_MANAGEMENT",{}).get('LOG_MANAGEMENT_NQL', False)
            if lic_status:
                nql_ff = True
            else:
                nql_ff = False
            res= {
                "filter_query":[filter_query],
                "log_management_nql" : nql_ff
            }
            return res
        except Exception as err:
            logger.error("Method set_cmdb_filter on LogIntegrationController :%s (%s)" % (
                err, type(err)))
            filter_query = {}
            filter_query["terms"] = {}
            filter_query['terms']['host.ip'] = ['0.0.0.0']
            return [filter_query]
        
    def create_log_sever_filter_query(self, request, node_details, customer_id=None, customer_entity_id=None):
        """
        Create optimized log server filter query.
        Uses filter context only (no scoring).
        Splits host.ip into chunks of 500.
        Applies organization + MSP visibility filters safely.
        """
        try:
            logger.info("Enter into create_log_sever_filter_query function on LogIntegrationController.")
            # Always use filter context for logs
            filter_query = {
                "bool": {
                    "filter": []
                }
            }
            organization_id = self.get_organization_id(request)
            valid_ips = [node for node in node_details if node not in self.noneList]
            if valid_ips:
                chunk_size = 500
                ip_chunks = [
                    valid_ips[i:i + chunk_size]
                    for i in range(0, len(valid_ips), chunk_size)
                ]
                ip_should_query = {
                    "bool": {
                        "should": [
                            {"terms": {"host.ip": chunk}}
                            for chunk in ip_chunks
                        ],
                        "minimum_should_match": 1
                    }
                }
                filter_query["bool"]["filter"].append(ip_should_query)
                if organization_id not in self.noneList:
                    filter_query["bool"]["filter"].append({
                        "term": {
                            "event.organization": organization_id
                        }
                    })
                is_msp_customer = self.is_msp_customer_user(request, return_customer_id=False)
                is_multi_customer_user = self.is_multi_customer_user(request)
                is_msp_org = self.is_msp_org(request, organization_id)
                if is_msp_org and (is_multi_customer_user or is_msp_customer):
                    msp_dict = self.get_log_visibility(request)
                    should_clauses = []
                    if msp_dict.get("msp_list"):
                        for item in msp_dict["msp_list"]:
                            must_filters = []
                            if "customer_id" in item:
                                must_filters.append({
                                    "terms": {
                                        "event.customer_id.keyword": item["customer_id"]
                                    }
                                })
                            if "customer_entity_id" in item:
                                must_filters.append({
                                    "terms": {
                                        "event.customer_entity_id.keyword": item["customer_entity_id"]
                                    }
                                })
                            if must_filters:
                                should_clauses.append({
                                    "bool": {
                                        "filter": must_filters
                                    }
                                })
                    if should_clauses:
                        filter_query["bool"]["filter"].append({
                            "bool": {
                                "should": should_clauses,
                                "minimum_should_match": 1
                            }
                        })
            else:
                # Prevent match-all
                return {
                    "terms": {
                        "host.ip": ["0.0.0.0"]
                    }
                }
            logger.info("Exit from create_log_sever_filter_query function on LogIntegrationController.")
            return filter_query
        except Exception as e:
            logger.error("Method create_log_sever_filter_query on LogIntegrationController: %s (%s)" % (e, type(e)))
            return {
                "terms": {
                    "host.ip": ["0.0.0.0"]
                }
            }

    def get_data_views(self, request, flag, script_flag=False, from_pipeline=False, pipeline={}):
        """
        function to get data view list
        :return: data view list
        """
        data_view = []
        new_data_view = []
        request_data = {}
        try:
            logger.info("Enter into get_data_view function on LogIntegrationController.")
            url = get_settings("LOG_MGMT_DATA_VIEW_URL")
            request_type = "GET"
            organization_id = self.get_organization_id(request)
            if organization_id in self.noneList:
                organization_id = request
            space_url = f"/s/infraon_{organization_id}/api"
            url = url.replace("/api", space_url, 1)
            response_data = self.sync_log_management_data(request_type, request_data, url)
            if response_data.get('data'):
                data_view = json.loads(response_data.get('data').decode('utf-8')).get('data_view')
                if script_flag:
                    single_data_view = [item for item in data_view if item['title'] == "**"]
                    if single_data_view in self.noneList:
                        data_url = get_settings("LOG_MGMT_DATA_VIEW_URL") + '/data_view'
                        space_url = f"/s/infraon_{organization_id}/api"
                        data_view_url = data_url.replace("/api", space_url, 1)
                        request_type = "POST"
                        request_data = {
                            "data_view": {
                            "title": "**",
                            "name": "Logs",
                            "timeFieldName": "@timestamp"
                            }   
                        }
                        response_data = self.sync_log_management_data(request_type, request_data, data_view_url)
                elif from_pipeline:
                    multi_index_title = pipeline.get('title')
                    multi_index_name = pipeline.get('name')
                    single_data_view = [item for item in data_view if item['title'] == multi_index_title]
                    if single_data_view in self.noneList:
                        data_url = get_settings("LOG_MGMT_DATA_VIEW_URL") + '/data_view'
                        space_url = f"/s/infraon_{organization_id}/api"
                        data_view_url = data_url.replace("/api", space_url, 1)
                        request_type = "POST"
                        request_data = {
                            "data_view": {
                            "title": multi_index_title,
                            "name": multi_index_name,
                            "timeFieldName": "@timestamp"
                            }   
                        }
                        response_data = self.sync_log_management_data(request_type, request_data, data_view_url)
                else:
                    new_data_view = [item for item in data_view if not item['title'].startswith('.')]
            if flag != 'kibana_url':
                new_regex_list = [i for i in new_data_view if i.get('name')]
                index_name_list = self.get_indices(request)
                new_data_view =[]
                for obj in new_regex_list:
                    if "title" in obj:
                        titles = [t.strip() for t in obj["title"].split(",")]
                        matched = False
                        for title_pattern in titles:
                            if title_pattern == '**':
                                matched = True
                            else:
                                pattern = re.compile(title_pattern)
                                if any(pattern.match(index) for index in index_name_list):
                                    matched = True
                        if matched and obj not in new_data_view:
                            new_data_view.append(obj)
            logger.info("Exit into get_data_view function on LogIntegrationController.")
        except Exception as exception:
            new_data_view = []
            logger.error("Method get_data_view in LogIntegrationController: exception %s - %s" % (exception, type(exception)))
        return new_data_view
    
    def add_export_data_queue(self, request):
        """
        Function to get log export data
        :return : log data value
        """
        try:
            logger.info("Enter into add_export_data_queue function on LogIntegrationController.")
            request_data = request.data
            params = request_data.get('params',{})
            index_patterns = params.get('index_patterns',[])
            start_time = params.get('start_time')
            end_time = params.get('end_time')
            filter_query = self.convert_to_elasticsearch_filter(params.get('filters',[]),start_time,end_time)
            if index_patterns:
                index = index_patterns[0].get('title','')
                params['index'] = index
                params['filter_query'] = filter_query
                params['organization_id'] = self.get_organization_id(request)
                params['start_time'] = start_time
                params['end_time'] = end_time
                params['module_type'] = "Log export"
                is_valid,msg_dict = self.is_valid_export(params)
                logger.info("Exit from add_export_data_queue function on LogIntegrationController .")
                if is_valid:
                    response = self.send_logmgmt_export_data_to_queue(request, params)
                    return response
                else:
                    return msg_dict
        except Exception as err:
            logger.error("Method add_export_data_queue on LogIntegrationController :%s (%s)" % (
                err, type(err)))
        

    def send_logmgmt_export_data_to_queue(self, request, celery_params):
        """
        function to send log management export data to queue
        :celery_params: celery params
        :return: true/false
        """
        try:
            organization_id = celery_params.get('organization_id')
            user_details = {}
            file_type = celery_params.get('type')
            profile_id = request.user_profile_id
            user_obj = UserProfile.objects.filter(profile_id=profile_id,organization=organization_id,is_active=True).first()
            if user_obj:
                user_details['profile_id'] = profile_id
                user_details['user_tz'] = user_obj.timezone_id
                user_details['user_id'] = user_obj.user
                user_details['full_name'] = user_obj.full_name
                celery_params['user_details'] = user_details
            data_obj = ExportConfig()
            data_obj.export_id = getID()
            data_obj.name = celery_params.get('name','')
            data_obj.description = celery_params.get('description','')
            data_obj.filters = str(celery_params)
            data_obj.type = celery_params.get('module_type')
            data_obj.file_type = file_type
            data_obj.user_details = user_details
            data_obj.organization = organization_id
            data_obj.child_pipeline_list=celery_params.get('child_pipeline_list')
            data_obj.pipeline_type=celery_params.get('pipeline_type')
            creation_time = datetime.now(pytz.timezone(get_settings('TIME_ZONE')))
            data_obj.creation_time = creation_time
            data_obj.save()
            celery_params['export_id'] = data_obj.export_id
            if celery_params.get('module_type') != "Log export":
                celery_params['request_data'] = self.serialize_request(request)
            # celery_params['request_data'] = self.serialize_request(request)
            queue_obj = InfraonQueue()
            task_name = "app.logmanagement.log_integration.tasks.start_logmanagement_export"
            out = queue_obj.send_data(celery_params, "export_logmanagement_data", task_name)
            if out:
                logger.info("Sending log management export data to queue - %s (%s) " % (organization_id, file_type))
                if celery_params.get('module_type') == "Log export":
                    return {"status": "success", "message": "Data is queued for export."}
                else:
                    pipeline_id =  celery_params.get('pipeline_id')
                    if pipeline_id:
                        LogPipelineConfiguration.objects.filter(pipeline_id = pipeline_id).update(status = 5, status_msg="Added to Queue")
                    return {"status": "success", "message": "Data is queued for pipeline upload."}
            else:
                logger.error("Log management export data to queue failed - %s (%s)." % (organization_id, file_type))
                if celery_params.get('module_type') == "Log export":
                    return {"status": "failed", "message":"Error in sending log management export data to queue."}
                else:
                    return {"status": "failed", "message":"Error in sending log management log pipeline data to queue."}
        except Exception as e:
            logger.exception("Error sending log management export data - %s (%s)" % (organization_id, file_type))
            if celery_params.get('module_type') == "Log export":
                return {"status": "failed", "message":"Error in sending log management export data to queue:%s"%e}
            else:
                return {"status": "failed", "message":"Error in sending log management log pipeline data to queue:%s"%e}
            
    def serialize_request(self,request):
        return {
            "method": request.method,
            "path": request.get_full_path(),
            "headers": dict(request.headers),
            "query_params": request.query_params.dict(),
            "data": request.data,
            "user": {
                "id": request.user.id,
                "username": request.user.username,
                "is_authenticated": request.user.is_authenticated,
            } if request.user.is_authenticated else None,
            "session": dict(request.session.items()) if hasattr(request, "session") else {},
            "cookies": request.COOKIES,
        }

    
    def export_log_data(self,params):
        """
        function to export log data
        :params: params
        """
        batch_size = 100000
        status = 1
        file_to_upload = None
        file_size = 0
        is_zip = False
        all_file_paths = []
        try:
            logger.info("Enter into export_log_data function on LogIntegrationController.")
            index = params.get('index')
            filter_query = params.get('filter_query')
            file_type = params.get('type')
            start_time = params.get('start_time')
            end_time = params.get('end_time')
            user_details = params.get('user_details',{})
            user_tz = user_details.get('user_tz','UTC')
            redable_start_time, readable_end_time = self.convert_relative_time_to_readable(start_time, end_time, user_tz)
            params['readable_start_time'] = redable_start_time
            params['readable_end_time'] = readable_end_time
            organization_id = params.get('organization_id')
            export_id = params.get('export_id')
            export_name = params.get('name','export')
            st = datetime.strptime(params.get('readable_start_time'), "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
            et = datetime.strptime(params.get('readable_end_time'), "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
            time_stamp = st +"-to-"+ et
            if export_id:
                ExportConfig.objects.filter(export_id = export_id, organization = organization_id).update(status=1)
            total_logs = self.elasticObj.get_elasticsearch_data(index, filter_query, is_count=True)
            fetched_count = 0
            total_fetched = 0
            search_after = None
            batch_sizes = []
            batch_num = 0
            total = copy.deepcopy(total_logs)
            while total > 0:
                size = min(batch_size, total)
                batch_sizes.append(size)
                total -= size
            for batch_size in batch_sizes:
                batch_data, params, batch_num, search_after, fetched_count, total_fetched = self.elasticObj.get_elasticsearch_data(index, filter_query, params=params, batch_num=batch_num, export_log=True, total_logs=total_logs, fetched_count=fetched_count, total_fetched=total_fetched, search_after=search_after, batch_size=batch_size)
                if not batch_data:
                    break
                if file_type == 'excel':
                    file_path, download_dir = self.export_log_data_to_excel(batch_data, params, batch_num)
                elif file_type == 'pdf':
                    file_path, download_dir = self.export_log_data_to_pdf(batch_data, params, batch_num)
                elif file_type == 'csv':
                    file_path, download_dir = self.export_log_data_to_csv(batch_data, params, batch_num)
                all_file_paths.append(file_path)
                batch_num += 1
            if len(all_file_paths) > 1:
                zip_filename = f"{export_name}_{time_stamp}.zip"
                zip_path = os.path.join(download_dir, zip_filename)
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_paths in all_file_paths:
                        arcname = os.path.basename(file_paths)
                        zipf.write(file_paths, arcname)
                file_to_upload = zip_path
                is_zip = True
                file_size = os.path.getsize(zip_path)
            else:
                file_to_upload = all_file_paths[0]
                file_size = os.path.getsize(file_to_upload)
            fstore = getFilestore()
            if file_type == 'excel':
                destination_path = os.sep.join([organization_id, "log_export", "XLSX"])
            elif file_type == 'pdf':
                destination_path = os.sep.join([organization_id, "log_export", "PDF"])
            else:
                destination_path = os.sep.join([organization_id, "log_export", "CSV"])
            upload_name = os.path.basename(file_to_upload)
            download_path = fstore.save(file_to_upload, destination_path, upload_name)
            # Cleanup temp files
            try:
                for path in all_file_paths:
                    os.remove(path)
                if is_zip:
                    os.remove(file_to_upload)
            except Exception as cleanup_err:
                logger.warning(f"File cleanup error: {cleanup_err}")
            if export_id:
                export_config_obj = ExportConfig.objects.filter(export_id = export_id, organization = organization_id).first()
                if export_config_obj:
                    export_config_obj.is_processed = True
                    status = 2
                    export_config_obj.status = status
                    export_config_obj.last_update_time = datetime.now()
                    export_config_obj.file_size = self.format_size(file_size)
                    export_config_obj.file_path = 'media/dest_path/' + destination_path + '/' + upload_name
                    export_config_obj.save()
                else:
                    status = 3
                    logger.error("Export config data not found for export id %s" % export_id)
            else:
                status = 3
                logger.error("Export id not found for export config data") 
            logger.info("Exit from export_log_data function on LogIntegrationController .")
        except Exception as err:
            status = 3
            logger.error("Method export_log_data on LogIntegrationController :%s (%s)" % (
                err, type(err)))
        if params.get('export_id',''):
            ExportConfig.objects.filter(export_id = params.get('export_id',''), organization = organization_id).update(status=status)           

    def convert_relative_time_to_readable(self, start_time, end_time, timezone_str='UTC'):
        """
        Converts relative time strings (e.g., 'now-15m') or ISO 8601 format into readable datetime format.
        Supports time zone conversion and outputs in '%Y-%m-%d %H:%M:%S' format.

        :param start_time: Relative start time (e.g., 'now-15m') or ISO 8601 format (e.g., '2024-08-23T06:30:00.000Z')
        :param end_time: Relative end time (e.g., 'now') or ISO 8601 format (e.g., '2024-08-23T07:30:00.000Z')
        :param timezone_str: Time zone string (e.g., 'America/New_York', 'UTC')
        :return: Tuple containing readable start and end times in '%Y-%m-%d %H:%M:%S' format
        """
        # Initialize the time zone object
        timezone = pytz.timezone(timezone_str)
        
        # Get the current time in the specified time zone
        now = datetime.now(timezone)
        
        def is_iso8601_format(time_str):
            try:
                # Try to parse the string as ISO 8601 format
                datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                return True
            except ValueError:
                return False
        
        def parse_relative_time(time_str):
            if time_str == 'now':
                return now
            elif time_str == 'now/d':
                # Start of the current day
                return now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif time_str == 'now/w':
                # Start of the current week (assuming week starts on Monday)
                start_of_week = now - timedelta(days=now.weekday())
                return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            elif time_str.startswith('now-'):
                # Handling cases like 'now-24h/h' or 'now-90d/d'
                if '/h' in time_str:
                    delta, _ = time_str.split('/h')
                    hours = int(delta[4:-1])  # Extract number of hours
                    start_time = now - timedelta(hours=hours)
                    return start_time.replace(minute=0, second=0, microsecond=0)  # Start of the hour
                elif '/d' in time_str:
                    delta, _ = time_str.split('/d')
                    days = int(delta[4:-1])  # Extract number of days
                    start_time = now - timedelta(days=days)
                    return start_time.replace(hour=0, minute=0, second=0, microsecond=0)  # Start of the day
                else:
                    # Extract the time delta part (e.g., '15m', '24h', '90d')
                    delta = time_str[4:]
                    if delta.endswith('m'):
                        minutes = int(delta[:-1])
                        return now - timedelta(minutes=minutes)
                    elif delta.endswith('h'):
                        hours = int(delta[:-1])
                        return now - timedelta(hours=hours)
                    elif delta.endswith('d'):
                        days = int(delta[:-1])
                        return now - timedelta(days=days)
            return None
        # Convert start_time
        if is_iso8601_format(start_time):
            readable_start_time = datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S.%fZ')
            readable_start_time = readable_start_time.astimezone(timezone).strftime('%Y-%m-%d %H:%M:%S')
        else:
            readable_start_time = parse_relative_time(start_time)
            readable_start_time = readable_start_time.strftime('%Y-%m-%d %H:%M:%S')
        # Convert end_time
        if is_iso8601_format(end_time):
            readable_end_time = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S.%fZ')
            readable_end_time = readable_end_time.astimezone(timezone).strftime('%Y-%m-%d %H:%M:%S')
        else:
            readable_end_time = parse_relative_time(end_time)
            readable_end_time = readable_end_time.strftime('%Y-%m-%d %H:%M:%S')
        return readable_start_time, readable_end_time
            
    def is_valid_export(self,params):
        """
        function to check valid export
        :params: params
        """
        try:
            logger.info("Enter into is_valid_export function on LogIntegrationController.")
            index = params.get('index')
            filter_query = params.get('filter_query')
            file_type = params.get('type')
            log_count = self.elasticObj.get_elasticsearch_data(index,filter_query,from_download=1,is_count=True)
            if log_count == 0:
                return False,{"status":"failure","message": "Error : No data found for the given filter"}
            if file_type == 'pdf':
                if len(params.get('selected_columns',[])) > PDF_COLUMN_LIMIT:
                    return False,{"status":"failure","message": "Error :Number of column's is greater than %s. Export using CSV"%PDF_COLUMN_LIMIT}
                elif log_count > PDF_ROW_LIMIT:
                    return False, {"status":"failure","message": "Error :Number of rows is greater than %s. Export using CSV"%PDF_ROW_LIMIT}
            return True,{"status":"success","message": "Forwarding to queue"}
        except Exception as err:
            logger.error("Method is_valid_export on LogIntegrationController :%s (%s)" % (
                err, type(err)))
            
    def export_log_data_to_excel(self, data, params, batch_num=0):
        """
        function to export log data to excel
        :data: data
        :params: params
        """
        file_path = ''
        download_dir = ''
        try:
            logger.info("Enter into export_log_data_to_excel function on LogIntegrationController.")
            organization_id = params.get('organization_id')
            title = ('Name', params.get('name',''))
            user_details = params.get('user_details',{})
            user_tz = user_details.get('user_tz','UTC')
            tzone = pytz.timezone(user_tz)
            user_current_time = datetime.now(tzone)
            creation_time = ('Creation Time', format_datetime(user_current_time,
                                                                format=get_setting_data("DISPLAY_DATE_TIME_FORMAT")))
            report_duration = params.get('readable_start_time','')+ ' - '+params.get('readable_end_time','')
            report_duration = ('Duration', report_duration)
            titles = [title, creation_time, report_duration]
            
            download_dir = os.sep.join([get_settings("FILE_DOWNLOAD_URL"), organization_id, "log_export"])
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
            request = dict_to_obj({'user': {'id': params.get('user_id')}})
            configured_logo_path = self.get_logo_path(request, organization_id)
            if configured_logo_path:
                config_relative_logo_path = os.sep.join(str(configured_logo_path).split("media/")[1].split("/"))
                logo_path = os.sep.join([get_settings("SITE_ROOT"), "infraon","media", config_relative_logo_path])
            else:
                base_logo_path = os.sep.join(
                                [get_settings("SITE_ROOT"), "infraon", "media", "images", "oem", "infraon_logo_new.png"])
                logo_path = base_logo_path
            logo_path = prepare_logo_for_excel(logo_path, target_height=96)
            unique_keys = {key for d in data for key in d}
            headers = sorted(list(unique_keys))
            headerMap = {key: key for key in headers}
            start_ts = data[0]['@timestamp']
            end_ts = data[-1]['@timestamp']
            start_fmt = datetime.strptime(start_ts, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d-%H-%M-%S")
            end_fmt = datetime.strptime(end_ts, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d-%H-%M-%S")
            chunk_file_name = f"{start_fmt}_to_{end_fmt}"
            chunk_filename = f"{chunk_file_name}_part_{batch_num + 1}.xlsx"
            file_path = page_data_to_xlsx(
                headers, headerMap, data,
                chunk_filename, titles=titles,
                logo_file_path=logo_path, download_dir=download_dir
            )
            if file_path:
                return file_path, download_dir 
        except Exception as err:
            logger.error("Method export_log_data_to_excel on LogIntegrationController :%s (%s)" % (
                err, type(err)))
            return file_path, download_dir
            
    def export_log_data_to_csv(self, data, params, batch_num=0):
        """
        function to export log data to csv
        :data: data
        :params: params
        """
        file_path = ''
        download_dir = ''
        try:
            logger.info("Enter into export_log_data_to_csv function on LogIntegrationController.")
            organization_id = params.get('organization_id')
            title = []
            title.append(['Name', params.get('name','')])
            user_details = params.get('user_details',{})
            user_tz = user_details.get('user_tz','UTC')
            tzone = pytz.timezone(user_tz)
            user_current_time = datetime.now(tzone)
            title.append(['Generation Time', str(user_current_time.strftime("%Y-%m-%d %H:%M:%S"))])
            report_duration = params.get('readable_start_time','')+ ' - '+params.get('readable_end_time','')
            title.append(['Report Duration', report_duration])
            download_dir = os.sep.join([get_settings("FILE_DOWNLOAD_URL"), organization_id, "log_export"])
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
            unique_keys = {key for d in data for key in d}
            headers = sorted(list(unique_keys))
            headerMap = {key: key for key in headers}
            start_ts = data[0]['@timestamp']
            end_ts = data[-1]['@timestamp']
            start_fmt = datetime.strptime(start_ts, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d-%H-%M-%S")
            end_fmt = datetime.strptime(end_ts, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d-%H-%M-%S")
            chunk_file_name = f"{start_fmt}_to_{end_fmt}"
            chunk_filename = f"{chunk_file_name}_part_{batch_num + 1}.csv"
            file_path = log_data_to_csv(headers, headerMap, data, chunk_filename, download_dir=download_dir, title=title)
            if file_path:
                return file_path, download_dir 
        except Exception as err:
            logger.error("Method export_log_data_to_csv on LogIntegrationController :%s (%s)" % (
                err, type(err)))
            return file_path, download_dir   
            
    def export_log_data_to_pdf(self, data_list, params, batch_num=0):
        """
        function to export log data to pdf
        :data: data
        :params: params
        """
        pdf_path = ''
        download_dir = ''
        try:
            logger.info("Enter into export_log_data_to_pdf function on LogIntegrationController.")
            organization_id = params.get('organization_id')
            download_dir = os.sep.join([get_settings("FILE_DOWNLOAD_URL"), organization_id, "log_export"])
            if not os.path.exists(download_dir):
                os.makedirs(download_dir)
            request = dict_to_obj({'user': {'id': params.get('user_id')}})
            configured_logo_path = self.get_logo_path(request, organization_id)
            if configured_logo_path:
                config_relative_logo_path = os.sep.join(str(configured_logo_path).split("media/")[1].split("/"))
                logo_path = os.sep.join([get_settings("SITE_ROOT"), "infraon","media", config_relative_logo_path])
            else:
                base_logo_path = os.sep.join(
                                [get_settings("SITE_ROOT"), "infraon", "media", "images", "oem", "infraon_logo_new.png"])
                logo_path = base_logo_path
                
            logo_path = prepare_logo_for_excel(logo_path, target_height=96)
            user_details = params.get('user_details',{})
            user_tz = user_details.get('user_tz','UTC')
            tzone = pytz.timezone(user_tz)
            user_current_time = datetime.now(tzone)
            report_duration = params.get('readable_start_time','')+ ' - '+params.get('readable_end_time','')
            generated_by = user_details.get('full_name','')
            generated_time = str(user_current_time.strftime("%Y-%m-%d %H:%M:%S"))
            start_ts = data_list[0]['@timestamp']
            end_ts = data_list[-1]['@timestamp']
            start_fmt = datetime.strptime(start_ts, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d-%H-%M-%S")
            end_fmt = datetime.strptime(end_ts, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d-%H-%M-%S")
            chunk_file_name = f"{start_fmt}_to_{end_fmt}"
            chunk_filename = f"{chunk_file_name}_part_{batch_num + 1}.pdf"
            pdf_path = generateDataToPDF(data_list, download_dir, chunk_filename, logo_path, generated_by, report_duration, generated_time)
            if pdf_path:
                return pdf_path, download_dir
            logger.info("Exit from export_log_data_to_pdf function on LogIntegrationController.")
        except Exception as err:
            logger.error("Method export_log_data_to_pdf on LogIntegrationController :%s (%s)" % (
                err, type(err)))
            return pdf_path, download_dir            

    def get_logo_path(self, request, organization_id):
        logo = ""
        try:
            is_msp_org = self.is_msp_org(request, organization_id)
            if is_msp_org:
                user_type = self.get_customer_entity_filter_condition(request, return_dict=True)
                if user_type.get('customer_id'):
                    logo = self.get_msp_customer_supported_data(request, organization_id, user_type.get('customer_id'),
                                                                "", "logo_path")
            if not logo:
                try:
                    config_obj = OrganizationalConfig.objects.get(organization=organization_id,
                                                                  config_type='getstarted')
                    serializer = OrganizationalConfigSerializer(config_obj)
                    data = serializer.data
                    page_branding = data.get('config', {}).get("branding", {})
                    logo = page_branding.get("logo_path", "")
                except Exception as r:
                    logo = ""
            if logo:
                if "dest_path" in logo:
                    logo = logo.replace("\\", os.sep).replace("/", os.sep)  # if the platform changes the os.sep also will change
                    local_file_path = getFilestore().download_to_local(logo, return_local_file_path=True)
                    return local_file_path.replace(os.sep, "/")
                else:
                    return logo.replace(os.sep, "/")
        except Exception as e:
            print_traceback()
            logger.exception("Expection occerred : get_logo_path")
            return None
            
    def format_size(self, bytes):
        if bytes < 1024:
            return f"{bytes} bytes"
        elif bytes < 1024**2:
            return f"{bytes / 1024:.2f} KB"
        elif bytes < 1024**3:
            return f"{bytes / 1024**2:.2f} MB"
        else:
            return f"{bytes / 1024**3:.2f} GB"

    def convert_to_elasticsearch_filter(self, filters, start_time, end_time):
        try:
            filter_query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "range": {
                                    "@timestamp": {
                                        "gte": start_time,
                                        "lte": end_time,
                                        "format": "strict_date_optional_time||epoch_millis"
                                    }
                                }
                            }
                        ]
                    }
                }
            }

            for filter_item in filters:
                # Skip disabled filters
                if filter_item.get('meta', {}).get('disabled', False):
                    continue

                # Handle negation (if 'negate' is True, use 'must_not' instead of 'must')
                negate = filter_item.get('meta', {}).get('negate', False)

                # Extract the actual query part
                query_part = filter_item.get('query', {})
                
                if negate:
                    if "must_not" not in filter_query['query']['bool']:
                        filter_query['query']['bool']["must_not"] = []
                    filter_query['query']['bool']["must_not"].append(query_part)
                else:
                    filter_query['query']['bool']["must"].append(query_part)

            return filter_query
        except Exception as err:
            logger.error("Method convert_to_elasticsearch_filter on LogIntegrationController: %s (%s)" % (
                err, type(err)))
            return {}

    
    def validate_logmgmt_data(self, queue_params):
        """
        function to validate log management data
        :queue_params: queue params
        :return: valid data true/false
        """
        valid_data = False
        try:
            logger.info("Enter into validate_logmgmt_data function on LogIntegrationController.")
            if queue_params.get('sync_type') == 'role' and queue_params.get('role_data').get('group_id'):
                result_page = GroupProfile.objects.filter(group_id=queue_params.get('role_data').get('group_id'))
                serializer = GroupSerializer(result_page, many=True)
                group_data = serializer.data
                if group_data:
                    if group_data[0]['last_update_time'] == queue_params.get('role_data').get('last_update_time'):
                        valid_data = True
            if queue_params.get('sync_type') == 'user' and queue_params.get('user_data').get('user'):
                user_profile_obj = UserProfile.objects.filter(user=queue_params.get('user_data').get('user'))
                user_profile_ser = UserProfileSerializer(user_profile_obj, many=True)
                user_profile_data = user_profile_ser.data
                if user_profile_data:
                    if user_profile_data[0].get('last_update_time') == queue_params.get('user_data').get('last_update_time'):
                        valid_data = True
            if queue_params.get('sync_type') == 'rule' and queue_params.get('rule_data').get('rule_id'):
                rule_obj = CorrelationRules.objects.filter(rule_id=queue_params.get('rule_data').get('rule_id'))
                rule_ser = CorrelationRuleSerializer(rule_obj, many=True)
                rule_data = rule_ser.data
                if rule_data:
                    db_date = rule_data[0].get('last_update_time')
                    param_date = queue_params.get('rule_data').get('last_update_time')
                    if db_date in self.noneList and param_date in self.noneList:
                        if db_date == param_date and queue_params.get('request_type') == 'POST':
                            valid_data = True
                    elif db_date[:-4] == param_date[:-4]:
                        if rule_data[0].get('log_rule_id') not in self.noneList and queue_params.get('request_type') == 'PUT':
                            valid_data = True
                        else:
                            valid_data = True
                            queue_params['request_type'] = 'POST'
                            if queue_params.get('copy_data'):
                                queue_params['data'] = queue_params.get('copy_data')
                    else:
                        valid_data = False
            logger.info("Exit into validate_logmgmt_data function on LogIntegrationController.")
        except Exception as exception:
            logger.error("Method validate_logmgmt_data in LogIntegrationController: exception %s - %s" % (exception, type(exception)))
        return valid_data
    
    def send_logmgmt_data_to_queue(self, celery_params):
        """
        function to send log management data to queue
        :celery_params: celery params
        :return: true/false
        """
        try:
            sync_type = celery_params.get('sync_type')
            organization_id = celery_params.get('organization_id')
            if celery_params.get('retry') in self.noneList:
                celery_params['retry'] = 0
                delay_seconds = 5
            else:
                delay_seconds = 300
            task_name = 'app.logmanagement.log_integration.tasks.start_logmanagement_sync'
            default_exchange_options = {
                "exchange_name": "LogmanagementSyncDelay",
                "exchange_type": "x-delayed-message",
                "args": {"x-delayed-type": "direct"}
            }
            exchange = get_setting_data("LOG_MGMT_DELAY_EXCHANGE_OPTIONS", default_exchange_options)
            out = self.queueObj.send_data(celery_params, "sync_logmanagement_data", task_name, 
                        exchange = exchange,
                        msg_properties = {"headers": {"x-delay": delay_seconds * 1000}}
                    )
            if out:
                logger.info("Sending log management data to queue - %s (%s) -> next action in %s seconds" % (organization_id, delay_seconds, sync_type))
            else:
                logger.error("Log management data to queue failed - %s (%s)." % (organization_id, sync_type))
            return out
        except Exception as e:
                logger.exception("Error sending log management data - %s (%s)" % (organization_id, sync_type))
        return False
        
    def save_logmgmt_rule(self, request,event, log_data, input_filters={}):
        """
        Function to save log management rule
        :param event:add/edit event
        :param log_data: log rule data
        :param input_filters:
        :return : response data
        """
        celery_params = {}
        try:
            logger.info(
                "Enter into save_logmgmt_rule function on LogIntegrationController.")
            url = get_settings("LOG_MGMT_RULE_URL")
            organization_id = self.get_organization_id(request)
            if organization_id in self.noneList:
                organization_id = request
            space_url = f"/s/infraon_{organization_id}/api"
            url = url.replace("/api", space_url, 1)
            if event == "Add":
                request_type = "POST"
            else:
                request_type = "PUT"
                url = f"{url}/{log_data.log_rule_id}"
            rule_name =  log_data.name
            rule_status =  log_data.is_enabled
            data_view_id = ""
            if log_data.rule_data.get('data_view'):
                data_view_id = log_data.rule_data.get('data_view')
            index_patterns = []
            if log_data.rule_data.get('index_pattern'):
                for pattern in log_data.rule_data.get('index_pattern'):
                    index_patterns.append(pattern.get('name'))
            rule_type_id = LOG_MGMT_RULE_EVENT_DICT.get(log_data.rule_type, log_data.rule_type)
            log_rule_type = LOG_MGMT_RULE_QUERY_DICT.get(log_data.rule_type, log_data.rule_type)
            custom_query = ""
            if log_data.rule_data.get('custom_filter'):
                if "organization.keyword" in log_data.rule_data.get('custom_filter'):
                    custom_query = log_data.rule_data.get('custom_filter')
                else:
                    custom_query = 'event.organization.keyword : "%s" AND '%(organization_id)
                    custom_query += log_data.rule_data.get('custom_filter')
            elif log_data.rule_data.get('esql_filter'):
                esql_filter = log_data.rule_data.get('esql_filter')
                custom_query = self.update_esql_filter(esql_filter,organization_id)
            connectors = self.get_action_connectors(request)
            actions = []
            if connectors:
                actions = [
                            {
                                "group": "default",
                                "id": connectors.get('id'),
                                "params": {
                                    "documents": [
                                        {
                                            "rule_name": "{{context.rule.name}}",
                                            "message": "{{alerts.all.data}}",
                                            "alarm_msg": log_data.action.get('event_message')
                                        }
                                    ]
                                },
                                "frequency": {
                                    "summary": True,
                                    "throttle": None,
                                    "notify_when": "onActiveAlert"
                                }
                            }
                        ]
            # if input_filters:
            #     output_filters = self.get_rule_filter(input_filters, trigger_data)
            meta = {}
            seconds = ""
            if log_data.action.get('severity'):
                severity = LOG_MGMT_SEVERITY_DICT.get(log_data.action.get('severity'))
            else:
                severity = "low"
            if log_data.rule_data.get('log_look_back'):
                meta['from'] = log_data.rule_data.get('log_look_back')
                if log_data.rule_data.get('log_look_back')[-1] == 'm':
                    seconds = "now-" + str(int(log_data.rule_data.get('log_look_back')[:-1]) * 60  + 60) + "s"
                else: 
                    seconds = "now-" + str(int(log_data.rule_data.get('log_look_back')[:-1]) * 60 * 60 + 60) + "s"
            if log_data.description:
                description = log_data.description
            else:
                description = rule_name
            if log_rule_type in ['esql']:
                language = 'esql'
            else:
                language = 'kuery'
            index_patterns=[i+"*" for i in index_patterns]
            data = {"params": { "author": [], "description": description, "falsePositives": [], 
                                "ruleId": "", "immutable": False, "license": "", "outputIndex": "", 
                                "maxSignals": 100, "riskScore": 21, "riskScoreMapping": [], "severity": severity, 
                                "severityMapping": [], "threat": [], "to": "now", "references": [], "version": 1, 
                                "exceptionsList": [], "relatedIntegrations": [], "requiredFields": [], 
                                "setup": "", "type": log_rule_type, "language": language, "query": custom_query, 
                                "filters": [], "meta": meta, "from": seconds, "index": index_patterns,
                                "dataViewId": data_view_id}, 
                    "consumer": "siem",
                    "rule_type_id": rule_type_id, 
                    "schedule": { "interval": log_data.rule_data.get('log_check_every') }, 
                    "actions": actions, 
                    "tags": [], 
                    "notify_when": None, 
                    "name": rule_name, 
                    "enabled": rule_status }
            if log_data.rule_type == 'threshold':
                if log_data.rule_data.get('threshold'):
                    data['params']['threshold'] = {"field": log_data.rule_data.get('group_by'), "value": log_data.rule_data.get('threshold'), "cardinality": []}
                    if log_data.rule_data.get('group_by'):
                        group_by = ['event.organization.keyword']
                        is_msp_org = self.is_msp_org(request, organization_id)
                        if is_msp_org:
                            user_type = self.get_customer_entity_filter_condition(request, return_dict=True)
                            if user_type.get('customer_id'):
                                group_by.append('event.customer_id.keyword')
                            if user_type.get('customer_entity_id'):
                                group_by.append('event.customer_entity_id.keyword')
                        for group_by_field in log_data.rule_data.get('group_by'):
                            group_by.append(LOG_MGMT_FILTER_OPTION_DICT.get(group_by_field))
                        data['params']['threshold']['field'] = group_by
                if log_data.rule_data.get('log_count'):
                    data['params']['threshold']['cardinality'] = [{
                    "field": LOG_MGMT_FILTER_OPTION_DICT.get(log_data.rule_data.get('log_count')),
                    "value": log_data.rule_data.get('unique_value')
                    }]
            copy_data = copy.deepcopy(data)
            if request_type == "PUT":
                del data['consumer']
                del data['rule_type_id']
                del data['enabled']
                celery_params['copy_data'] = copy_data
            celery_params['request_type'] = request_type
            celery_params['data'] = data
            celery_params['url'] = url
            logger.info(
                "Exit from save_logmgmt_rule function on LogIntegrationController .")
            return celery_params
        except Exception as err:
            logger.error("Method save_logmgmt_rule on LogIntegrationController :%s (%s)" % (
                err, type(err)))
            return celery_params
        
    def get_action_connectors(self,request):
        """
        Function to get connectors, if no connectors it will create new connector.
        :return : response data
        """
        response_data = []
        request_data = {}
        connector_data = {}
        try:
            organization_id = self.get_organization_id(request)
            if organization_id in self.noneList:
                organization_id = request
            url = get_settings("LOG_MGMT_CONNECTORS_URL")
            space_url = f"/s/infraon_{organization_id}/api"
            url = url.replace("/api", space_url, 1)
            request_type = "GET"
            response_data = self.sync_log_management_data(request_type, request_data, url)
            connectors_list = json.loads(response_data.get('data').decode('utf-8'))
            if connectors_list:
                connectors = [item for item in connectors_list if item['name'] == 'Log_Alerts']
                if connectors:
                    connector_data = connectors[0]
                else:
                    response_data = self.save_connectors(request)
                    if response_data.get('ok'):
                        self.get_action_connectors(request)
            else:
                response_data = self.save_connectors(request)
                if response_data.get('ok'):
                    self.get_action_connectors(request)
            logger.info(
                "Exit from get_action_connectors function on LogIntegrationController .")
            return connector_data
        except Exception as err:
            response_data = {'ok': False, 'reason': 'Data Error', 'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR}
            logger.error("Method get_action_connectors on LogIntegrationController :%s (%s)" % (
                err, type(err)))
            return response_data
        
    def update_rule_data(self, response_data, queue_params):
        """
        Function update rule data after saving in third party tool
        :return : response data
        """
        try:
            logger.info(
                "Enter into update_rule_data function on LogIntegrationController.")
            correlation_rule_model = CorrelationRules.objects.get(organization=queue_params.get('rule_data').get("organization"), rule_id=queue_params.get('rule_data').get("rule_id"), is_deleted=False)
            if correlation_rule_model not in self.noneList:
                correlation_rule_model.log_rule_id = json.loads(response_data.get('data').decode('utf-8')).get('id')
                correlation_rule_model.save()
            logger.info(
                "Exit from update_rule_data function on LogIntegrationController .")
        except Exception as err:
            logger.error("Method update_rule_data on LogIntegrationController :%s (%s)" % (
                err, type(err)))

    def delete_correlation_rule_data(self,request, rule_id):
        """
        function to delete correlation rule
        :role_data: role data
        :return: response data
        """
        celery_params = {}
        try:
            logger.info("Enter into delete_correlation_rule_data function on LogIntegrationController.")
            rule_url = get_settings("LOG_MGMT_RULE_URL")
            organization_id = self.get_organization_id(request)
            if organization_id in self.noneList:
                organization_id = request
            space_url = f"/s/infraon_{organization_id}/api"
            rule_url = rule_url.replace("/api", space_url, 1)
            url = f"{rule_url}/{rule_id}"
            request_type = "DELETE"
            celery_params['request_type'] = request_type
            celery_params['data'] = {}
            celery_params['url'] = url
            logger.info("Exit into delete_correlation_rule_data function on LogIntegrationController.")
        except Exception as exception:
            logger.error("Method delete_correlation_rule_data in LogIntegrationController: exception %s - %s" % (exception, type(exception)))
        return celery_params
    
    def update_log_rule_status(self, request,rule_data):
        """
        Function to update log rule status Enable/Disable
        :param rule_data: Rule data
        return: log user data
        """
        celery_params = {}
        try:
            logger.info("Enter into update_log_rule_status function on LogIntegrationController.")
            if rule_data.is_enabled:
                status = '_enable'
            else:
                status = '_disable'
            rule_url = get_settings("LOG_MGMT_RULE_URL")
            organization_id = self.get_organization_id(request)
            if organization_id in self.noneList:
                organization_id = request
            space_url = f"/s/infraon_{organization_id}/api"
            rule_url = rule_url.replace("/api", space_url, 1)
            url = f"{rule_url}/{rule_data.log_rule_id}/{status}"
            celery_params['request_type'] = "POST"
            celery_params['data'] = {}
            celery_params['url'] = url
            logger.info("Exit from update_log_rule_status on LogIntegrationController")
        except Exception as e:
            logger.error("Method update_log_rule_status on LogIntegrationController:%s (%s)" % (e, type(e)))
        return celery_params

    def get_export_list(self, request):
        """
        Function used for get the export list with pagination
        :param request:object received on web server.
        :return : list of Export Configs.
        """
        try: 
            logger.info("Enter into get_export_list function on LogIntegrationController.")
            logger.debug("Dta on get_export_list function request:%s" % (request))
            paginator = StandardResultsSetPagination()
            request_data = self.get_query_params_data(request)
            user_tz = request_data.get("user_tz", "UTC")
            search_filter = request_data.get("filter", [])
            export_configs_search_str = request_data.get("export_configs_search_str")
            search_filter_Q = Q()
            user_id = request.user.id
            user_filter_Q = Q(user_details__user_id=user_id)
            if len(search_filter) > 2:
                search_filter_Q = self.get_page_filtered_data(request)
            organization_id = self.get_organization_id(request)
            logger.debug("Data on get_export_list function organization_id:%s" % (organization_id))
            init_filter_condition = Q(organization=organization_id) & search_filter_Q  & user_filter_Q & Q(type__ne='Inventory')
            if export_configs_search_str:
                init_filter_condition = init_filter_condition & (Q(name__contains=export_configs_search_str) |
                Q(description__contains=export_configs_search_str) |Q(type__contains=export_configs_search_str) | 
                Q(file_type__contains=export_configs_search_str))
            logger.debug("Data on get_export_list function init_filter_condition:%s" % init_filter_condition)
            logger.debug("Data on get_export_list function organization_id:%s" % (organization_id))
            filter_options = {}
            result_page = paginator.paginate_queryset(self.get_model_filter(request, ExportConfig, init_filter_condition), request)
            serializer = ExportConfigsListSerializer(result_page, many=True)
            export_configs_list = serializer.data
            for export_config in export_configs_list:
                creation_time = datetime.strptime(export_config.get('creation_time'), '%Y-%m-%dT%H:%M:%S.%fZ')
                export_config['creation_time'] = format_utc_datetime(creation_time, user_tz, DISPLAY_DATE_TIME_FORMAT)
                export_config['disable_download'] = False if export_config.get('status') == 2 and export_config.get('type') == 'Log export' else True
                export_config['disable_info'] = False if export_config.get('type') == 'Log Pipeline' else True
            param={}
            param['module_id'] = 81
            param['option_type'] = 1
            options = self.get_system_option_for_macro_language(request, param)
            filter_options=options[0].get("data")[0]
            export_configs_list = {
                "export_configs": export_configs_list,
                "filter_options": filter_options
            }
            logger.info("Data on get_export_list function options:%s" % (options))
            response_data = paginator.get_paginated_response(export_configs_list)
            logger.info("Exit from get_export_list function on LogIntegrationController.")
            return response_data
        except Exception as err:
            logger.error(
                "Method get_export_list on LogIntegrationController:%s (%s)" % (err, type(err)))
            return Response(self.get_return_object("error", {}, "Error.err_fail"),
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def save_connectors(self,request):
        """
        Function to save connector
        return: response data
        """
        response_data = {}
        try:
            logger.info("Enter into save_connector function on LogIntegrationController.")
            connector_url = get_settings("LOG_MGMT_CONNECTORS_URL")
            organization_id = self.get_organization_id(request)
            if organization_id in self.noneList:
                organization_id = request
            space_url = f"/s/infraon_{organization_id}/api"
            connector_url = connector_url.replace("/api", space_url, 1)
            url = connector_url[:-1]
            request_type = "POST"
            request_data = {
                                "name": "Log_Alerts",
                                "config": {
                                    "index": "log_alerts",
                                    "refresh": False,
                                    "executionTimeField": None
                                },
                                "connector_type_id": ".index"
                            }
            response_data = self.sync_log_management_data(request_type, request_data, url)
            logger.info("Exit from save_connector on LogIntegrationController")
        except Exception as e:
            logger.error("Method save_connector on LogIntegrationController:%s (%s)" % (e, type(e)))
        return response_data
        
    def get_spaces(self, group_name, username, organization_id=''):
        """
        Function to get space, if no space it will create new space.
        :group_name: group name
        :user_dict: user data
        :return : response data
        """
        response_data = []
        request_data = {}
        role_space_id = ''
        try:
            logger.info(
                "Enter into get_spaces function on LogIntegrationController.")
            # temp_space_id = group_name.lower().replace(" ", "_")+"_"+ username.replace('@@@', '_')
            # pattern = r'[^a-z0-9_-]'/
            # space_id = re.sub(pattern, '', temp_space_id)
            if organization_id:
                space_id = "infraon_" + organization_id
                space_url = get_settings("LOG_MGMT_SPACE_URL")
                url = f"{space_url}/{space_id}"
                request_type = "GET"
                response_data = self.sync_log_management_data(request_type, request_data, url)
                if response_data.get('ok'):
                    space_data = json.loads(response_data.get('data').decode('utf-8'))
                    if space_data:
                        role_space_id = space_id
                else:
                    response_data = self.save_space(space_id)
                    if response_data.get('ok'):
                        role_space_id = json.loads(response_data.get('data').decode('utf-8')).get('id')
                logger.info(
                    "Exit from get_spaces function on LogIntegrationController .")
                return role_space_id
        except Exception as err:
            response_data = {'ok': False, 'reason': 'Data Error', 'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR}
            logger.error("Method get_spaces on LogIntegrationController :%s (%s)" % (
                err, type(err)))
            return response_data
        
    def save_space(self, space_id):
        """
        Function to save space
        return: response data
        """
        response_data = {}
        try:
            logger.info("Enter into save_space function on LogIntegrationController.")
            url = get_settings("LOG_MGMT_SPACE_URL")
            request_type = "POST"
            request_data = {
                                "id": space_id,
                                "name": space_id,
                                "description" : "This is the "+ space_id +" Space",
                                "disabledFeatures": []
                            }
            response_data = self.sync_log_management_data(request_type, request_data, url)
            logger.info("Exit from save_space on LogIntegrationController")
        except Exception as e:
            logger.error("Method save_space on LogIntegrationController:%s (%s)" % (e, type(e)))
        return response_data
    

    def delete_logmgmt_space(self, role_data, username):
        """
        function to delete log management space
        :role_data: role data
        :return: response data
        """
        request_data = {}
        try:
            logger.info("Enter into delete_logmgmt_space function on LogIntegrationController.")
            space_url = get_settings("LOG_MGMT_SPACE_URL")
            temp_space_id = role_data.lower().replace(" ", "_")+"_"+ username.replace('@@@', '_')
            pattern = r'[^a-z0-9_-]'
            space_id = re.sub(pattern, '', temp_space_id)
            url = f"{space_url}/{space_id}"
            request_type = "DELETE"
            response_data = self.sync_log_management_data(request_type, request_data, url)
            logger.info("Exit into delete_logmgmt_space function on LogIntegrationController.")
        except Exception as exception:
            response_data = {'ok': False, 'reason': 'Data Error', 'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR}
            logger.error("Method delete_logmgmt_space in LogIntegrationController: exception %s - %s" % (exception, type(exception)))
        return response_data


    def sync_asset_from_log(self,params):
        """
        Function to sync asset from log
        return: response data
        """
        try:
            logger.info("Enter into sync_asset_from_log function on LogIntegrationController.")
            cmdb_ctrl = CMDBController()
            organization = params.get("organization","")
            ip_data = self.get_ip_list_from_elastic(params)
            ip_list_data = [{
                'ip'    :   data.get("ip",""),
                'customer_id' : data.get('log_entry',{}).get('event',{}).get("customer_id",""),
                'customer_entity_id' : data.get('log_entry',{}).get('event',{}).get("customer_event_id",""),
                } for data in ip_data]
            ip_list_data_classified = classify_objs(ip_list_data, lambda a: a.get("ip"))
            ip_list_elastic = list(ip_list_data_classified.keys())
            logger.info("IP List from elasticserach in sync_asset_from_log function on LogIntegrationController: %s" % (ip_list_elastic))
            ip_list_mongo = set(CMDBCi.objects.filter(organization=organization,is_deleted=False,object_type='Node').values_list('ip_address'))
            ips_not_in_mongo = [ip for ip in ip_list_elastic if ip not in ip_list_mongo]
            ips_with_syslog_enabled = set(CMDBCi.objects.filter(organization=organization,is_deleted=False,is_logmanagement_enabled=True,object_type='Node').values_list('ip_address'))
            ips_in_mongo = [ip for ip in ip_list_elastic if ip in ip_list_mongo and ip not in ips_with_syslog_enabled]
            if ips_not_in_mongo:
                for ip in ips_not_in_mongo:
                    asset_data = {}
                    asset_data["ci_name"] = "Log - %s" % (ip)
                    customer_id =   ip_list_data_classified.get(ip, {})[0].get("customer_id", "")
                    customer_entity_id  =   ip_list_data_classified.get(ip, {})[0].get("customer_entity_id", "")
                    log_entry = next((entry['log_entry'] for entry in ip_data if entry['ip'] == ip), None)
                    category_name, sub_category_name = self.get_category_name(log_entry)
                    if not category_name:
                        category_name = "Other"
                    if log_entry:
                        host = log_entry.get("host", {})
                        if host:
                            asset_data["host_name"] = host.get("name", "")
                            asset_data["ci_name"] = host.get("name", "")
                            os = host.get("os", {})
                            if os:
                                asset_data["os_name"] = os.get("name", "")
                                asset_data["os_version"] = os.get("version", "")
                    if not asset_data.get("ci_name"):
                        asset_data["ci_name"] = "Log Device - %s" % (ip)
                    asset_data["ip_address"] = ip
                    if customer_id not in self.noneList:
                        asset_data["customer_id"] = customer_id
                        if customer_entity_id not in self.noneList:
                            asset_data["customer_entity_id"] = customer_entity_id
                    asset_data["organization"] = organization
                    category_data = self.get_category_id(category_name, sub_category_name, organization)
                    asset_data["ci_category"] = category_data.get("category_id", "")
                    asset_data["ci_sub_category"] = category_data.get("sub_category_id", "")
                    asset_data["is_logmanagement_enabled"] = True
                    user_info = self.get_system_user_obj(organization)
                    options=cmdb_ctrl.get_default_options({}, organization_id=organization, current_event=None, filter_status=True,
                            request_data=asset_data, user_info=None, from_csv=False)
                    asset_data['lav_asset_type'] = "LOGMANAGEMENT"
                    asset_data['state'] = options.get('state', [])[0]
                    asset_data['status'] = options.get('status', [])[0]
                    asset_data['criticality'] = options.get('criticality', [])[-1]
                    asset_data['operational_status'] = options.get('operational_status', [])[0]
                    asset_data['service_status'] = options.get('service_status', [])[0]
                    asset_data['usage_type'] =  options.get('usage_type', [])[0]
                    comman_info = {
                        'prev_status' : {},
                        'maintenance_ids' : [],
                        'usage_type' : options.get('usage_type', [])[0],
                        "quantity": 0,
                        "re_order_quantity": 0,
                        "threshold_user_type": {},
                        "threshold_to": {},
                        "type": {},
                        "currency": {}
                    }
                    asset_data['common_info']= comman_info
                    cmdb_ctrl.add_cmdb_ci(request={}, add_asset_data=asset_data, organization_id=organization,
                                                    return_id=True, user=user_info)

            if ips_in_mongo:
                lav_obj = LavenderMonitor(organization)
                enabled_count = CMDBCi.objects.filter(organization=organization, is_deleted=False, is_logmanagement_enabled=True).count()
                log_device_count = lav_obj.check_logmanagement_count()
                if enabled_count < log_device_count:
                    for obj in CMDBCi.objects.filter(
                        organization=organization,
                        ip_address__in=ips_in_mongo,
                        is_deleted=False,
                        object_type='Node'
                    ):
                        serializers = CMDBCiSerializer(obj, many=False)
                        serializer_data = serializers.data
                        ip_address = serializer_data.get("ip_address", "")
                        asset_customer_id = serializer_data.get("customer_id", "")
                        asset_customer_entity_id = serializer_data.get("customer_entity_id", "")
                        customer_id = ip_list_data_classified.get(ip_address, {})[0].get("customer_id", asset_customer_id)
                        customer_entity_id = ip_list_data_classified.get(ip_address, {})[0].get("customer_entity_id", asset_customer_entity_id)
                        if customer_id not in self.noneList and asset_customer_id in self.noneList :
                            obj.customer_id = customer_id # if customer_id already exists, it will not overwrite
                            if customer_entity_id not in self.noneList and asset_customer_entity_id in self.noneList:
                                obj.customer_entity_id = customer_entity_id #if customer_entity_id already exists, it will not overwrite
                        obj.is_logmanagement_enabled = True  # Add the missing field
                        obj.save(update_fields=['is_logmanagement_enabled'])  # Ensure DB updates only the missing field
            is_queue_inserted = self.send_logmgmt_asset_sync_data_to_queue(params)
            if not is_queue_inserted:
                self.send_logmgmt_asset_sync_data_to_queue(params)
            logger.info("Exit from sync_asset_from_log on LogIntegrationController")
        except Exception as e:
            logger.error("Method sync_asset_from_log on LogIntegrationController:%s (%s)" % (e, type(e)))
            self.send_logmgmt_asset_sync_data_to_queue(params)
    

    def get_ip_list_from_elastic(self, params):
        """
        Function to get all IP's from elasticsearch and one log entry per IP
        return: unique IP's with one log entry
        """
        try:
            logger.info("Enter into get_ip_list_from_elastic function on LogIntegrationController.")
            es = self.elasticObj.get_elasticsearch_connection()
            organization = params.get("organization", "")
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

            query = {
                "size": 0,  # No need to return documents in the main query
                "query": {
                    "bool": {
                        "filter": [
                            {"range": {"@timestamp": {"gte": "now-60m/m"}}}, 
                            {"exists": {"field": "event.organization"}},
                            {"term": {"event.organization": organization}}
                        ]
                    }
                },
                "aggs": {
                    "unique_ips": {
                        "terms": {
                            "field": "host.ip.keyword",  # Aggregate by unique IPs
                            "size": 10000  # Max IPs to return
                        },
                        "aggs": {
                            "sample_log": {
                                "top_hits": {
                                    "size": 1,  # Only get one log entry for each IP
                                }
                            }
                        }
                    }
                }
            }

            response = es.search(index='*', body=query)
            ip_buckets = response['aggregations']['unique_ips']['buckets']

            unique_ips_with_logs = []
            if len(SUBNET_MASK_LIST) > 0:
                subnets = [ipaddress.ip_network(subnet) for subnet in SUBNET_MASK_LIST]
            else:
                subnets = []

            for bucket in ip_buckets:
                ip = bucket['key']
                ip_obj = ipaddress.ip_address(ip)
                
                # Check if the IP is in any of the subnets
                if subnets:
                    if any(ip_obj in subnet for subnet in subnets):
                        # Extract the log entry
                        log_entry = bucket['sample_log']['hits']['hits'][0]['_source']
                        unique_ips_with_logs.append({
                            "ip": ip,
                            "log_entry": log_entry
                        })
                else:
                        # Extract the log entry
                        log_entry = bucket['sample_log']['hits']['hits'][0]['_source']
                        unique_ips_with_logs.append({
                            "ip": ip,
                            "log_entry": log_entry
                        })

            logger.info("Exit from get_ip_list_from_elastic on LogIntegrationController")
            return unique_ips_with_logs
        except Exception as e:
            logger.error("Method get_ip_list_from_elastic on LogIntegrationController: %s (%s)" % (e, type(e)))
            return []
        
    def get_category_name(self, log_entry):
        """
        Function to get category name and sub_category name
        """
        category_name = ""
        sub_category_name = ""
        try:
            logger.debug("Enter into get_category_name of DiscoveryResultProcessor")
            if log_entry:
                host = log_entry.get("host", {})
                device_type = log_entry.get("type", "")
                if host:
                    os = host.get("os", {})
                    if os:
                        os_name = os.get("name", "")
                        type = os.get("type", "")
                        if os_name.lower().find("server") > -1:
                            category_name = "Server"
                            if type.lower().find("windows") > -1:
                                sub_category_name = "Windows Server"
                            else:
                                sub_category_name = "Linux Server"
                        else:
                            category_name = "Work Station"
                            sub_category_name = "Desktop"
                if device_type:
                    if device_type in ['firewall','switch','router']:
                        category_name = "Network"
                        if device_type == 'firewall':
                            sub_category_name = "Firewall"
                        elif device_type == 'switch':
                            sub_category_name = "Switch"
                        elif device_type == 'router':
                            sub_category_name = "Router"
            logger.debug("Exit from get_category_name of DiscoveryResultProcessor")
            return category_name, sub_category_name
        except Exception as e:
            logger.error("Method get_category_name of DiscoveryResultProcessor: %s (%s)" % (e, type(e)))
            return category_name, sub_category_name
        
    def get_category_id(self, category_name, sub_category_name="", org_id=None):
        """
        Function to get category id and sub_category_id.
        """
        cmdb_obj = {}
        try:
            logger.debug("Enter into get_category_id of DiscoveryResultProcessor")

            if category_name not in noneList:
                # Filter for the category
                category_query = CMDBCategory.objects.filter(
                    organization=org_id,
                    is_deleted=False,
                    name=category_name,
                    cmdb_class='1'
                )

                # Check for sub_category_name
                if sub_category_name not in noneList:
                    category = category_query.first()  # Get the first matching category
                    if category:
                        # Find the sub-category within the embedded documents
                        cmdb_item = next((item for item in category.items if item.name == sub_category_name), None)
                        if cmdb_item:
                            cmdb_obj["sub_category_id"] = cmdb_item.sub_category_id
                            cmdb_obj["category_id"] = category.category_id
                else:
                    category = category_query.first()
                    if category:
                        cmdb_obj["category_id"] = category.category_id
            logger.debug("Exiting from get_category_id of DiscoveryResultProcessor")
            return cmdb_obj
        except Exception as error:
            logger.exception("Method get_category_id of DiscoveryResultProcessor - Error: %s" % error)
        return {}
    
    def send_logmgmt_asset_sync_data_to_queue(self, celery_params):
        """
        function to send log management asset sync data to queue
        :celery_params: celery params
        :return: true/false
        """
        try:
            organization_id = celery_params.get('organization')
            delay_seconds = 300
            task_name = 'app.logmanagement.log_integration.tasks.start_logmanagement_asset_sync'
            default_exchange_options = {
                "exchange_name": "LogmanagementAssetSyncDelay",
                "exchange_type": "x-delayed-message",
                "args": {"x-delayed-type": "direct"}
            }
            exchange = get_setting_data("LOG_MGMT_DELAY_EXCHANGE_OPTIONS", default_exchange_options)
            out = self.queueObj.send_data(celery_params, "sync_logmanagement_asset_data", task_name, 
                        exchange = exchange,
                        msg_properties = {"headers": {"x-delay": delay_seconds * 1000}}
                    )
            if out:
                logger.info("Sending log management asset sync data to queue - %s -> next action in %s seconds" % (organization_id, delay_seconds))
            else:
                logger.error("Log management asset sync data to queue failed - %s " % (organization_id ))
            return out
        except Exception as e:
            logger.exception("Error sending log management asset sync data - %s" % (organization_id))
        return False
    

    def send_logmgmt_events_clear_data_to_queue(self, celery_params):
        """
        function to send log management events clear data to queue
        :celery_params: celery params
        :return: true/false
        """
        try:
            organization_id = celery_params.get('organization')
            delay_seconds = 300
            task_name = 'app.logmanagement.log_integration.tasks.start_logmanagement_events_clear'
            default_exchange_options = {
                "exchange_name": "LogmanagementEventsClearDelay",
                "exchange_type": "x-delayed-message",
                "args": {"x-delayed-type": "direct"}
            }
            exchange = get_setting_data("LOG_MGMT_DELAY_EXCHANGE_OPTIONS", default_exchange_options)
            out = self.queueObj.send_data(celery_params, "sync_logmanagement_events_clear", task_name, 
                        exchange = exchange,
                        msg_properties = {"headers": {"x-delay": delay_seconds * 1000}}
                    )
            if out:
                logger.info("Sending log management events clear data to queue - %s -> next action in %s seconds" % (organization_id, delay_seconds))
            else:
                logger.error("Log management events clear data to queue failed - %s " % (organization_id ))
            return out
        except Exception as e:
            logger.exception("Error sending log management events clear data - %s" % (organization_id))
        return False

    def log_events_clear(self, params):
        """
        Function to clear log events based on a time condition and threshold ID pattern
        return: response data
        """
        try:
            logger.info("Enter into log_events_clear function on LogIntegrationController.")
            organization = params.get("organization", "")
            days_threshold = get_settings("LOG_EVENTS_CLEAR_TIME_IN_DAYS")
            if days_threshold:
                days_threshold = int(days_threshold)
                time_threshold = datetime.utcnow() - timedelta(days=days_threshold)
                init_filter_condition = Q(is_deleted=False,is_cleared=0,last_event__lte=time_threshold,thresid__startswith="LOGMGMT")
                log_event_objs = ActiveEvents.objects.filter(init_filter_condition, organization=organization).order_by("creation_time")
                log_event_objs.update(is_cleared=1)
                self.send_logmgmt_events_clear_data_to_queue(params)
            logger.info("Exit from log_events_clear on LogIntegrationController")
        except Exception as e:
            logger.error("Method log_events_clear on LogIntegrationController: %s (%s)" % (e, type(e)))

    def get_space_data_from_role(self, group_id, username):
        """
        Function to get space id.
        :group_id: group id
        :username: username
        :return : response data
        """
        response_data = []
        request_data = {}
        role_space_id = ''
        try:
            logger.info("Enter into get_space_data_from_role function on LogIntegrationController.")
            group_data = GroupProfile.objects.filter(group_id=group_id).first()
            role_name = group_data.role_name.replace(' ', '_') +"_"+ username
            role_url = get_settings("LOG_MGMT_ROLE_URL")
            url = f"{role_url}/{role_name}"
            request_type = "GET"
            response_data = self.sync_log_management_data(request_type, request_data, url)
            if response_data.get('ok'):
                space_data = json.loads(response_data.get('data').decode('utf-8'))
                role_space_id = space_data.get('kibana')[0].get('spaces')[0]
                if role_space_id == '*':
                    role_space_id = ''
            logger.info("Exit from get_space_data_from_role function on LogIntegrationController.")
            return role_space_id
        except Exception as err:
            logger.error("Method get_space_data_from_role on LogIntegrationController :%s (%s)" % (
                err, type(err)))
            return ''
        

    def get_indices(self,request):
        """
        Function to retrieve and clean Elasticsearch indices that contain documents
        where   "event.organization": organization_id,
                "event.customer_id": customer_id,
                "event.customer_entity_id": entity_id
        :return: List of cleaned index names.
        """
        try:
            logger.info("Enter into get_indices function on LogIntegrationController.")
            es = self.elasticObj.get_elasticsearch_connection()
            indices = es.indices.get_alias(index="*")
            user_indices = [index for index in indices if not index.startswith('.')]
            # Filter indices based on search for specific organization
            matching_indices = []
            if type(request)!=str:
                organization_id = self.get_organization_id(request)
            else:
                organization_id = request
            post_data = {}
            # customer_id
            is_msp_customer_user = self.is_msp_customer_user(request)
            customer_id = ""
            entity_id = ""
            if is_msp_customer_user:
                if request.method == "POST":
                    post_data = self.get_post_data(request)
                if request.GET and "customer_id" in request.GET:
                    customer_id = request.GET.get("customer_id", "-1")
                elif "customer_id" in post_data:
                    customer_id = post_data.get("customer_id", "-1")
                elif hasattr(request, "customer_id") and not is_msp_customer_user: # When Multi Customer User selects navbar filter it has issue.:
                    customer_id = request.customer_id
                # entity id
                if request.GET and "customer_entity_id" in request.GET:
                    entity_id = request.GET.get("customer_entity_id", "-1")
                elif "customer_entity_id" in post_data:
                    entity_id = post_data.get("customer_entity_id", "-1")
                elif hasattr(request, "customer_entity_id") and not is_msp_customer_user: # When Multi Customer User selects navbar filter it has issue.
                    entity_id = request.customer_entity_id
            if not is_msp_customer_user and customer_id in self.noneList:
                query = {
                    "query": {
                        "term": {
                            "event.organization": organization_id
                        }
                    },
                    "size": 0
                }
            elif is_msp_customer_user :
                if is_msp_customer_user and entity_id in self.noneList:
                    query = {
                        "query": {
                            "bool": {
                                "must": [
                                    {"term": {"event.organization": organization_id}},
                                    {"term": {"event.customer_id": customer_id}}
                                ]
                            }
                        },
                        "size": 0
                    }
                else:
                    query = {
                        "query": {
                            "bool": {
                                "must": [
                                    {"term": {"event.organization": organization_id}},
                                    {"term": {"event.customer_id": customer_id}},
                                    {"term": {"event.customer_entity_id": entity_id}}
                                ]
                            }
                        },
                        "size": 0
                    }
            cleaned_indices = list(OrderedDict.fromkeys(index.split('-')[0] for index in user_indices))
            for index in cleaned_indices:
                try:
                    response = es.search(index=index+'*', body=query)
                    if response['hits']['total']['value'] > 0:
                        matching_indices.append(index)
                except Exception as e:
                    logger.warning(f"Skipping index {index} due to error: {e}")
                    continue
            # Clean the matching indices (extract prefix before first '-')
            # cleaned_indices = list(OrderedDict.fromkeys(index.split('-')[0] for index in matching_indices))
            logger.info("Exit from get_indices function on LogIntegrationController.")
            return matching_indices
        except Exception as e:
            logger.exception("Error retrieving and filtering indices from Elasticsearch: %s" % (e))
            return []
        
            
    def delete_documents_older_than_days(self, each_dict ):
        """
        Function to delete Elasticsearch documents older than days.
        :return: Dictionary containing the status 'success' or 'failed' with an error message.
        """
        try:
            logger.info("Enter into delete_documents_older_than_days function on LogIntegrationController.")      
            index_name = each_dict.get('index_name','')
            days = each_dict.get('days','') 
            date_threshold = datetime.now() - timedelta(days=safe_int(days))
            date_threshold_timestamp = int(date_threshold.timestamp() * 1000)  
            es = self.elasticObj.get_elasticsearch_connection()
            indices = es.indices.get_alias(index=index_name +"*") 
            for index_name in indices.keys():
                # Get index creation date
                index_info = es.indices.get(index=index_name)  
                creation_date = index_info[index_name]['settings']['index']['creation_date']
                # Convert creation date to timestamp
                creation_date_timestamp = int(creation_date)  
                # Compare creation date with the threshold
                if creation_date_timestamp < date_threshold_timestamp:
                    # Delete the index
                    logger.info(f"Deleting index: {index_name}")
                    response = es.indices.delete(index=index_name) 
                    logger.info("Deletion response: %s", response)
                else:
                    logger.info(f"Index {index_name} is not older than 15 days.")
            logger.info("Exit from delete_documents_older_than_days function on LogIntegrationController.")
        except Exception as e:
            logger.exception("Error deleting old indices from Elasticsearch: %s", e)

    def get_log_columns(self, request):
        """
        Function to get log columns.
        :return: log_columns list
        """
        log_columns = []
        try:
            logger.info("Enter into get_log_columns function on LogIntegrationController.")
            index_pattern = request.GET.get('index_pattern','*')    
            widget_type = request.GET.get('widget_type','')     
            if index_pattern[0]=='[':
                index_pattern=json.loads(index_pattern)
            if isinstance(index_pattern,str):
                index_pattern=index_pattern+"*"
                log_columns=self.elasticObj.get_log_columns(index_pattern)
            elif isinstance(index_pattern,list):
                index=[]
                for item in index_pattern:
                    if isinstance(item,dict):
                        if item.get("title"):
                            for i in item.get("title").split(","):
                                index.append(i.replace(' ',''))
                        elif item.get("id"):
                            index.append(item.get("id")+"*")
                    else:
                        item = item +'*' if item[-1] != '*' else item
                        index.append(item)
                log_index_columns=self.elasticObj.get_log_columns(index)
                log_columns.extend(log_index_columns)
            if log_columns:
                log_columns = list({d['value']: d for d in log_columns}.values())
            if widget_type in ["log_mgmt_summary_trendline","log_mgmt_summary_heatmap"]:
                log_columns = LOG_MGMT_ASSET_GROUP_BY_COLUMS + log_columns
                filtered_data = [column for column in log_columns if column.get('name') not in ['@timestamp', 'timestamp', 'timestamp.keyword']]
                log_columns = filtered_data
            logger.info("Exit from get_log_columns function on LogIntegrationController.")
        except Exception as e:
            logger.exception("Error getting log columns from Elasticsearch: %s", e)
        return log_columns

    def get_log_filter_suggestions(self, request):
        """
        Function to get log filter suggestions.
        :return: log_filter_suggestions list
        """
        log_filter_suggestions = []
        index = []
        try:
            logger.info("Enter into get_log_filter_suggestions function on LogIntegrationController.")
            # filter_cond = Q()
            request_data = self.get_query_params_data(request)
            organization_id = self.get_organization_id(request)
            user_tz = request_data.get("user_tz", "UTC")
            field = request_data.get('filter_key','')
            index_pattern_obj = json.loads(request_data.get('index_pattern','{}'))
            index_pattern = index_pattern_obj.get('index_pattern') if index_pattern_obj.get('index_pattern',[]) else index_pattern_obj.get('multi_index',[])
            for item in index_pattern:
                if isinstance(item,dict):
                    if item.get("title"):
                        for i in item.get("title").split(","):
                            index.append(i.replace(' ',''))
                    elif item.get("id"):
                        index.append(item.get("id")+"*")
                else:
                    index.append(item)
            if field:
                field = field.replace('(', '').replace(')', '').replace(' ', '')
                log_visibility = self.get_log_visibility(request)
                log_filter_suggestions = self.elasticObj.get_filter_suggestions(request, index, field, user_tz, log_visibility)
            logger.info("Exit from get_log_filter_suggestions function on LogIntegrationController.")
        except Exception as e:
            logger.exception("Error getting log filter suggestions from Elasticsearch: %s", e)
        return log_filter_suggestions
    

    def get_log_visibility(self,request):
        """
        Function to get log filter visibility for MSP and customer-based access.
        :param request: request object
        :return: dict with log visibility info and MSP filters
        """
        result = {}
        try:
            logger.info("Enter into get_log_filter_visibility function on LogIntegrationController.")
            organization_id = self.get_organization_id(request)
            msp_filter = self.get_customer_entity_filter_condition(request, return_dict=True)
            if isinstance(msp_filter, dict):
                for key in ("customer_id", "customer_entity_id"):
                    if key in msp_filter and not isinstance(msp_filter[key], list):
                        msp_filter[key] = [msp_filter[key]]
            # Initialize flags
            result['is_customer'] = self.is_msp_customer_user(request, return_customer_id=False)
            result['is_multi_customer_user'] = self.is_multi_customer_user(request)
            result['is_msp_org'] = self.is_msp_org(request, organization_id)
            msp_dist = []
            # Normalize msp_filter to a list of dicts
            if msp_filter:
                if isinstance(msp_filter, dict):
                    msp_items = [msp_filter]
                elif isinstance(msp_filter, list):
                    msp_items = msp_filter
                else:
                    msp_items = []
            else:
                msp_items = []
            # Loop over MSP items to map customer -> entities
            for item in msp_items:
                customer_ids = item.get("customer_id", [])
                entity_ids = item.get("customer_entity_id", [])

                for customer_id in customer_ids:
                    # Fetch entity objects for this customer
                    entity_objs = CustomerEntity.objects.filter(
                        customer_id=customer_id,
                        organization=organization_id,
                        is_deleted=False
                    )
                    entity_data = CustomerEntityListSerializer(entity_objs, many=True).data
                    # Map only the entities present in entity_ids
                    entity_map = [
                        entity["customer_entity_id"]
                        for entity in entity_data
                        if entity["customer_entity_id"] in entity_ids
                    ]
                    dist_item = {"customer_id": [customer_id]}
                    if entity_map:
                        dist_item["customer_entity_id"] = entity_map
                    msp_dist.append(dist_item)
            filtered_list = []
            filter_cond = Q(is_deleted=False,object_type="Node",is_logmanagement_enabled=True,is_enabled=True)
            visibility_filter = self.get_cmdb_visibility_filter(request, organization_id=organization_id)
            if visibility_filter:
                filter_cond = filter_cond & visibility_filter
                #filter_cond = visibility_filter & Q(is_deleted=False,object_type="Node",is_logmanagement_enabled=True,is_enabled=True)
            assets = list(CMDBCi.objects.filter(filter_cond).values_list('ip_address'))
            if assets:
                filtered_list = list(filter(None, assets))
                filtered_list = [
                    ip for ip in assets
                    if ip and ip not in self.noneList
                ]
                filtered_list = [
                    filtered_list[i:i+500]
                    for i in range(0, len(filtered_list), 500)
                ]
            else:
                filtered_list = ['0.0.0.0']
            
            result['msp_list'] = msp_dist
            result['host_ip'] = filtered_list
            logger.info("Exit from get_log_filter_visibility function on LogIntegrationController.")
        except Exception as e:
            logger.exception("Error getting get_log_filter_visibility: %s", e)
        return result
    
    def get_log_columns_for_pipeline(self,request):
        """
        Function to get log columns.
        :return: log_columns list
        """
        log_columns = []
        try:
            logger.info("Enter into get_log_columns_for_pipeline function on LogIntegrationController.")
            param = {'module_id':95,'option_type':5}
            system_options = self.get_system_option_for_macro_language(request, param)
            log_columns=system_options[0].get('data',[])
            logger.info("Exit from get_log_columns_for_pipeline function on LogIntegrationController.")
        except Exception as e:
            logger.exception("Error getting log columns from Elasticsearch: %s", e)
        return log_columns

    def get_log_filter_suggestions_for_pipeline(self,request):
        """
        Function to get log filter suggestions.
        :return: log_filter_suggestions list
        """
        log_filter_suggestions = []
        try:
            logger.info("Enter into get_log_filter_suggestions function on LogIntegrationController.")
            request_data = self.get_query_params_data(request)
            user_tz = request_data.get("user_tz", "UTC")
            field = request_data.get('filter_key','')  
            index_pattern = request_data.get('index_pattern','*') + '*'
            if field:
                field = field.replace('(', '').replace(')', '').replace(' ', '')
                log_visibility = self.get_log_visibility(request)
                log_filter_suggestions = self.elasticObj.get_filter_suggestions(request, index_pattern, field, user_tz, log_visibility)
                param = {'module_id':95,'option_type':6}
                system_options = self.get_system_option_for_macro_language(request, param)
                # log_filter_suggestions=log_filter_suggestions[0]
                log_filter_suggestions_default=system_options[0].get('data',[])[0].get(field,[])
                log_filter_suggestions=list(set(log_filter_suggestions + log_filter_suggestions_default))
            logger.info("Exit from get_log_filter_suggestions function on LogIntegrationController.")
        except Exception as e:
            logger.exception("Error getting log filter suggestions from Elasticsearch: %s", e)
        return log_filter_suggestions

    
    def validate_esql(self,request):
        """
        Function to validate esql.
        :return: esql_validation_response dict
        """
        esql_validation_response = {}
        try:
            logger.info("Enter into validate_esql function on LogIntegrationController.")
            request_data = self.get_query_params_data(request)
            esql = request_data.get('esql_filter', '')
            esql_validation_response = self.elasticObj.validate_esql_query(esql)
            logger.info("Exit from validate_esql function on LogIntegrationController.")
        except Exception as e:
            logger.exception("Error validating esql: %s", e)
        return esql_validation_response



    def update_esql_filter(self, esql, org_id):
        try:
            required_keep_fields = ["message", "host.ip", "host.name", "event.organization"]
            metadata_fields = ["_id", "_version", "_index"]
            agg_functions = [
                "AVG", "COUNT", "COUNT_DISTINCT", "MAX", "MEDIAN", "MEDIAN_ABSOLUTE_DEVIATION", "MIN",
                "PERCENTILE", "ST_CENTROID_AGG", "ST_EXTENT_AGG", "STD_DEV", "SUM", "TOP", "VALUES", "WEIGHTED_AVG"
            ]

            lines = [line.strip() for line in esql.strip().split('\n') if line.strip()]
            new_lines = []
            where_found = False
            keep_found = False

            # Prepare regex for "STATS ... AGG_FUNC ... BY" or just "STATS ... AGG_FUNC"
            agg_func_regex = "|".join(map(re.escape, agg_functions))
            stats_agg_regex = re.compile(r"\bSTATS\b[^|]*\b(" + agg_func_regex + r")\b", re.IGNORECASE)

            # Detect if query is aggregating
            stats_by_present = any(stats_agg_regex.search(line) for line in lines)

            for idx, line in enumerate(lines):
                # WHERE
                if re.match(r"^\|?\s*WHERE\b", line, re.IGNORECASE):
                    where_found = True
                    if "event.organization" not in line:
                        line = line.rstrip() + f' AND event.organization == "{org_id}"'
                # KEEP
                if re.match(r"^\|?\s*KEEP\b", line, re.IGNORECASE):
                    keep_found = True
                    fields_str = re.split(r"\s*KEEP\s*", line, flags=re.IGNORECASE)[-1]
                    current_fields = [f.strip() for f in fields_str.split(',')]

                    # Always require standard keep fields
                    for f in required_keep_fields:
                        if f not in current_fields:
                            current_fields.append(f)

                    # If not aggregating, ensure metadata fields too
                    if not stats_by_present:
                        for f in metadata_fields:
                            if f not in current_fields:
                                current_fields.append(f)
                    line = "| KEEP " + ", ".join(current_fields)
                # FROM line: add metadata if not aggregating and not already present
                if not stats_by_present and re.match(r"^FROM\b", line, re.IGNORECASE):
                    if "metadata" not in line.lower():
                        m = re.match(r"^(FROM\s+[^\s|]+)", line, re.IGNORECASE)
                        if m:
                            from_clause = m.group(1)
                            rest = line[len(from_clause):]
                            line = f"{from_clause} metadata _id, _version, _index{rest}"
                new_lines.append(line)

            # If no WHERE, add it after FROM
            if not where_found:
                for i, line in enumerate(new_lines):
                    if re.match(r"^FROM\b", line, re.IGNORECASE):
                        new_lines.insert(i+1, f'| WHERE event.organization == "{org_id}"')
                        break

            # If no KEEP, add it at the end (include metadata if not aggregating)
            if not keep_found:
                keep_fields = required_keep_fields[:]
                if not stats_by_present:
                    keep_fields += [f for f in metadata_fields if f not in keep_fields]
                new_lines.append("| KEEP " + ", ".join(keep_fields))

            return "\n".join(new_lines)
        except Exception as msg:
            logger.exception("Error updating esql filter: %s", msg)
            return ''

    def get_nql_query(self, request):
        """
        Function to get nql query
        Construct the DSL query from the NQL query given by the user
        params : request
        return: log_query
        """
        try:
            logger.info(f"Enter into get_nql_query function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            start_time =datetime.now()
            request_data = self.get_query_params_data(request)
            nql_query = request_data.get('params', {}).get('query', {}).get('query', "")
            log_query = {}
            log_query['query'] = {"match_all": {}}
            if nql_query not in self.noneList:
                index_patterns = request_data.get('params', {}).get('indexPatterns', [])
                if index_patterns:
                    LOG_INDEX_PATTERN = index_patterns[0].get('title') or "*"
                else:
                    LOG_INDEX_PATTERN = "*"
                if LOG_INDEX_PATTERN == "**":
                    LOG_INDEX_PATTERN = "*"
                EXCLUDED_ROOTS = (
                    "dns","dll","client","cloud","container","data_stream","destination","faas",
                    "file.code_signature","file.elf","file.pe","file.x509","host.geo","host.network",
                    "network","observer","orchestrator","package","process.code_signature",
                    "process.elf","process.hash","process.parent","process.pe","registry","related",
                    "rule","server","service","source.geo","threat","tls","user.effective",
                    "vulnerability","user_agent","user","message","event.original",
                    "system.auth.message","system.auth.timestamp","@timestamp","event.created","event.ingested","rabbitmq.log.pid","mongodb.log.id",
                )
                es = self.elasticObj.get_elasticsearch_connection()
                get_all_fields = self.get_all_fields(
                    request=request,
                    es_client=es,
                    index_pattern=LOG_INDEX_PATTERN,
                    excluded_roots=EXCLUDED_ROOTS
                )
                get_all_fields = json.dumps(get_all_fields, indent=2)
                if get_all_fields:
                    # Step 1: Prepare prompt for selecting fields
                    selected_fields_prompt = PROMPT_SELECT_FIELDS.replace(
                        "@@nql@@", nql_query
                    ).replace(
                        "@@all_fields@@", json.dumps(get_all_fields, indent=2)
                    )
                    # Step 2: Send to AI client
                    query = "The user given nql query is " + nql_query
                    response = self.call_ai_client(request, selected_fields_prompt, query)
                    # Step 3: Extract JSON selected fields from AI response
                    selected_fields_ai = response
                    # Step 4: Collect all values for the selected fields
                    field_values_full = {}
                    for field_def in selected_fields_ai:
                        field_name = next(iter(field_def.keys()))
                        values = self.get_field_values(self,es,LOG_INDEX_PATTERN,field_def,50)
                        if values:
                            field_values_full[field_name] = values
                    # Step 5: Prepare prompt for selecting relevant values
                    field_values_full_json = json.dumps(field_values_full, indent=2)
                    field_values_prompt = PROMPT_SELECT_RELEVANT_FIELD_VALUES.replace(
                        "@@nql@@", nql_query
                    ).replace(
                        "@@field_values@@", field_values_full_json
                    )
                    # Step 6: Send to AI client to filter relevant values
                    response_values = self.call_ai_client(request, field_values_prompt, query)
                    field_values_full = response_values
                    TIME_FIELDS = {"timestamp", "@timestamp"}
                    field_values_full = {
                        k: v for k, v in field_values_full.items()
                        if k not in TIME_FIELDS
                    }
                    matched_queries = []
                    for fields_subset in self.build_reversed_field_plan(list(field_values_full.keys())):
                        scoped_field_values = {
                            f: field_values_full[f]
                            for f in fields_subset
                            if field_values_full.get(f)
                        }
                        if not scoped_field_values:
                            continue
                        dsl = self.build_dsl_from_fields(scoped_field_values, nql_query, selected_fields_ai)
                        if not self.has_non_time_filter(dsl):
                            continue
                        count = self.get_dsl_count(es, LOG_INDEX_PATTERN, dsl)
                        if count > 0:
                            matched_queries.append({
                                "query": dsl.get("query", {})
                            })
                    if not matched_queries or (isinstance(matched_queries, str) and not matched_queries.strip()):
                        # Return early if there are no matched queries
                        return log_query
                    matching_prompt = PROMPT_MATCHING_QUERY.replace(
                        "@@nql@@", nql_query
                    ).replace(
                        "@@query@@", str(matched_queries)
                    )
                    parsed = ''
                    response_values = self.call_ai_client(request, matching_prompt, query)
                    if isinstance(response_values, str):
                        response_values = response_values.strip()
                        response_values = re.sub(r"^```(?:json)?\s*", "", response_values)
                        response_values = re.sub(r"\s*```$", "", response_values)
                        parsed = json.loads(response_values)
                    elif isinstance(response_values, dict):
                        parsed = response_values
                    log_query['status'] = 'success'
                    log_query['query'] = parsed.get('query', {})
                    return log_query
                else:
                    logger.info(f"NQL getting empty fields. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
                    return  log_query
            else:
                logger.info(f"Exit from get_nql_query function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
                return  log_query
        except Exception as e:
            logger.exception(f"Error getting nql query: {e}organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
        return  log_query
    
    def get_dsl_count(self, es: Elasticsearch, index_pattern: str, dsl: dict) -> int:
        """
        Returns the number of documents matching the DSL query.
        """
        try:
            response = es.count(index=index_pattern, body=dsl)
            return response.get("count", 0)
        except Exception as e:
            logger.error(f"Error getting count: {e}")
            return 0
        
    def build_dsl_from_fields(
        self,
        scoped_field_values: Dict[str, Union[str, List[str]]],
        nql: str,
        selected_fields: list
    ) -> Dict:
        """
        Build Elasticsearch DSL query from selected fields and values.

        - scoped_field_values: {"account": ["root"], "uid": ["0"], ...}
        - selected_fields: [{"account": "text"}, {"uid": "text"}, ...] (AI output)
        """
        field_type_map = {}
        for item in selected_fields:
            if isinstance(item, dict) and item:
                key, val = next(iter(item.items()))
                field_type_map[key] = val
            filters = []
            for field, value in scoped_field_values.items():
                # Ensure value is a list
                values = value if isinstance(value, list) else [value]
                if not values:
                    continue
                # Special handling for "message" field
                if field == "message":
                    for v in values:
                        filters.append({
                            "wildcard": {
                                "message": f"{v}"
                            }
                        })
                    continue  # skip normal term/terms handling
                # Append .keyword ONLY for text fields (not message)
                field_type = field_type_map.get(field)
                query_field = f"{field}.keyword" if field_type == "text" else field
                # Use "term" for single value, "terms" for multiple
                filters.append(
                    {"term": {query_field: values[0]}} if len(values) == 1 else {"terms": {query_field: values}}
                )
        # Add time range if present in NQL
        time_range = self.extract_time_range(nql)
        if time_range:
            filters.append({"range": {"@timestamp": time_range}})
        return {"query": {"bool": {"filter": filters}}}
    

    def extract_time_range(self, nql: str) -> Optional[Dict[str, str]]:
        """
        Extract a time range from NQL phrases like:
        - today, yesterday
        - this week, this month, this year
        - previous week, previous month, previous year
        - last week, last month, last year
        - last 3 hours, last 2 days, last 4 weeks, last 6 months, last 1 year
        """
        nql = nql.lower()
        word_numbers = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
        }
        # Today / Yesterday
        if "today" in nql:
            return {"gte": "now/d", "lt": "now"}
        if "yesterday" in nql:
            return {"gte": "now-1d/d", "lt": "now/d"}
        # This week / month / year
        if "this week" in nql:
            return {"gte": "now/w", "lt": "now"}
        if "this month" in nql:
            return {"gte": "now/M", "lt": "now"}
        if "this year" in nql:
            return {"gte": "now/y", "lt": "now"}
        # Previous / Last week/month/year
        if "previous week" in nql or "last week" in nql:
            return {"gte": "now-1w/w", "lt": "now/w"}
        if "previous month" in nql or "last month" in nql:
            return {"gte": "now-1M/M", "lt": "now/M"}
        if "previous year" in nql or "last year" in nql:
            return {"gte": "now-1y/y", "lt": "now/y"}
        # last N hours/days/weeks/months/years  (digits OR words)
        m = re.search(
            r"last\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*"
            r"(hour|hours|day|days|week|weeks|month|months|year|years)",
            nql
        )
        if m:
            count_raw, unit = m.groups()
            if count_raw.isdigit():
                count = int(count_raw)
            else:
                count = word_numbers.get(count_raw, 1)
            unit_map = {
                "hour": "h", "hours": "h",
                "day": "d", "days": "d",
                "week": "w", "weeks": "w",
                "month": "M", "months": "M",
                "year": "y", "years": "y"
            }
            es_unit = unit_map[unit]
            round_down = "" if es_unit == "h" else "/d"
            return {"gte": f"now-{count}{es_unit}{round_down}", "lt": "now"}
        return None

    def has_non_time_filter(self,dsl: Dict) -> bool:
        return any(
            "term" in f or "terms" in f
            for f in dsl.get("query", {}).get("bool", {}).get("filter", [])
        )

    def build_reversed_field_plan(self,fields: list) -> list[list[str]]:
        """
        Generate reversed field plans without using itertools.
        Returns a list of lists of field subsets, from full to singletons.
        """
        n = len(fields)
        plans = []
        # full set first
        if n > 1:
            plans.append(fields[:])
        # generate all subsets of size n-1 down to 2
        for r in range(n - 1, 1, -1):
            def helper(start=0, path=[]):
                if len(path) == r:
                    plans.append(path[:])
                    return
                for i in range(start, n):
                    path.append(fields[i])
                    helper(i + 1, path)
                    path.pop()
            helper()
        # single fields in reverse order
        for f in reversed(fields):
            plans.append([f])
        return plans
    
    def extract_json(self, text: str) -> Union[dict, list]:
        """
        Extract JSON object or array from AI response text.
        Handles:
        - Markdown code fences ```json ... ```
        - Extra text before or after JSON
        - Minor formatting issues (newlines, spaces)
        
        Returns Python dict or list. If JSON cannot be parsed, returns empty list.
        """
        if not text or not text.strip():
            return []
        text = text.strip()
        # Remove Markdown code fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        # Attempt direct parsing
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Fallback: find first JSON object or array using regex
        match = re.search(r"(\{.*?\}|\[.*?\])", text, re.DOTALL)
        if match:
            raw_json = match.group(1)
            try:
                return json.loads(raw_json)
            except json.JSONDecodeError:
                return []
        # If all fails, return empty list
        return []
    

    def get_field_values(
        self,
        request,
        es: Elasticsearch,
        index_pattern: str,
        field_def: Dict[str, str],
        terms_size: int = 50
    ) -> List[str]:
        """
        Fetch unique values for a field using Elasticsearch aggregation.

        field_def example:
        {"event.module": "keyword"}
        """
        try:
            logger.info(f"Enter into ES for getting field value function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            field, field_type = next(iter(field_def.items()))
            if not field or not field_type:
                return []
            # Append .keyword ONLY for text fields
            if field_type == "text":
                agg_field = f"{field}.keyword"
            else:
                agg_field = field
            body = {
                "size": 0,
                "aggs": {
                    "values": {
                        "terms": {
                            "field": agg_field,
                            "size": terms_size,
                            "order": {"_count": "desc"}
                        }
                    }
                }
            }
            resp = es.search(
                index=index_pattern,
                body=body
            )
            buckets = (
                resp.get("aggregations", {})
                    .get("values", {})
                    .get("buckets", [])
            )
            return [b["key"] for b in buckets]
        except Exception as e:
            logger.exception(f"Getting error for field value function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            return []

    def should_exclude(self, field: str, excluded_roots: Set) -> bool:
        return any(field == r or field.startswith(r + ".") for r in excluded_roots)

    def flatten_properties(
        self,
        props: dict,
        excluded_roots: Set,
        parent: str = ""
    ) -> Dict[str, str]:
        fields = {}
        for k, v in props.items():
            name = f"{parent}.{k}" if parent else k
            if self.should_exclude(name, excluded_roots):
                continue
            if "properties" in v:
                fields.update(
                    self.flatten_properties(
                        props=v["properties"],
                        excluded_roots=excluded_roots,
                        parent=name
                    )
                )
            elif "type" in v:
                fields[name] = v["type"]
        return fields
        
    def get_all_fields(
            self,
            request,
            es_client: Elasticsearch,
            index_pattern: str,
            excluded_roots: Set
        ) -> Dict[str, str]:
        try:
            logger.info(
                f"Fetching mappings | index={index_pattern} | "
                f"org_id={self.get_organization_id(request)} "
                f"user_id={self.get_user_id(request)}"
            )
            mappings = es_client.indices.get_mapping(index=index_pattern)
            all_fields = {}
            for idx in mappings.values():
                props = idx.get("mappings", {}).get("properties", {})
                all_fields.update(
                    self.flatten_properties(
                        props=props,
                        excluded_roots=excluded_roots
                    )
                )
            return all_fields
        
        except Exception as e:
            logger.exception(
                f"get_all_fields failed | "
                f"org_id={self.get_organization_id(request)} "
                f"user_id={self.get_user_id(request)} | error={e}"
            )
            return {}

    def get_field_caps(es: Elasticsearch, index_pattern: str) -> Dict:
        return es.field_caps(index=index_pattern, fields="*")
    
    def validate_dsl_query(self, request,es:Elasticsearch, indices_clean, dsl_query):
        """
        Validate the dsl query
        param request: request
        param es: es
        param indices_clean: indices_clean
        param dsl_query: dsl_query
        return: True or False
        """
        res ={
            "valid": False,
            "explanations": []
        }
        try:
            logger.info(f"Enter into validate_dsl_query function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            err = None
            try:
                response = es.indices.validate_query(index=indices_clean, body=dsl_query, explain=True)
            except Exception as e:
                err = str(e)
            if response.get("valid", False)==False:
                res= {
                    "valid": response.get("valid", False),
                    "explanations": response.get("error", None) or err
                }
                logger.error(f"The given DSL Query is not valid. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
                return res
            else:
                res= {
                    "valid": response.get("valid", False),
                    "explanations": response.get("error", [])
                }
            logger.info(f"Exit from validate_dsl_query function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            return res
        except Exception as e:
            logger.error(f"An error occurred: {str(e)} organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            return res
        
    def call_ai_client(self,request,prompt,query: str=""):
        """
        Call AI client call the marketplace AI client to get the response
        param request: request
        param prompt: prompt
        param query: query
        return: response
        """
        try:
            logger.info(f"Enter into call_ai_client function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            organization_id = self.get_organization_id(request)
            filter_query = {}
            model=DEFAULT_OPENAI_MODEL
            if prompt not in self.noneList:
                infraonai_key_setting = self.bot_config.get_infraonai_key_settings({}, organization_id=organization_id,feature_type= FEATURE_TYPE_MAPPING.get('logmangement_nql','logmangement_nql'))
                infraonai_settings = infraonai_key_setting.get('settings_data',{}).get(FEATURE_TYPE_MAPPING.get('logmangement_nql','logmangement_nql'),{})
                infraonai_keys = infraonai_key_setting.get('keys_data',{})
                # infraonai_settings['messages'] = []
                if query not in self.noneList:
                    chat = [{
                        "role": "system",
                        "content": prompt 
                    },
                    {
                        "role": "user",
                        "content": query
                    }]
                else:
                    chat = [{
                        "role": "system",
                        "content": prompt
                    }]
                infraonai_settings['messages']= chat
                # infraonai_settings['messages']['role'] = "user"
                # infraonai_settings['messages']['content'] = f"give me the dsl from Dsl to get the logs from elastic search for {nql_query}"
                infraonai_settings_cpy = copy.deepcopy(infraonai_settings)
                infraonai_settings_cpy['messages'] = chat
                data_config = {}
                data_config['feature_type'] = FEATURE_TYPE_MAPPING.get('logmangement_nql','logmangement_nql')
                data_config['module'] = MODULES_APP_KEY_KEY_MAP.get('log_discover')
                data_config['prompt'] = prompt
                data_config['creation_time'] = datetime.now(pytz.timezone(TIME_ZONE))
                data_config['settings'] = infraonai_settings
                data_config['ai_request_time_int'] = time.time()
                data_config['response_message_time'] = datetime.now(pytz.timezone(TIME_ZONE))

                if request not in self.noneList:
                    user_id = self.get_user_id(request)
                    user_name = self.get_user_full_name(request)
                else:
                    user_id = get_setting_data('SYSTEM_USER_ID')
                    user_name = get_setting_data('SYSTEM_DEFINED_NAME')
                    
                
                data_config = {
                    'user_id':user_id,
                    'organization_id': organization_id,
                    'ref_id':"", 
                    'wss_uuid': "",
                    'query' : chat,
                    'user_name': user_name,
                    'conversation_id': ""
                }

                data_config['feature_type'] = FEATURE_TYPE_MAPPING.get('logmangement_nql','logmangement_nql')
                data_config['module'] = MODULES_APP_KEY_KEY_MAP.get('log_discover')
                data_config['prompt'] = chat
                data_config['creation_time'] = datetime.now(pytz.timezone(TIME_ZONE))
                data_config['settings'] = infraonai_settings
                data_config['ai_request_time_int'] = time.time()
                openai_st = time.time()
                chat, status, err_msg = asyncio.run(self.get_ai_response(request,infraonai_settings, infraonai_keys))
                logger.warning("time taken from call_infraonai %s ans user %s"%(time.time()-openai_st, data_config.get('user_name','')))
                # Split the conversation into parts and interact with the model
                if chat and status == "success":
                    text_response = chat.text.strip()
                    if text_response.startswith("```"):
                        text_response = re.sub(r'^```json\s*|\s*```$', '', text_response, flags=re.DOTALL)
                    try:
                        query_dict = json.loads(text_response)
                    except json.JSONDecodeError as e:
                        return filter_query
                    filter_query = query_dict
                data_config['request_process_time_ms'] = (time.time()-data_config.get('ai_request_time_int',0))*1000
                data_config['full_reply_content'] = str(filter_query)
                data_config['input_token'] = self.ai_obj.num_tokens_from_messages(messages=data_config.get("query",""), model=model, prompt=False, is_str_output=True)
                data_config['output_token'] = self.ai_obj.num_tokens_from_messages(messages=chat, model=model, prompt=False, is_str_output=True)
                data_config['response_message_time'] = datetime.now(pytz.timezone(TIME_ZONE))
                data_config['openai_status'] = "success"
                data_config['query'] = prompt
                self.bot_config.save_openai_request_log(data_config, infraonai_settings)   
            logger.info(f"Exit from get_nql_query function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            return filter_query
        except Exception as e:
            logger.error(f"An error occurred: {str(e)} organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
        
        
        
    def get_all_indices(self,request,es_client: Elasticsearch):
        """
        Get all indices from Elasticsearch.
        """
        try:
            logger.info(f"Enter into get_all_indices function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            indices = es_client.indices.get_alias(index="*")
            indices = list(indices.keys())
            indices = [index for index in indices if not index.startswith('.')]# Use keyword argument
            logger.info(f"Exit from get_all_indices function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            return indices
        except Exception as e:
            logger.error(f"An error occurred: {str(e)} organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")

    def get_ecs_fields_from_index(
        self,
        request,
        es_client: Elasticsearch,
        index: Union[str, List[str]],
        keyword: Union[str, List[str], None] = None,
        query: Dict = {}
    ) -> List[str]:
        """
        Get unique ECS leaf fields from one or more Elasticsearch indices.
        Handles both string or list inputs for index and keyword.
        Returns only leaf fields (no nested structures).
        
        Args:
            es_client (Elasticsearch): Elasticsearch client instance.
            index (str | list): Index name or list of index names.
            keyword (str | list, optional): Filter to include fields containing these substrings (case-insensitive).
            query (dict, optional): Optional mapping filter query.
        
        Returns:
            list: Sorted list of unique ECS leaf field names.
        """
        try:
            logger.info(f"Enter into get_ecs_fields_from_index function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            # Normalize inputs
            indices = [index] if isinstance(index, str) else index
            keywords = [keyword.lower()] if isinstance(keyword, str) else (
                [k.lower() for k in keyword] if isinstance(keyword, list) else []
            )

            ecs_fields: Set[str] = set()
            # Fetch all mappings in a single call if possible
            mapping = es_client.indices.get_mapping(index=indices, body=query)
            def extract_leaf_fields(properties: Dict, parent: str = "") -> Set[str]:
                fields = set()
                for name, info in properties.items():
                    full_name = f"{parent}.{name}" if parent else name
                    props = info.get("properties")
                    
                    if isinstance(props, dict):
                        # Recurse into nested properties
                        fields.update(extract_leaf_fields(props, full_name))
                    else:
                        # Leaf field check
                        if keywords:
                            if any(full_name.lower().startswith(k) for k in keywords):
                                fields.add(full_name)
                        else:
                            fields.add(full_name)
                return fields
            for idx in indices:
                props = mapping[idx]["mappings"].get("properties", {})
                ecs_fields.update(extract_leaf_fields(props))
            # Remove redundant ".keyword" duplication
            final_fields = sorted(set(ecs_fields))
            logger.info("ECS Fields Added in Prompt:", final_fields)
            logger.info(f"Exit from get_ecs_fields_from_index function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            return final_fields
        except:
            logger.error(f"Error in get_ecs_fields_from_index function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            return []

    def get_field_values_from_indices(self, request, es_client: Elasticsearch, indices: list, fields: list, query: dict = None,slice_limit: int = 5):
        """
        Efficiently get up to 5 unique field values per field across all logs using composite aggregation.
        """
        try:
            logger.info(f"Enter get_field_values_from_indices on org_id: {self.get_organization_id(request)}, user_id: {self.get_user_id(request)}")

            if not indices or not fields:
                raise ValueError("Both 'indices' and 'fields' parameters are required.")
            if query not in self.noneList:
                if "query" in query:
                    query = query["query"]
            query_body = query if query else {"match_all": {}}
            field_samples = {}
            for field in fields:
                field = field.replace(".keyword", "")
                agg_body = {
                    "size": 0,
                    "query": query_body,
                    "aggs": {
                        "unique_values": {
                            "composite": {
                                "size": 1000,
                                "sources": [{field: {"terms": {"field": f"{field}.keyword"}}}]
                            }
                        }
                    }
                }
                response = es_client.search(index=indices, body=agg_body)
                buckets = response.get("aggregations", {}).get("unique_values", {}).get("buckets", [])
                values = [b["key"][field] for b in buckets if field in b["key"]]
                if values not in self.noneList:
                    field_samples[field] = " or ".join(values[:slice_limit])
            logger.info(f"Exit get_field_values_from_indices on org_id: {self.get_organization_id(request)}, user_id: {self.get_user_id(request)}")
            return field_samples

        except Exception as e:
            logger.error(f"Error in get_field_values_from_indices: {e}")
            return {}


    def fault_tolerant_Nql(self,request,es, indices_clean, query,explanations=""):
        """
        Fault Tolerant Nql
        if the dsl provided by the AI agent is not valid, it will be corrected using the Feed Back mechanism
        params : request,es, indices_clean, query,explanations
        return : validation_result after the validation
        """
        try:
            logger.info(f"Enter into fault_tolerant_Nql function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            prompt = NQL_FAULT_TOLERANCE_PROMPT.replace("@@query@@", str(query))
            if explanations not in self.noneList:
                prompt = prompt.replace("@@explanations@@", str(explanations))
            response = self.call_ai_client(request,prompt)
            if isinstance(response, str):
                fault_tolerance_dict_response = json.loads(response)
            else:
                fault_tolerance_dict_response = response
            validation_result = self.validate_dsl_query(request,es, indices_clean, fault_tolerance_dict_response.get("corrected_query",{}))
            if validation_result.get("valid", False):
                return fault_tolerance_dict_response.get("corrected_query",{})
            logger.info("Fault Tolerance Response", fault_tolerance_dict_response)
            logger.info(f"exit from fault_tolerant_Nql function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
        except Exception as e:
            logger.info("Error calling GPT model:", e)
            return {"query":{"match_all": {}}}
    def flatten_dict(self,request,d, parent_key="", sep="."):
        """
        Flatten a nested dictionary.

        Args:
            d (dict): Dictionary to flatten
            parent_key (str): Prefix for keys (used in recursion)
            sep (str): Separator for nested keys (default: ".")

        Returns:
            dict: Flattened dictionary
        """
        try:
            logger.info(f"Enter into flatten_dict function on LogIntegrationController.organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            items = {}
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.update(self.flatten_dict(v, new_key, sep=sep))
                else:
                    items[new_key] = v
            logger.info(f"Exit from flatten_dict function on LogIntegrationController.organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            return items
        except:
            logger.error("Error in flatten_dict function on LogIntegrationController.")
    def get_doc_count_and_samples(self,request,es_client: Elasticsearch, index, query: dict = None, sample_size: int = 5):
        """
        Get the document count and sample documents from Elasticsearch for a given index and query.
        Uses the modern client syntax without 'body'.
        """
        try:
            logger.info(f"Enter into get_doc_count_and_samples function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            # Default query
            query_body = query if query else None
            try:
                if query:
                    # Count documents   
                    count_resp = es_client.count(index=index, body=query_body)
                    total_count = count_resp.get("count", 0)
                    # Get sample documents
                    search_resp = es_client.search(
                        index=index,
                        size=sample_size,
                        body=query_body,
                    )
                else:
                    count_resp = es_client.count(index=index)
                    total_count = count_resp.get("count", 0)
                    search_resp = es_client.search(
                        index=index,
                        size=sample_size,
                    )
            except:
                logger.error(f"Error in get_doc_count_and_samples function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
                # self.fault_tolerant_Nql(request,es_client,index,query)
            # Parse search hits
            samples = [
                {
                    "_index": hit.get("_index"),
                    "_id": hit.get("_id"),
                    "_score": hit.get("_score"),
                    "_source": hit.get("_source", {})
                }
                for hit in search_resp.get("hits", {}).get("hits", [])
            ]
            logger.info(f"Exit from get_doc_count_and_samples function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            return {"count": total_count, "samples": samples}
        except Exception as e:
            logger.info(f"Error calling GPT model: {e}. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}", )
            return None
            
    async def get_ai_response(self,request,infraonai_settings_cpy, infraonai_keys):
        """
        Function to get ai response.
        :return: ai_response dict
        """
        logger.info(f"Enter into get_ai_response function on LogIntegrationController. organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
        try:
            chat, status, err_msg = await self.ai_obj.call_infraonai(infraonai_settings_cpy, infraonai_keys)
            logger.info("Exit from get_ai_response function on LogIntegrationController.")
            return chat, status, err_msg
        except Exception as e:
            logger.exception(f"Error getting ai response: {e} organization_id : {self.get_organization_id(request)} user_id : {self.get_user_id(request)}")
            return None, None, None
        
    def get_rule_execution_result(self, request):
        """
        Function to get rule execution result.
        :return: kibana_url str
        """
        response_data = {}
        try:
            logger.info("Enter into get_rule_execution_result function on LogIntegrationController.")
            request_data = self.get_query_params_data(request)
            user_tz = request_data.get("user_tz", "UTC")
            organization_id = self.get_organization_id(request)
            rule_id = request_data.get('rule_id', '')
            correlation_rule_model = CorrelationRules.objects.get(organization=organization_id, rule_id=rule_id, is_deleted=False)
            if correlation_rule_model:
                log_rule_id = correlation_rule_model.log_rule_id
                url = "/infraon/s/infraon_%s/api/detection_engine/rules?id=%s"%(organization_id, log_rule_id)
                data = {}
                request_type = "GET"
                response = self.sync_log_management_data(request_type, data, url)
                if response.get('ok'):
                    response_data = json.loads(response.get('data').decode('utf-8'))
                    # Original UTC time
                    utc_time_str = response_data["execution_summary"]["last_execution"]["date"]
                    utc_time = datetime.strptime(utc_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                    date = format_utc_datetime(utc_time, tzone=user_tz)
                    response_data["execution_summary"]["last_execution"]["date"] = date
                    response_data["enabled"] = "Enabled" if response_data["enabled"] else "Disabled"
                    response_data["interval"] = response_data["interval"].replace("s", " seconds").replace("m", " minutes").replace("h", " hours")
                    if response_data["type"] == "query":
                        response_data["rule_type"] = "Custom Query"
                    elif response_data["type"] == "esql":
                        response_data["rule_type"] = "ESQL"
                    else:
                        response_data["rule_type"] = "Threshold"
                    if response_data.get("severity", "") == "high":
                        response_data["severity"] = "Critical"
                    elif response_data.get("severity", "") == "medium":
                        response_data["severity"] = "Major"
                    elif response_data.get("severity", "") == "low":   
                        response_data["severity"] = "Minor"
                    response_data["execution_summary"]["last_execution"]["status"] = response_data["execution_summary"]["last_execution"]["status"].capitalize()
                    response_data["color_status"] = "green" if response_data["execution_summary"]["last_execution"]["status"] == "Succeeded" else "red"
                else:
                    response_data["status"] = "failed"
                    response_data["message"] = "Unable to connect to Logserver. Please contact administrator." if response.get("reason") == "Connection Error" else response.get("reason", "Failed to fetch rule execution result")
            return response_data
        except Exception as e:
            logger.exception("Error getting request data: %s", e)
            response_data["status"] = "failed"
            return response_data
        
        
    def get_associated_log_events(self, request):
        """
        Function to get associated log events based on the event data.
        :return: response_data dict
        """
        response_data = {}
        try:
            logger.info("Enter into get_associated_log_events function on LogIntegrationController.")
            request_data = self.get_query_params_data(request)
            user_tz = request_data.get("user_tz", "UTC")
            event_data = request_data.get('event_data', {})
            sortBy = request_data.get('sort','')
            order = request_data.get('reverse')
            page = request_data.get('page', 1)
            alarm_cause = request_data.get('alarm_cause', '')
            match = re.search(r"occurred\s+(\d+)\s+times", alarm_cause)
            match_count = 0
            if match:
                match_count = int(match.group(1))
            items_per_page = request_data.get('items_per_page', 10)
            if event_data:
                event_data = json.loads(event_data) if isinstance(event_data, str) else event_data
                index = event_data.get('indices', [])
                es_query = self.build_es_query(
                    kql_query=event_data.get('kql_query', ''),
                    threshold_terms=event_data.get('threshold_terms', {}),
                    time_from=event_data.get('time_from', ''),
                    time_to=event_data.get('time_to', '')
                )
                if order:
                    order = 'asc'
                else:
                    order = 'desc'
                page = safe_int(page)
                items_per_page = safe_int(items_per_page)
                if page == 1:
                    start_page = 1
                    offset = 0
                    size = items_per_page
                else:
                    start_page = items_per_page * (page - 1) + 1
                    offset = (page - 1) * items_per_page
                    size = (page + 1) * items_per_page
                log_count = self.elasticObj.get_elasticsearch_data(index, es_query, offset,size,order,sortBy,is_count=True)
                event_count,log_data = self.elasticObj.get_elasticsearch_data(index, es_query, offset,size,order,sortBy)
                if log_count > match_count:
                    log_count = match_count
                    log_data = log_data[:match_count]      
                for log in log_data:
                    timestamp = log.get('@timestamp','')
                    timestamp = timestamp[:26]
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    local_timezone = pytz.timezone(user_tz) 
                    timestamp = timestamp.replace(tzinfo=pytz.utc).astimezone(local_timezone)
                    log['@timestamp'] = timestamp.strftime("%a %d %b %Y, %I:%M %p")
                if event_count > 0:
                    response_data["status"] = "success"
                    response_data["event_count"] = log_count
                    response_data["log_data"] = log_data
                else:
                    response_data["status"] = "no_data"
                    response_data["message"] = "No associated log events found."
                
            logger.info("Exit from get_associated_log_events function on LogIntegrationController.")
        except Exception as e:
            logger.exception("Error getting associated log events: %s", e)
            response_data["status"] = "failed"
        return response_data
    
    def build_es_query(self, kql_query, threshold_terms, time_from, time_to):
        """
        Build an Elasticsearch query for fetching logs that triggered a Kibana threshold rule.
        Handles variable KQL queries by using query_string.
        Includes exception handling and logging.
        """
        filters = []
        try:
            logger.info("Building Elasticsearch query with KQL: %s, Threshold Terms: %s, Time From: %s, Time To: %s", kql_query, threshold_terms, time_from, time_to)
            # Time range filter
            try:
                filters.append({
                    "range": {
                        "@timestamp": {
                            "gte": time_from,
                            "lte": time_to
                        }
                    }
                })
            except Exception as msg:
                logger.exception("Exception in adding time range filter - %s" % msg)

            try:
                for field, value in (threshold_terms or {}).items():
                    filters.append({"term": {field: value}})
            except Exception as msg:
                logger.exception("Exception in adding threshold term filters - %s" % msg)

            # KQL query string
            must_clauses = []
            try:
                if kql_query:
                    must_clauses.append({
                        "query_string": {
                            "query": kql_query,
                            "default_operator": "AND"
                        }
                    })
            except Exception as msg:
                logger.exception("Exception in adding KQL query string - %s" % msg)

            # Final query
            try:
                query = {
                    "query": {
                        "bool": {
                            "filter": filters,
                            "must": must_clauses
                        }
                    }
                }
            except Exception as msg:
                logger.exception("Exception in building final query - %s" % msg)
                query = {}
            logger.info("Exit from build_es_query function on LogIntegrationController.")
        except Exception as msg:
            logger.exception("Exception in build_es_query - %s" % msg)
            query = {}

        return query

    def update_log_agent_assets(self, request):
        try:
            logger.info(f"Enter into update_log_agent_assets function on LogIntegrationController. organization_id : {self.get_organization_id(request)}")
            response_data = {}
            data = request
            agent_id = data.get('agent_id', "")
            org_id = data.get('org_id', "")
            action = data.get("log_agent",{}).get("action","")
            job_id = data.get("log_agent",{}).get("job_id","")
            if  agent_id not in self.noneList and org_id not in self.noneList:
                asset = CMDBCi.objects.filter(organization=org_id, is_deleted=False,ci_name="log_agent_status",agent_id=agent_id).first()
                serializers = CMDBCiSerializer(asset)
                asset_data = serializers.data
                if data.get("log_agent",{}).get("status","") not in self.noneList and data.get("log_agent",{}).get("status","") not in ["Service not installed","Running","Stopped"]:
                        data["log_agent"]["status"] = "Refresh The Status"
                if asset_data not in self.noneList:
                    asset_info = asset_data.get("asset_info", {})
                    asset_info['display_name_status'] ={}
                    asset_info["display_name_status"]["status"] = data.get("log_agent",{}).get("status","Error Occured")
                    asset_info['display_name_status']['msg'] = data.get("log_agent",{}).get("msg","").replace("winlogbeat","Log Agent").replace("Filebeat","Log Agent").replace("Winlogbeat","Log Agent").replace("filebeat","Log Agent")
                    asset_info['display_name_status']['last_update_time'] = dtime.datetime.now(pytz.timezone(get_setting_data("TIME_ZONE")))
                    asset_info['service_name_status'] ={}
                    asset_info["service_name_status"]["status"] = data.get("log_agent",{}).get("status","Error Occured")
                    asset_info['service_name_status']['msg'] = data.get("log_agent",{}).get("msg","").replace("winlogbeat","Log Agent").replace("Filebeat","Log Agent").replace("Winlogbeat","Log Agent").replace("filebeat","Log Agent")
                    asset_info['service_name_status']['last_update_time'] = dtime.datetime.now(pytz.timezone(get_setting_data("TIME_ZONE")))
                    if asset_info.get("job_id",None) not in self.noneList:
                        if asset_info.get("job_id","") == data.get("log_agent",{}).get("job_id",""):
                            asset_info['last_task_completed'] = True
                        else:
                            asset_info['last_task_completed'] = False
                    asset.asset_info = asset_info
                    if action in ['install','uploadConfig','checkConfig']:
                        log_agent_profile_data = LogAgentConfig.objects.filter(organization=org_id,inventory_agents__agent_id=agent_id, is_deleted=False)
                        log_agent_profile_data = LogAgentConfigSerializer(log_agent_profile_data,many=True).data
                        if isinstance(log_agent_profile_data, list):
                            if len(log_agent_profile_data) > 1:
                                log_agent_profile_data = [d for d in log_agent_profile_data if d.get("log_agent_id","") not in ["000000000000000000001","000000000000000000002"]]
                                log_agent_profile_data = log_agent_profile_data[0] if len(log_agent_profile_data)>0 else {}
                            else:
                                log_agent_profile_data = log_agent_profile_data[0] if len(log_agent_profile_data)>0 else {}
                        log_agent_profile_data = LogAgentConfig.objects.get(log_agent_id=log_agent_profile_data.get("log_agent_id",""),organization=org_id,is_deleted=False)
                        inventory_agent_data = log_agent_profile_data.inventory_agents
                        for agent in inventory_agent_data:
                            if agent.get("agent_id") == agent_id:
                                agent["last_config_validated_time"] = datetime.now(pytz.timezone('UTC'))
                                agent["configuration_error_msg"] = data.get("log_agent",{}).get("configuration_error_msg","")
                                agent['is_configuration_valid'] = True if data.get("log_agent",{}).get("is_configuration_valid","") == "success" else False
                        log_agent_profile_data['inventory_agents'] = inventory_agent_data
                        log_agent_profile_data.save()
                    try:
                        asset.save()
                    except Exception as e:
                        logger.exception(f"Error saving asset: {e} organization_id : {self.get_organization_id(request)}")
                    if data.get("log_agent",{}).get("data",[{}])[0].get("is_multiple_agent_action",False):
                        export_data_obj = ExportConfig.objects.get(
                            export_id=job_id,
                            organization=org_id,
                            type="Inventory",
                        )
                        export_data = ExportConfigsListSerializer(export_data_obj).data
                        agent_data_list = export_data.get("data",[])
                        msg_map ={
                            "install":
                            {
                                
                                "success":["LogAgent service started successfully",
                                           "Mdules enabled successfully",
                                           "Modules enabled successfully"
                                        ],
                                "failed":[
                                    "No organization data found",
                                    "Unsupported OS","Log agent download failed",
                                    "MSI file not found",
                                    "Admin privileges required to execute MSI installer",
                                    "MSI installation failed",
                                    "Unexpected MSI error",
                                    "Winlogbeat configuration file not found after installation",
                                    "Winlogbeat service not found after installation",
                                    "Config rename error",
                                    "Config rewrite error",
                                    "Admin privileges required for config file operations.",
                                    "Unexpected config error",
                                    "Service installed but did not start",
                                    "Admin privileges required to install or start service.",
                                    "Service install error",
                                    "Service not installed",
                                    "Service enabled but did not start"
                                    ],
                                "config_error":["Config validation error","Configuration is not valid","Config validation failed"]
                            },
                            "uploadConfig":
                            {
                                
                                "success":["Configuration uploaded successfully","Configuration is valid","Configuration updated successfully"],
                                "failed":[
                                    "Configuration upload failed",
                                    "Config validation failed",
                                    "Config rewrite error",
                                    "Admin privileges required for config file operations.",
                                    "Unexpected config error"
                                    ],
                                "config_error":["Config validation error","Configuration is not valid","Config validation failed"]
                            },
                            "checkConfig":
                            {
                                "success":["Configuration is valid","Configuration is valid for"],
                                "failed":[
                                    "Winlogbeat executable not found at",
                                    "Configuration is not valid",
                                    "Filebeat config validation timeout after 30 seconds.",
                                    "Filebeat executable not found in any standard location.",
                                    "Configuration file not found",
                                    "Configuration file not found",
                                    "Configuration is not valid",
                                    "Config validation failed",
                                    "Filebeat config is valid",
                                    "An unexpected error occurred"
                                    ],
                                "config_error":["Config validation error"]
                            },
                            "start":
                            {
                                "success":["LogAgent service started successfully","started successfully","Log Agent is running"],
                                "failed":[
                                    "already running",
                                    "Failed to start service",
                                    "MSI file not found",
                                    "Log Agent is stopped",
                                    "Service started but not active",
                                    "Start timeout error",
                                    "Refresh to Check Status",
                                    "Service install error",
                                    "Service not installed",
                                    "Service enabled but did not start"
                                    ],
                                "config_error":[]
                            },
                            "stop":
                            {
                                "success":["LogAgent service stopped successfully","Log Agent is stopped","Stopped via kill"],
                                "failed":[
                                    "Service stop error",
                                    "Service not stopped",
                                    "Admin privileges required to stop service.",
                                    "Failed to stop","Stop timeout"
                                    ],
                                "config_error":[]
                            },
                            "restart":
                            {
                                "success":["LogAgent service restarted successfully"],
                                "failed":[
                                    "Service restart error",
                                    "Service not restarted",
                                    "Admin privileges required to restart service."
                                    ],
                                "config_error":[]
                            },
                            "uninstall":
                            {
                                "success":["Log agent uninstalled successfully"],
                                "failed":[
                                    "Service uninstall error",
                                    "Service not uninstalled",
                                    "Admin privileges required to uninstall service.",
                                    "Failed to uninstall log agent app",
                                    "Exception in Uninstalling LogAgent",
                                    "Error removing filebeat"
                                    ],
                                "config_error":[]
                            }
                        }
                        for agent_data in agent_data_list:
                            if agent_data.get("agent_id",None) == agent_id:
                                agent_data["log_agent_status"] = data.get("log_agent",{}).get("status","")
                                agent_data["log_agent_message"] = data.get("log_agent",{}).get("msg","")
                                agent_data["log_agent_config_message"] = data.get("log_agent",{}).get("configuration_error_msg","")
                                agent_data["log_agent_config_status"] = True if data.get("log_agent",{}).get("is_configuration_valid","") == "success" else False
                                log_agent_msg = data.get("log_agent", {}).get("msg", "")
                                log_agent_action = data.get("log_agent", {}).get("action", "")
                                if log_agent_action in ["uploadConfig","checkConfig"]:
                                    log_agent_msg = data.get("log_agent", {}).get("configuration_error_msg", "")
                                if log_agent_action in msg_map:
                                    msg_map = msg_map.get(log_agent_action,{})
                                if any(key in log_agent_msg for key in msg_map.get("success", [])):
                                    agent_data["job_status"] = "Success"
                                    agent_data['job_message'].append(log_agent_msg)
                                elif any(key in log_agent_msg for key in msg_map.get("failed", [])):
                                    agent_data["job_status"] = "Failed"
                                    agent_data['job_message'].append(log_agent_msg)
                                elif any(key in log_agent_msg for key in msg_map.get("config_error", [])):
                                    agent_data["job_status"] = "Config_error"
                                    agent_data["log_agent_config_status"] = False
                                    agent_data["log_agent_config_message"] = data.get("log_agent",{}).get("configuration_error_msg","")
                                    agent_data['job_message'].append(data.get("log_agent",{}).get("configuration_error_msg",""))
                                else:
                                    agent_data["job_status"] = "Failed"
                                    agent_data['job_message'].append(log_agent_msg)
                                export_data_obj.data = agent_data_list
                                export_data_obj.save()
                                break
            response_data["status"] = "success"
            response_data["message"] = "Log agent assets updated successfully."
            logger.info(f"Exit from update_log_agent_assets function on LogIntegrationController. organization_id : {self.get_organization_id(request)}")
        except Exception as e:
            logger.exception(f"Error updating log agent assets: {e} organization_id : {self.get_organization_id(request)}")
            response_data["status"] = "failed"
            response_data["message"] = "Failed to update log agent assets."
        return response_data
    
    def get_devices_data(self, request):
        """
        Return device data for log-grid sidebar
        Columns:
        - IP Address
        - Hostname
        - Device Type
        - Logs/sec (only for UP devices)
        """
        response_data = {
            "count": 0,
            "results": []
        }  
        try:
            req_data = self.get_query_params_data(request)
            organization_id = self.get_organization_id(request)
            ip_list = req_data.get("log_device_ip_list", [])
            node_status = req_data.get("log_device_status", "")
            from_download = safe_int(req_data.get("from_download", 0))
            page = safe_int(req_data.get("page", 1))
            items_per_page = safe_int(req_data.get("items_per_page", 25))
            if not ip_list:
                return response_data
            # Fetch devices from CMDB
            devices = CMDBCi.objects(
                ip_address__in=ip_list,
                organization=organization_id,
                object_type="Node",
                is_deleted=False,
                is_enabled=True,
                is_logmanagement_enabled=True
            ).only(
                "ci_id",
                "ip_address",
                "ci_name",
                "device_type",
                "common_info"
            )
            device_rows = []
            for device in devices:
                operational_status = ""
                common_info = getattr(device, "common_info", None)
                if common_info:
                    op_status = getattr(common_info, "operational_status", None)
                    if isinstance(op_status, dict):
                        operational_status = op_status.get("name", "")
                    else:
                        operational_status = getattr(op_status, "name", "")
                device_rows.append({
                    "ci_id": str(device.ci_id),
                    "ip_address": device.ip_address,
                    "host_name": device.ci_name or "",
                    "device_type": device.device_type or "",
                    "operational_status": operational_status,
                    "logs_per_sec": None,
                    "last_log_time":None
                })
            es = None
            if node_status in ("up", "down") or from_download == 1:
                es = self.elasticObj.get_elasticsearch_connection()
            # Logs/sec calculation for UP devices or last log time for DOWN devices
            if node_status == "up":
                extra_filters = req_data.get("extraFilters", {})
                time_filter = extra_filters.get("time_filters", {})
                start_time = time_filter.get("start_time")
                end_time = time_filter.get("end_time")
                if not start_time or not end_time:
                    for row in device_rows:
                        row["logs_per_sec"] = "0.0 logs/sec"
                else:
                    start_time = parser.parse(start_time)
                    end_time = parser.parse(end_time)
                    time_window_seconds = int((end_time - start_time).total_seconds())
                    if time_window_seconds <= 0:
                        time_window_seconds = 1
                    start_time = start_time.replace(tzinfo=timezone.utc)
                    end_time = end_time.replace(tzinfo=timezone.utc)
                    es_query = {
                        "size": 10000,
                            "query": {
                                "bool": {
                                    "must": [
                                        {
                                            "range": {
                                                "@timestamp": {
                                                    "format": "strict_date_optional_time",
                                                    "gte": start_time.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                                                    "lte": end_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")
                                                }
                                            }
                                        }
                                    ],
                                    "filter": [
                                        {
                                            "terms": {
                                                "host.ip": ip_list
                                            }
                                        },
                                        {
                                            "term": {
                                                "event.organization": organization_id
                                            }
                                        }
                                    ]
                                }
                            },
                            "aggs": {
                                "1": {
                                    "terms": {
                                        "field": "host.ip.keyword",
                                        "size": 10000
                                    }
                                }
                            },
                            "sort": [
                                {
                                    "@timestamp": {
                                        "order": "desc"
                                    }
                                }
                            ]
                        }
                    es_response = es.search(index="*", body=es_query)
                    buckets = (
                        es_response
                        .get("aggregations", {})
                        .get("1", {})
                        .get("buckets", [])
                    )
                    ip_log_map = {b["key"]: b["doc_count"] for b in buckets}
                    # Calculate logs/sec
                    for row in device_rows:
                        ip = row["ip_address"]
                        log_count = ip_log_map.get(ip, 0)
                        logs_per_sec = round(log_count / time_window_seconds, 2)    
                        row["logs_per_sec"] = f"{logs_per_sec} logs/sec"
            elif node_status == "down":
                index_name = req_data.get("log_index_pattern", [])
                if index_name:
                    index_name = [i.get("key") + "*" for i in index_name]
                else:
                    index_name = "*"
                es_query = {
                    "size": 0,
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "terms": {
                                        "host.ip": ip_list
                                    }
                                },
                                {
                                    "term": {
                                        "event.organization": organization_id
                                    }
                                }
                            ]
                        }
                    },
                    "aggs": {
                        "by_ip": {
                            "terms": {
                                "field": "host.ip.keyword",
                                "size": 10000
                            },
                            "aggs": {
                                "last_seen": {
                                    "max": {
                                        "field": "@timestamp"
                                    }
                                }
                            }
                        }
                    }
                }
                es_response = es.search(index="*", body=es_query)
                buckets = (
                    es_response
                    .get("aggregations", {})
                    .get("by_ip", {})
                    .get("buckets", [])
                )
                ip_last_seen_map = {
                    b["key"]: b["last_seen"].get("value_as_string")
                    for b in buckets
                }
                tz_name = req_data.get("user_tz") or "UTC"
                user_tz = pytz.timezone(tz_name)
                for row in device_rows:
                    ip = row["ip_address"]
                    row["logs_per_sec"] = "-"
                    last_seen_utc = ip_last_seen_map.get(ip)
                    if last_seen_utc:
                        dt_utc = parser.isoparse(str(last_seen_utc))
                        # user_tz = pytz.timezone(req_data.get("user_tz","UTC"))
                        dt_user = dt_utc.astimezone(user_tz)
                        row["last_log_time"] = dt_user.strftime("%b %d, %Y %I:%M %p")
                    else:
                        row["last_log_time"] = "-"
            for row in device_rows:
                row["logs_per_sec"] = row.get("logs_per_sec") or "-"
                row["last_log_time"] = row.get("last_log_time") or "-"
            # Search functionality
            search_query = req_data.get('search_filter')
            if isinstance(search_query, str) and search_query.strip():
                search_query = search_query.strip().lower()
                device_rows = [
                    item for item in device_rows
                    if search_query in (item.get("ip_address") or "").lower()
                    or search_query in (item.get("host_name") or "").lower()
                    or search_query in (item.get("device_type") or "").lower()
                ]
                page = 1
            # Sorting
            sort_by = req_data.get("sort", "")
            reverse = bool(req_data.get("reverse"))
            if sort_by == "host.name.keyword":
                device_rows.sort(
                    key=lambda row: (row.get("host_name") or "").lower(),
                    reverse=reverse
                )
            elif sort_by == "host.ip.keyword":
                device_rows.sort(
                    key=lambda row: str(row.get("ip_address") or ""),
                    reverse=reverse
                )
            elif sort_by == "device_type":
                device_rows.sort(
                    key=lambda row: (row.get("device_type") or "").lower(),
                    reverse=reverse
                )
            # Export
            if from_download == 1:
                return {
                    "count": len(device_rows),  
                    "results": device_rows
                }
            #Pagination
            total_items = len(device_rows)
            offset = (page - 1) * items_per_page
            paginated_data = device_rows[offset: offset + items_per_page]
            response_data.update({
                "count": total_items,
                "results": paginated_data,
                "next": page + 1 if offset + items_per_page < total_items else '',
                "previous": page - 1 if page > 1 else '',
            })
            logger.info(f"Exit from get_devices_data function. organization_id : {self.get_organization_id(request)}")
            return response_data        
        except Exception as e:
            logger.exception(f"Error in getting devices data: {e} organization_id : {self.get_organization_id(request)}")
            return response_data