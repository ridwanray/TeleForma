# -*- coding: utf-8 -*-
# Copyright (c) 2012 Parisson SARL

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


from teleforma.views.core import *
from django.utils.translation import ugettext_lazy as _

from forms_builder.forms.forms import FormForForm
from forms_builder.forms.models import Form
from forms_builder.forms.signals import form_invalid, form_valid


def get_seminars(user):
    seminars = []

    if not user.is_authenticated():
        return None

    professor = user.professor.all()
    auditor = user.auditor.all()

    if professor:
        professor = user.professor.get()
        seminars = professor.seminars.all()

    elif auditor:
        auditor = user.pro_auditor.get()
        s_seminars = auditor.seminars.all()

    elif user.is_staff or user.is_superuser:
        seminars = Seminar.objects.all()
    else:
        seminars = None

    return seminars


def seminar_progress(user, seminar):    
    """return the user progress of a seminar in percent
    """

    progress = 0
    total = 0
    
    objects = [seminar.docs_1, seminar.docs_2, seminar.media, seminar.docs_correct]
    for obj in objects:
        for item in obj.all():
            total += item.weight
            if user in item.readers.all():
                progress += item.weight
    
    questions = Question.objects.filter(seminar=seminar, status=3)
    for question in questions:
        total += question.weight
        answer = Answer.objects.filter(question=question, status=3, user=user, validated=True)
        if answer:
            progress += question.weight

    if total != 0:
        return int(progress*100/total)
    else:
        return 0


def total_progress(user):
    """return the user progress of all seminars in percent"""

    progress = 0
    auditor = user.auditor.all()
    if auditor:
        seminars = auditor[0].seminars.all()        
    elif user.is_superuser or user.is_staff:
        seminars = Seminar.objects.all()
    for seminar in seminars:
        progress += seminar_progress(user, seminar)

    if seminars:
        return int(progress/len(seminars))
    else:
        return 0

def seminar_validated(user, seminar):
    validated = []
    for question in seminar.question.all():
        answers = Answer.objects.filter(question= question, user=user, validated=True)
        if answers:
            validated.append(True)
        else:
            validated.append(False)
    return not False in validated


class SeminarView(DetailView):

    model = Seminar
    template_name='teleforma/seminar_detail.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(SeminarView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(SeminarView, self).get_context_data(**kwargs)
        seminar = self.get_object()
        context['all_seminars'] = get_seminars(self.request.user)
        context['seminar_progress'] = seminar_progress(self.request.user, seminar)
        context['total_progress'] = total_progress(self.request.user)
        context['validated'] = seminar_validated(self.request.user, seminar)
        context['evaluation'] = seminar.form
        return context


class SeminarsView(ListView):

    model = Seminar
    template_name='teleforma/seminars.html'

    def get_queryset(self):
        self.seminars = get_seminars(self.request.user)
        return self.seminars

    def get_context_data(self, **kwargs):
        context = super(SeminarsView, self).get_context_data(**kwargs)
        context['all_seminars'] = self.seminars
        context['total_progress'] = total_progress(self.request.user)
        return context

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(SeminarsView, self).dispatch(*args, **kwargs)


class AnswerView(FormView):

    model = Answer
    form_class = AnswerForm
    template_name='teleforma/answer_form.html'

    def get_initial(self):
        initial = {}
        self.question = Question.objects.get(pk=self.kwargs['pk'])
        answers = Answer.objects.filter(user=self.request.user, 
                                        question=self.question).order_by('-date_submitted')
        if answers:
            answer = answers[0]
        else:
            answer = Answer()
        initial['answer'] = answer.answer
        initial['status'] = answer.status
        self.status = answer.status
        return initial

    def form_valid(self, form):
        answer = form.instance
        answer.user = self.request.user
        answer.question = self.question
        answer.save()
        if answer.status <= 2:
            messages.info(self.request, _("You have successfully saved your answer"))
        elif answer.status == 3:
            messages.info(self.request, _("You have successfully submitted your answer"))
        return super(AnswerView, self).form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request,
            "Your submission has not been saved. Try again."
        )
        return super(AnswerView, self).form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super(AnswerView, self).get_context_data(**kwargs)
        context['all_seminars'] = get_seminars(self.request.user)
        context['question'] = self.question
        context['status'] = self.status
        context['seminar'] = self.question.seminar
        context['seminar_progress'] = seminar_progress(self.request.user, self.question.seminar)
        context['total_progress'] = total_progress(self.request.user)
        return context

    def get_success_url(self):
        return reverse('teleforma-seminar-detail', kwargs={'pk':self.question.seminar.id})



class MediaPackageView(DetailView):

    model = MediaPackage

    def get_context_data(self, **kwargs):
        context = super(MediaPackageView, self).get_context_data(**kwargs)
        media_package = self.get_object()
        media_package.readers.add(self.request.user)
        seminar = media_package.seminar.get()
        all_seminars = get_seminars(self.request.user)
        context['all_seminars'] = all_seminars
        context['seminar'] = seminar
        context['media_package'] = media_package
        context['seminar_progress'] = seminar_progress(self.request.user, seminar)
        context['total_progress'] = total_progress(self.request.user)
        return context

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(MediaPackageView, self).dispatch(*args, **kwargs)

    @jsonrpc_method('teleforma.publish_media_package')
    def publish(request, id):
        media_package = MediaPackage.objects.get(id=id)
        media_package.is_published = True
        media_package.save()
        for media in media_package.video.all():
            media.is_published = True
            media.save()
        for media in media_package.audio.all():
            media.is_published = True
            media.save()

    @jsonrpc_method('teleforma.unpublish_media_package')
    def unpublish(request, id):
        media_package = MediaPackage.objects.get(id=id)
        media_package.is_published = False
        media_package.save()
        for media in media_package.video.all():
            media.is_published = False
            media.save()
        for media in media_package.audio.all():
            media.is_published = False
            media.save()

                
class AnswersView(ListView):

    model = Answer
    template_name='teleforma/answers.html'

    def get_queryset(self):
        return Answer.objects.filter(status=3)

    def get_context_data(self, **kwargs):
        context = super(AnswersView, self).get_context_data(**kwargs)
        all_seminars = get_seminars(self.request.user)
        context['all_seminars'] = all_seminars
        
        paginator = Paginator(self.object_list, per_page=12)
        try:
            page = int(self.request.GET.get('page', '1'))
        except ValueError:
            page = 1

        try:
            page = paginator.page(page)
        except (InvalidPage):
            page = paginator.page(paginator.num_pages)
        context['page'] = page
        return context

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(AnswersView, self).dispatch(*args, **kwargs)


    @jsonrpc_method('teleforma.validate_answer')
    def validate(request, id):
        answer = Answer.objects.get(id=id)
        answer.validated = True
        answer.save()

    @jsonrpc_method('teleforma.reject_answer')
    def reject(request, id):
        answer = Answer.objects.get(id=id)
        answer.validated = False
        answer.status = 2
        answer.save()


class AnswerDetailView(DetailView):

    model = Answer
    template_name='teleforma/answer_detail.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(AnswerDetailView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(AnswerDetailView, self).get_context_data(**kwargs)
        context['all_seminars'] = get_seminars(self.request.user)
        return context


class AjaxableResponseMixin(object):
    """
    Mixin to add AJAX support to a form.
    Must be used with an object-based FormView (e.g. CreateView)
    """
    def render_to_json_response(self, context, **response_kwargs):
        data = json.dumps(context)
        response_kwargs['content_type'] = 'application/json'
        return HttpResponse(data, **response_kwargs)

    def form_invalid(self, form):
        if self.request.is_ajax():
            return self.render_to_json_response(form.errors, status=400)
        else:
            return super(AjaxableResponseMixin, self).form_invalid(form)

    def form_valid(self, form):
        if self.request.is_ajax():
            data = {
                'pk': form.instance.pk,
            }
            return self.render_to_json_response(data)
        else:
            return super(AjaxableResponseMixin, self).form_valid(form)


# class EvaluationView(DetailView):

#     model = Seminar
#     template_name='teleforma/evaluation_form.html'

#     def get_context_data(self, **kwargs):
#         context = super(EvaluationView, self).get_context_data(**kwargs)
#         context['all_seminars'] = get_seminars(self.request.user)
#         context['total_progress'] = total_progress(self.request.user)
#         context['form'] = self.get_object().form
#         context['seminar_progress'] = seminar_progress(self.request.user, self.get_object())
#         return context


def evaluation_form_detail(request, pk, template='teleforma/evaluation_form.html'):
    """
    Display a built form and handle submission.
    """
    context = {}
    seminar = Seminar.objects.get(pk=pk)
    published = Form.objects.published(for_user=request.user)
    form = seminar.form
    if form.login_required and not request.user.is_authenticated():
        return redirect("%s?%s=%s" % (settings.LOGIN_URL, REDIRECT_FIELD_NAME,
                        urlquote(request.get_full_path())))
    request_context = RequestContext(request)
    args = (form, request_context, request.POST or None, request.FILES or None)
    form_for_form = FormForForm(*args)
    if request.method == "POST":
        if not form_for_form.is_valid():
            form_invalid.send(sender=request, form=form_for_form)
        else:
            entry = form_for_form.save()
            form_valid.send(sender=request, form=form_for_form, entry=entry)
        return redirect('teleforma-seminar-detail', seminar.id)

    context['seminar'] = seminar
    context['all_seminars'] = get_seminars(request.user)
    context['total_progress'] = total_progress(request.user)
    context['form'] = form
    context['seminar_progress'] = seminar_progress(request.user, seminar)
    
    return render_to_response(template, context, request_context)


# Testimonials

def fetch_resources(uri, rel):
    """
    Callback to allow xhtml2pdf/reportlab to retrieve Images,Stylesheets, etc.
    `uri` is the href attribute from the html link element.
    `rel` gives a relative path, but it's not used here.

    """
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT,
                            uri.replace(settings.MEDIA_URL, ""))
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT,
                            uri.replace(settings.STATIC_URL, ""))
    else:
        path = os.path.join(settings.STATIC_ROOT,
                            uri.replace(settings.STATIC_URL, ""))

        if not os.path.isfile(path):
            path = os.path.join(settings.MEDIA_ROOT,
                                uri.replace(settings.MEDIA_URL, ""))

            if not os.path.isfile(path):
                raise UnsupportedMediaPathException(
                                    'media urls must start with %s or %s' % (
                                    settings.MEDIA_ROOT, settings.STATIC_ROOT))

    return path


def render_to_pdf(template_src, context_dict):
    """Function to render html template into a pdf file"""
    template = get_template(template_src)
    context = Context(context_dict)
    html = template.render(context)
    result = StringIO.StringIO()

    pdf = pisa.pisaDocument(StringIO.StringIO(html.encode("UTF-8")),
                                            dest=result,
                                            encoding='UTF-8',
                                            link_callback=fetch_resources)
    if not pdf.err:
        response = HttpResponse(result.getvalue(),
                                                    mimetype='application/pdf')

        return response

    return HttpResponse('We had some errors<pre>%s</pre>' % escape(html))


def download_pdf(request):
    """Build briefing packages format and export as HTML and PDF."""
    response = HttpResponse(content_type='application/pdf')
    return generate_pdf('app/test.html', file_object=response)