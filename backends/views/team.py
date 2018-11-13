# -*- coding: utf8 -*-
import logging
import operator
import json

from rest_framework.response import Response
from django.db import connection

from backends.services.exceptions import *
from backends.services.resultservice import *
from backends.services.tenantservice import tenant_service
from backends.services.userservice import user_service
from backends.services.regionservice import region_service
from console.services.team_services import team_services as console_team_service
from base import BaseAPIView
from goodrain_web.tools import JuncheePaginator
from www.models import Tenants, PermRelTenant
from console.services.enterprise_services import enterprise_services
from console.services.perm_services import perm_services as console_perm_service
from console.services.region_services import region_services as console_region_service
from django.db import transaction
from console.services.team_services import team_services
from console.repositories.app import service_repo
from www.services import app_group_svc
from console.repositories.user_repo import user_repo
from www.service_http import RegionServiceApi
from backends.services.httpclient import HttpInvokeApi
from console.repositories.region_repo import region_repo

logger = logging.getLogger("default")
http_client = HttpInvokeApi()
regionClient = RegionServiceApi()


class AllTeamView(BaseAPIView):
    def get(self, request, *args, **kwargs):
        """
        获取团队信息
        ---
        parameters:
            - name: page_num
              description: 页码
              required: false
              type: string
              paramType: query
            - name: page_size
              description: 每页数量
              required: false
              type: string
              paramType: query
            - name: enterprise_alias
              description: 企业别名
              required: false
              type: string
              paramType: query
            - name: tenant_alias
              description: 团队别名
              required: false
              type: string
              paramType: query
            - name: tenant_name
              description: 团队名称
              required: false
              type: string
              paramType: query

        """
        try:
            page = request.GET.get("page_num", 1)
            page_size = request.GET.get("page_size", 20)
            enterprise_alias = request.GET.get("enterprise_alias", None)
            tenant_alias = request.GET.get("tenant_alias", None)
            tenant_name = request.GET.get("tenant_name", None)
            if enterprise_alias:
                enter = enterprise_services.get_enterprise_by_enterprise_alias(enterprise_alias)
                if not enter:
                    return Response(
                        generate_result("0404", "enterprise is not found", "企业{0}不存在".format(enterprise_alias)))
            # if tenant_alias:
            #     team = console_team_service.get_team_by_team_alias(tenant_alias)
            #     if not team:
            #         return Response(
            #             generate_result("0404", "team is not found", "团队别名{0}不存在".format(tenant_alias)))
            if tenant_name:
                team = console_team_service.get_tenant_by_tenant_name(tenant_name)
                if not team:
                    return Response(
                        generate_result("0404", "team is not found", "团队名称{0}不存在".format(tenant_name)))
            cursor = connection.cursor()
            cursor.execute(
                "select * from tenant_info")
            tenant_tuples = cursor.fetchall()
            tenant_list = []
            # tenant_list = [(), (), ()]
            # 通过别名来搜索团队
            if tenant_alias:
                for tenant_tuple in tenant_tuples:
                    if tenant_alias in tenant_tuple[13]:
                        tenant_list.append(tenant_tuple)
            else:
                for tenant_tuple in tenant_tuples:
                    tenant_list.append(tenant_tuple)
            # 分页
            tenant_paginator = JuncheePaginator(tenant_list, int(page_size))
            tenants = tenant_paginator.page(int(page))
            logger.debug('lllllllllllllllllll{0}'.format(tenants))
            tenants_num = Tenants.objects.count()

            try:
                # 查询所有团队有哪些数据中心
                region_list = []
                for tenant in tenants:
                    tenant_id = tenant[1]
                    tenant_region_list = tenant_service.get_all_tenant_region_by_tenant_id(tenant_id)
                    if len(tenant_region_list) != 0:
                        for tenant_region in tenant_region_list:
                            region_list.append(tenant_region.region_name)
                region_lists = list(set(region_list))
            except Exception as e:
                logger.exception(e)
                result = generate_result("1111", "2.faild", "{0}".format(e.message))
                return Response(result)

            tenant_info = {}
            logger.debug("region_lists", region_lists)
            try:
                resources_dicts = {}
                for region_name in region_lists:

                    region_obj = region_repo.get_region_by_region_name(region_name)
                    if not region_obj:
                        continue
                    tenant_name_list = []
                    for tenant in tenants:
                        if tenant[3] == region_name:
                            tenant_name_list.append(tenant[2])
                    # 获取数据中心下每个团队的使用资源
                    res, body = http_client.get_tenant_limit_memory(region_obj, json.dumps({"tenant_name": tenant_name_list}))
                    logger.debug("======111===={0}".format(body))
                    if int(res.status) >= 400:
                        continue
                    if not body.get("list"):
                        continue
                    tenant_resources_list = body.get("list")

                    logger.debug('111111111111111{0}'.format(tenant_resources_list))

                    tenant_resources_dict = {}
                    for tenant_resources in tenant_resources_list:

                        tenant_resources_dict[tenant_resources["tenant_id"]] = tenant_resources
                    # tenant_resources_dict = {id:{}, id:{}}
                    try:
                        for tenant in tenants:

                            tenant_region = {}
                            tenant_id = tenant[1]
                            if tenant_id in tenant_resources_dict:
                                # tenant_region["name1"] = {"cpu_total":0, "cpu_use":0}
                                tenant_region[region_obj.region_alias] = tenant_resources_dict[tenant_id]
                                if tenant_id not in resources_dicts:
                                    resources_dicts[tenant_id] = {"resources": tenant_region}
                                else:
                                    resources_dicts[tenant_id]["resources"].update(tenant_region)
                    except Exception as e:
                        logger.exception(e)
                        result = generate_result("1111", "2.5-faild", "{0}".format(e.message))
                        return Response(result)
            except Exception as e:
                logger.exception(e)
                result = generate_result("1111", "2.6-faild", "{0}".format(e.message))
                return Response(result)
            try:
                run_app_num_dicts = {}
                for region_name in region_lists:

                    region_obj = region_repo.get_region_by_region_name(region_name)
                    if not region_obj:
                        continue
                    # 获取数据中心下每个团队的运行的应用数量
                    ret, data = http_client.get_tenant_service_status(region_obj)
                    logger.debug("=========", ret, data)
                    if int(ret.status) >= 400:
                        continue

                    for tenant in tenants:
                        tenant_id = tenant[1]
                        if tenant_id in data.get("bean"):
                            run_app_num = data["bean"][tenant_id]["service_running_num"]
                            logger.debug(run_app_num)
                            if tenant_id not in run_app_num_dicts:
                                run_app_num_dicts[tenant_id] = {"run_app_num": [run_app_num]}
                            else:
                                run_app_num_dicts[tenant_id]["run_app_num"].append(run_app_num)
            except Exception as e:
                logger.exception(e)
                result = generate_result("1111", "2.7-faild", "{0}".format(e.message))
                return Response(result)

            for tenant in tenants:
                # 为每个团队拼接信息
                tenant_id = tenant[1]
                tenant_info[tenant_id] = {}
                for key in run_app_num_dicts:
                    if key == tenant_id:
                        tenant_info[tenant_id]["run_app_num"] = run_app_num_dicts[key]["run_app_num"]
                for key in resources_dicts:
                    if key == tenant_id:
                        tenant_info[tenant_id]["resources"] = resources_dicts[key]["resources"]

                total_app = service_repo.get_services_by_tenant_id(tenant_id)
                tenant_info[tenant_id]["total_app"] =  total_app

                user_list = tenant_service.get_tenant_users(tenant[2])
                tenant_info[tenant_id]["user_num"] = len(user_list)

                creater = user_service.get_creater_by_user_id(tenant[8])
                if not creater:
                    tenant_info[tenant_id]["tenant_creater"] = ''
                else:
                    tenant_info[tenant_id]["tenant_creater"] = creater.nick_name
                tenant_info[tenant_id]["pay_type"] = tenant[5]
                tenant_info[tenant_id]["update_time"] = tenant[10]
                tenant_info[tenant_id]["tenant_alias"] = tenant[13]
                tenant_info[tenant_id]["pay_level"] = tenant[11]
                tenant_info[tenant_id]["tenant_name"] = tenant[2]
                tenant_info[tenant_id]["region"] = tenant[3]
                tenant_info[tenant_id]["is_active"] = tenant[4]
                tenant_info[tenant_id]["create_time"] = tenant[7]
                tenant_info[tenant_id]["expired_time"] = tenant[12]
                tenant_info[tenant_id]["limit_memory"] = tenant[9]
                tenant_info[tenant_id]["enterprise_id"] = tenant[14]
                tenant_info[tenant_id]["balance"] = tenant[6]
                tenant_info[tenant_id]["ID"] = tenant[0]
            # 需要license控制，现在没有，默认为一百万
            allow_num = 1000000
            list1 = []
            bean = {"tenants_num": tenants_num, "allow_num": allow_num}
            for val in tenant_info.values():
                list1.append(val)
            list1.sort(key=operator.itemgetter('total_app'), reverse=True)
            result = generate_result(
                "0000", "success", "查询成功", bean=bean, list=list1, total=tenant_paginator.count
            )
            return Response(result)
        except Exception as e:
            result = generate_result("1111", "4.faild", "{0}".format(e.message))
            return Response(result)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """
        添加团队
        ---
        parameters:
            - name: tenant_name
              description: 团队名
              required: true
              type: string
              paramType: form
            - name: enterprise_id
              description: 企业ID
              required: true
              type: string
              paramType: form
            - name: useable_regions
              description: 可用数据中心 ali-sh,ali-hz
              required: false
              type: string
              paramType: form
        """
        sid = None
        try:
            tenant_name = request.data.get("tenant_name", None)
            if not tenant_name:
                return Response(generate_result("1003", "team name is none", "团对名称不能为空"))
            enterprise_id = request.data.get("enterprise_id", None)
            if not enterprise_id:
                return Response(generate_result("1003", "enterprise id is none", "企业ID不能为空"))
            enter = enterprise_services.get_enterprise_by_enterprise_id(enterprise_id)
            if not enter:
                return Response(generate_result("0404", "enterprise not found", "企业在云帮不存在"))

            team = console_team_service.get_team_by_team_alias_and_eid(tenant_name, enterprise_id)
            if team:
                return Response(generate_result("0409", "team alias is exist", "团队别名{0}在该企业已存在".format(tenant_name)))

            creater = request.data.get("creater", None)
            if not creater:
                return Response(generate_result("0412", "please specify owner", "请指定拥有者"))
            user = user_repo.get_user_by_username(creater)
            useable_regions = request.data.get("useable_regions", "")
            logger.debug("team name {0}, usable regions {1}".format(tenant_name, useable_regions))
            regions = []
            if useable_regions:
                regions = useable_regions.split(",")
            # 开启保存点
            sid = transaction.savepoint()
            code, msg, team = console_team_service.create_team(user, enter, regions, tenant_name)
            # 创建用户在团队的权限
            perm_info = {
                "user_id": user.user_id,
                "tenant_id": team.ID,
                "identity": "owner",
                "enterprise_id": enter.pk
            }
            console_perm_service.add_user_tenant_perm(perm_info)

            for r in regions:
                code, msg, tenant_region = console_region_service.create_tenant_on_region(team.tenant_name, r)
                if code != 200:
                    logger.error(msg)
                    if sid:
                        transaction.savepoint_rollback(sid)
                    return Response(generate_result("0500", "add team error", msg), status=code)

            transaction.savepoint_commit(sid)

            bean = {"tenant_name": team.tenant_name, "tenant_id": team.tenant_id, "tenant_alias": team.tenant_alias,
                    "user_num": 1}
            result = generate_result("0000", "success", "租户添加成功", bean=bean)
        except TenantOverFlowError as e:
            result = generate_result("7001", "tenant over flow", "{}".format(e.message))
        except TenantExistError as e:
            result = generate_result("7002", "tenant exist", "{}".format(e.message))
        except NoEnableRegionError as e:
            result = generate_result("7003", "no enable region", "{}".format(e.message))
        except UserNotExistError as e:
            result = generate_result("7004", "not user", "{}".format(e.message))
        except Exception as e:
            logger.exception(e)
            if sid:
                transaction.savepoint_rollback(sid)
            result = generate_error_result()
        return Response(result)

    def delete(self, request, *args, **kwargs):
        """
        删除团队
        ---
        parameters:
            - name: team_name
              description: 要删除的团队
              required: true
              type: string
              paramType: path
        """
        tenant_name = request.data.get("tenant_name", None)
        if not tenant_name:
            return Response(generate_result("1003", "team name is none", "参数缺失"))

        try:
            service_count = team_services.get_team_service_count_by_team_name(team_name=tenant_name)
            if service_count >= 1:
                result = generate_result("0404", "failed", "当前团队内有应用,不可以删除")
                return Response(result)
            status = team_services.delete_tenant(tenant_name=tenant_name)
            if not status:
                result = generate_result("0000", "success", "删除团队成功")
            else:
                result = generate_result("1002", "delete a tenant failed", "删除团队失败")
        except Tenants.DoesNotExist as e:
            logger.exception(e)
            result = generate_result("1004", "tenant not exist", "{}团队不存在".format(tenant_name))
        except Exception as e:
            result = generate_result("9999", "sys exception", "系统异常")
            logger.exception(e)
        return Response(result)


class TeamView(BaseAPIView):
    def get(self, request, tenant_name, *args, **kwargs):
        """
        获取某指定团队信息
        ---
        parameters:
            - name: tenant_name
              description: 团队名称
              required: true
              type: string
              paramType: path

        """
        try:
            tenant = tenant_service.get_tenant(tenant_name)
            create_id = tenant.creater
            user = user_service.get_user_by_user_id(create_id)
            user_list = tenant_service.get_users_by_tenantID(tenant.ID)
            user_num = len(user_list)
            rt_list = [{"tenant_id": tenant.tenant_id, "tenant_name": tenant.tenant_name, "user_num": user_num,
                        "tenant_alias": tenant.tenant_alias, "creater": user.nick_name}]
            result = generate_result("0000", "success", "查询成功", list=rt_list)
        except Tenants.DoesNotExist as e:
            logger.exception(e)
            result = generate_result("1001", "tenant not exist", "租户{}不存在".format(tenant_name))
        except Exception as e:
            logger.exception(e)
            result = generate_result("9999", "system error", "系统异常")
        return Response(result)


class TeamUserView(BaseAPIView):
    def get(self, request, tenant_name, user_name, *args, **kwargs):
        """
        查询某团队下的某个用户
        ---
        parameters:
            - name: tenant_name
              description: 团队名
              required: true
              type: string
              paramType: path
            - name: user_name
              description: 用户名
              required: true
              type: string
              paramType: path
        """
        try:
            user = user_service.get_user_by_username(user_name)
            tenant = tenant_service.get_tenant(tenant_name)
            perm_tenants = PermRelTenant.objects.filter(tenant_id=tenant.ID, user_id=user.pk)
            if not perm_tenants:
                result = generate_result("1010", "tenant user not exist",
                                         "租户{0}下不存在用户{1}".format(tenant_name, user_name))
            else:
                code = "0000"
                msg = "success"
                list = []
                res = {"tenant_id": tenant.tenant_id, "tenant_name": tenant.tenant_name, "user_id": user.user_id,
                       "nick_name": user.nick_name, "email": user.email, "phone": user.phone}
                list.append(res)
                result = generate_result(code, msg, "查询成功", list=list)
        except UserNotExistError as e:
            result = generate_result("1008", "user not exist", e.message)
        except Tenants.DoesNotExist as e:
            logger.exception(e)
            result = generate_result("1001", "tenant not exist", "租户{}不存在".format(tenant_name))
        except Exception as e:
            logger.exception(e)
            result = generate_result("9999", "system error", "系统异常")
        return Response(result)


class AddTeamUserView(BaseAPIView):
    def post(self, request, tenant_name, *args, **kwargs):
        """
        为团队添加用户
        ---
        parameters:
            - name: tenant_name
              description: 团队名
              required: true
              type: string
              paramType: path
            - name: user_name
              description: 用户名
              required: true
              type: string
              paramType: form
            - name: identity
              description: 权限
              required: true
              type: string
              paramType: form
        """
        try:
            user_name = request.data.get("user_name", None)
            if not user_name:
                return Response(generate_result("1003", "username is null", "用户名不能为空"))
            identity = request.data.get("identity", "viewer")
            if not identity:
                return Response(generate_result("1003", "identity is null", "用户权限不能为空"))

            user = user_service.get_user_by_username(user_name)
            tenant = tenant_service.get_tenant(tenant_name)
            enterprise = enterprise_services.get_enterprise_by_id(tenant.enterprise_id)
            tenant_service.add_user_to_tenant(tenant, user, identity, enterprise)
            result = generate_result("0000", "success", "用户添加成功")
        except PermTenantsExistError as e:
            result = generate_result("1009", "permtenant exist", e.message)
        except UserNotExistError as e:
            result = generate_result("1008", "user not exist", e.message)
        except Tenants.DoesNotExist as e:
            logger.exception(e)
            result = generate_result("1001", "tenant not exist", "租户{}不存在".format(tenant_name))
        except Exception as e:
            logger.exception(e)
            result = generate_result("9999", "system error", "系统异常")
        return Response(result)


class TeamUsableRegionView(BaseAPIView):

    def get(self, request, tenant_name, *args, **kwargs):
        """
        获取团队可用的数据中心
        ---
        parameters:
            - name: tenant_name
              description: 团队名
              required: true
              type: string
              paramType: path
        """
        region_name = None
        try:
            team = console_team_service.get_tenant_by_tenant_name(tenant_name)
            if not team:
                return Response(generate_result("0404", "team not found", "团队{0}不存在".format(tenant_name)))

            region_list = console_region_service.get_region_list_by_team_name(request, tenant_name)
            if region_list:
                region_name = region_list[0]["team_region_name"]
            else:
                regions = region_service.get_all_regions()
                if regions:
                    region_name = regions[0].region_name
            result = generate_result("0000", "success", "查询成功", bean={"region_name": region_name})
        except Exception as e:
            logger.exception(e)
            result = generate_result("9999", "system error", "系统异常")
        return Response(result)


class TenantSortView(BaseAPIView):
    """企业下团队排行（根据人数+应用数）"""

    def get(self, request, *args, **kwargs):

        enterprise_id = request.GET.get("enterprise_id", None)
        if enterprise_id:
            enter = enterprise_services.get_enterprise_by_enterprise_id(enterprise_id)
            if not enter:
                return Response(
                    generate_result("0404", "enterprise is not found", "企业不存在"))
            try:
                tenant_list = tenant_service.get_team_by_name_or_alias_or_enter(tenant_name=None, tenant_alias=None,
                                                                                enterprise_id=enterprise_id)
                bean = {}
                bean["tenant_num"] = len(tenant_list)
                user_list = app_group_svc.get_users_by_eid(enterprise_id)
                bean["user_num"] = len(user_list)
                tenant_dict = {}
                for tenant in tenant_list:
                    user_list = tenant_service.get_tenant_users(tenant.tenant_name)
                    service_list = service_repo.get_tenant_services(tenant.tenant_id)
                    total = len(user_list) + len(service_list)
                    tenant_dict[tenant.tenant_alias] = [total]
                    tenant_dict[tenant.tenant_alias].append(len(user_list))
                    # 根据应用数加用户数倒序
                sort_list = sorted(tenant_dict.items(), key=lambda item: item[1], reverse=True)
                result = generate_result('0000', 'success', '查询成功', list=sort_list, bean=bean)
            except Exception as e:
                logger.exception(e)
                result = generate_result('9999', 'system error', '系统异常')
            return Response(result)
        else:
            result = generate_result("1003", "the enterprise alias cannot be empty", "企业别名不能为空")
            return Response(result)
