# -*- coding: utf-8 -*-
# Copyright (c) 2011-2012 Parisson SARL

# This software is a computer program whose purpose is to backup, analyse,
# transcode and stream any audio content with its metadata over a web frontend.

# This software is governed by the CeCILL  license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".

# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.

# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.

# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL license and that you accept its terms.
#
# Authors: Guillaume Pellerin <yomguy@parisson.com>

from django import template
from django.utils.http import urlquote
from django.core.urlresolvers import reverse
from django.utils import html
from django import template
from django.utils.text import capfirst
from django.utils.translation import ungettext
from docutils.core import publish_parts
from django.utils.encoding import smart_str, force_unicode
from django.utils.safestring import mark_safe
from django import db
from django.shortcuts import get_object_or_404
import re
import os
import datetime
from django.conf import settings
from django.template.defaultfilters import stringfilter
import django.utils.timezone as timezone
from timezones.utils import localtime_for_timezone
from django.utils.translation import ugettext_lazy as _
from urlparse import urlparse

from teleforma.models.core import Document
from teleforma.models.crfpa import Course, NewsItem
from teleforma.views import get_courses
from teleforma.models import *
from teleforma.exam.models import *

register = template.Library()

# more translations for template variables
title = _('General tweeter')
title = _('Local tweeter')

class TeleFormaVersionNode(template.Node):
    def render(self, context):
        from teleforma import __version__
        return __version__

@register.tag
def teleforma_version(parser, token):
    "Get TeleForma version number"
    return TeleFormaVersionNode()

@register.filter
def parse_urls(text):
    output = ''
    for block in text.split(' '):
        if 'http://' in block:
            output += '<a href="' + block + '">' + block + '</a>'
        else:
            output += block
    return output


@register.tag
def value_from_settings(parser, token):
    try:
        # split_contents() knows not to split quoted strings.
        tag_name, var = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires a single argument" % token.contents.split()[0]
    return ValueFromSettings(var)

class ValueFromSettings(template.Node):
    def __init__(self, var):
        self.arg = template.Variable(var)
    def render(self, context):
        return settings.__getattr__(str(self.arg))

@register.filter
def user_courses(user):
    return get_courses(user)

@register.filter
def to_recipients(users):
    list = []
    for user in users:
        list.append(user.username)
    return ':'.join(list)

@register.filter
def localtime(value, timezone):
    return localtime_for_timezone(value, timezone)

@register.filter
def or_me(value, arg):
    """
    Replace the value by a fixed pattern, if it equals the argument.

    Typical usage: sender|or_me:user

    """
    if not isinstance(value, (unicode, str)):
        value = unicode(value)
    if not isinstance(arg, (unicode, str)):
        arg = unicode(arg)
    return _('me') if value == arg else value

@register.filter
def yes_no(bool):
    if bool:
        return _('Yes')
    else:
        return _('No')

@register.filter
def from_course_type(contents, type):
    if contents:
        return contents.filter(course_type=type)

@register.filter
def from_doc_type(contents, type):
    if contents:
        return contents.filter(type=type)

@register.filter
def from_period(contents, period):
    if contents:
        if type(contents[0]) == Document:
            return contents.filter(periods__in=(period,))
        else:
            return contents.filter(period=period)

@register.assignment_tag
def get_all_professors():
    return Professor.objects.all()

@register.assignment_tag
def get_all_admins():
    return User.objects.filter(is_superuser=True).order_by('last_name')

@register.assignment_tag
def get_all_trainings():
    return Training.objects.all()

@register.assignment_tag
def get_all_iejs():
    return IEJ.objects.all()

@register.assignment_tag
def get_all_courses():
    return Course.objects.all()

@register.assignment_tag
def get_telecaster():
    return 'telecaster' in settings.INSTALLED_APPS

@register.assignment_tag
def get_googletools():
    return 'googletools' in settings.INSTALLED_APPS

@register.filter
def get_audio_id(media):
    if media.conference:
        medias = media.conference.media.all()
        for m in medias:
            if 'audio' in m.mime_type:
                return m.id
    return

@register.filter
def get_video_id(media):
    if media.conference:
        medias = media.conference.media.all()
        for m in medias:
            if 'video' in m.mime_type:
                return m.id
    return

@register.filter
def get_host(url, host):
    u = urlparse(url)
    if host == '127.0.0.1' or host == 'localhost':
        nu = u.scheme + '://' + host + ':' + str(u.port) + u.path
        return nu
    else:
        return url

@register.filter
def published(doc):
    if doc:
        return doc.filter(is_published=True)

@register.simple_tag
def untreated_scripts_count(user, period):
    Q1 = Q(status=3, author=user, period=period)
    Q2 = Q(status=3, corrector=user, period=period)
    scripts = Script.objects.filter(Q1 | Q2)
    if scripts:
        return ' (' + str(len(scripts)) + ')'
    else:
        return ''

@register.simple_tag
def treated_scripts_count(user, period):
    if not period:
        return ''
    Q1 = Q(status=4, author=user, period=period)
    Q2 = Q(status=4, corrector=user, period=period)
    scripts = Script.objects.filter(Q1 | Q2)
    if scripts:
        return ' (' + str(len(scripts)) + ')'
    else:
        return ''

@register.simple_tag
def get_training_profile(user):
    text = ''
    if user:
        student = user.student.all()
        if student:
            student = student[0]
            if student.platform_only:
                text += 'Internaute - '
            for training in student.trainings.all():
                text += unicode(training) + ' '
    return text

@register.inclusion_tag('teleforma/inc/newsitems_portlet.html', takes_context=True)
def newsitems_portlet(context, course_id, period_id):
    request = context['request']
    user = request.user
    def get_data(newsitem):
        return {
        'id':newsitem.id,
        'title':newsitem.title,
        'text':newsitem.text,
        'creator':newsitem.creator,
        'created':newsitem.created,
        'can_edit':newsitem.can_edit(request),
        'can_delete':newsitem.can_delete(request),
        }
    
    course = get_object_or_404(Course, id=course_id) 
    course_newsitems = [get_data(news) for news in NewsItem.objects.filter(deleted=False, course__id=course_id, period_id=period_id).order_by('-created')[:5]]
    all_newsitems = [get_data(news) for news in NewsItem.objects.filter(deleted=False, period_id=period_id).order_by('-created')[:5]]
    can_add = False 
    if user.is_staff or user.professor.count():
        can_add = True
    return {
            'can_add':can_add,
            'course':course,
            'period_id':period_id,
            'course_newsitems':course_newsitems, 
            'all_newsitems':all_newsitems
           }
