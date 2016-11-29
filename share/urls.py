from django.conf.urls import patterns, url
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from share.views.region_provider_view import *

urlpatterns = patterns(
    '',
    url(r'^$', login_required(RegionOverviewView.as_view())),
    url(r'^region/$', login_required(RegionOverviewView.as_view())),
    url(r'^region/price/$', login_required(RegionResourcePriceView.as_view())),
    url(r'^region/report/consume/$', login_required(RegionResourceConsumeView.as_view())),
)
