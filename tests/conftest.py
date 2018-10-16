import json
import os
from datetime import datetime

import pytest
import vcr
from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from django.utils.timezone import get_current_timezone
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

from apostello.models import *
from site_config.models import SiteConfiguration


@pytest.fixture(autouse=True)
def short_circuit_q(monkeypatch):
    def new_async(func, *args, **kwargs):
        # pull django_q kwargs out:
        schedule_kwargs = ['name', 'hook', 'schedule_type', 'minutes', 'repeats', 'next_run']
        async_kwargs = [
            'hook', 'group', 'save', 'sync', 'cached', 'iter_count', 'iter_cached', 'chain', 'broker', 'q_options'
        ]
        for k in schedule_kwargs + async_kwargs:
            kwargs.pop(k, None)
        f = func
        if not callable(func):
            try:
                import importlib
                module, func = f.rsplit('.', 1)
                m = importlib.import_module(module)
                f = getattr(m, func)
            except (ValueError, ImportError, AttributeError) as e:
                result = (e, False)
        result = f(*args, **kwargs)

        return result

    monkeypatch.setattr('django_q.tasks.async_task.__code__', new_async.__code__)
    monkeypatch.setattr('django_q.tasks.schedule.__code__', new_async.__code__)


@pytest.fixture
def recipients():
    """Create a bunch of recipients for testing."""
    calvin = Recipient.objects.create(first_name="John", last_name="Calvin", number='+447927401749')
    house_lamp = Recipient.objects.create(first_name="Johannes", last_name="Oecolampadius", number='+447927401740')
    knox = Recipient.objects.create(first_name="John", last_name="Knox", number='+447928401745', is_archived=True)
    wesley = Recipient.objects.create(first_name="John", last_name="Wesley", number='+447927401745', is_blocking=True)
    john_owen = Recipient.objects.create(
        first_name="John", last_name="Owen", number='+15005550004'
    )  # blacklisted magic num
    thomas_chalmers = Recipient.objects.create(
        first_name="Thomas", last_name="Chalmers", number='+15005550009'
    )  # can't recieve
    beza = Recipient.objects.create(first_name="Theodore", last_name="Beza", number='+447927411115', do_not_reply=True)
    unknown = Recipient.objects.create(first_name="Unknown", last_name="Person", number='+447097565645')

    objs = {
        'calvin': calvin,
        'house_lamp': house_lamp,
        'knox': knox,
        'wesley': wesley,
        'john_owen': john_owen,
        'thomas_chalmers': thomas_chalmers,
        'beza': beza,
        'unknown': unknown,
    }
    return objs


@pytest.mark.usefixtures("recipients")
@pytest.fixture
def groups(recipients):
    """Create some groups with recipients."""
    test_group = RecipientGroup.objects.create(
        name="Test Group",
        description="This is a test group",
    )
    archived_group = RecipientGroup.objects.create(
        name="Archived Group", description="This is a test group", is_archived=True
    )
    archived_group.save()
    empty_group = RecipientGroup.objects.create(name="Empty Group", description="This is an empty group")
    empty_group.save()

    test_group.recipient_set.add(recipients['calvin'])
    test_group.recipient_set.add(recipients['house_lamp'])
    test_group.save()
    objs = {
        'test_group': test_group,
        'empty_group': empty_group,
        'archived_group': archived_group,
    }
    return objs


@pytest.fixture
@pytest.mark.usefixtures("recipients", "groups")
def smsout(recipients, groups):
    """Create a single outbound message."""
    smsout = SmsOutbound.objects.create(
        sid='123456',
        content='test',
        sent_by='test',
        recipient_group=groups['test_group'],
        recipient=recipients['calvin']
    )

    objs = {'smsout': smsout}
    return objs


@pytest.fixture
def keywords():
    """Create various keywords for testing different options."""
    # keywords:
    test = Keyword.objects.create(
        keyword="test",
        description="This is an active test keyword with custom response",
        custom_response="Test custom response with %name%",
        custom_response_new_person="Thanks new person!",
        activate_time=timezone.make_aware(
            datetime.strptime('Jun 1 1970  1:33PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        ),
        deactivate_time=timezone.make_aware(
            datetime.strptime('Jun 1 2400  1:33PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        )
    )
    test.save()
    # active with custom response
    test2 = Keyword.objects.create(
        keyword="2test",
        description="This is an active test keyword with no custom response",
        custom_response="",
        activate_time=timezone.make_aware(
            datetime.strptime('Jun 1 1970  1:33PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        ),
        deactivate_time=timezone.make_aware(
            datetime.strptime('Jun 1 2400  1:33PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        )
    )
    test2.save()
    # active with custom response
    test_expired = Keyword.objects.create(
        keyword="expired_test",
        description="This is an expired test keyword with no custom response",
        custom_response="",
        activate_time=timezone.make_aware(
            datetime.strptime('Jun 1 1970  1:33PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        ),
        deactivate_time=timezone.make_aware(
            datetime.strptime('Jun 1 1975  1:33PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        )
    )
    test_expired.save()
    # not yet active with custom response
    test_early = Keyword.objects.create(
        keyword="early_test",
        description="This is a not yet active test keyword "
        "with no custom response",
        custom_response="",
        activate_time=timezone.make_aware(
            datetime.strptime('Jun 1 2400  1:33PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        ),
        deactivate_time=timezone.make_aware(
            datetime.strptime('Jun 1 2400  1:35PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        )
    )
    test_early.save()

    test_no_end = Keyword.objects.create(
        keyword="no_end",
        description="This has no end",
        custom_response="Will always reply",
        activate_time=timezone.make_aware(
            datetime.strptime('Jun 1 1400  1:33PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        )
    )
    test_no_end.save()
    # test deactivated response
    test_deac_resp_fail = Keyword.objects.create(
        keyword="cust_endf",
        description="This has a diff reply",
        custom_response="Hi!",
        deactivated_response="Too slow, Joe!",
        activate_time=timezone.make_aware(
            datetime.strptime('Jun 1 1400  1:33PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        )
    )

    test_deac_resp = Keyword.objects.create(
        keyword="just_in_time",
        description="This has a diff reply",
        custom_response="Just in time!",
        deactivated_response="Too slow, Joe!",
        deactivate_time=timezone.make_aware(
            datetime.strptime('Jun 1 1400  2:33PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        ),
        activate_time=timezone.make_aware(
            datetime.strptime('Jun 1 1400  1:33PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        )
    )
    test_no_end.save()

    test_early_with_response = Keyword.objects.create(
        keyword="22early",
        description="This is a not yet active test keyword"
        "with a custom response",
        too_early_response="This is far too early",
        activate_time=timezone.make_aware(
            datetime.strptime('Jun 1 2400  1:33PM', '%b %d %Y %I:%M%p'), get_current_timezone()
        ),
    )
    test_early.save()

    test_do_not_reply = Keyword.objects.create(
        keyword='donotreply',
        disable_all_replies=True,
    )
    test_do_not_reply.save()

    keywords = {
        'test': test,
        'test2': test2,
        'test_expired': test_expired,
        'test_early': test_early,
        'test_no_end': test_no_end,
        'test_deac_resp': test_deac_resp,
        'test_deac_resp_fail': test_deac_resp_fail,
        'test_early_with_response': test_early_with_response,
        'test_do_not_reply': test_do_not_reply,
    }
    return keywords


@pytest.fixture
def smsin():
    """Create some messages."""
    sms1 = SmsInbound.objects.create(
        content='test message',
        time_received=timezone.now(),
        sender_name="John Calvin",
        sender_num="+447927401749",
        matched_keyword="test",
        sid='12345'
    )
    sms1.save()
    sms3 = SmsInbound.objects.create(
        content='test message',
        time_received=timezone.now(),
        sender_name="John Calvin",
        sender_num="+447927401749",
        matched_keyword="test",
        sid='123456789'
    )
    sms3.save()
    sms2 = SmsInbound.objects.create(
        content='archived message',
        time_received=timezone.now(),
        sender_name="John Calvin",
        sender_num="+447927401749",
        matched_keyword="test",
        sid='123456789a',
        is_archived=True
    )
    sms2.save()
    objs = {'sms1': sms1, 'sms2': sms2, 'sms3': sms3}
    return objs


@pytest.mark.usefixtures("recipients", "keywords")
@pytest.fixture()
def users(recipients, keywords):
    """Create apostello users."""
    user = User.objects.create_user(username='test', email='test@example.com', password='top_secret')
    user.profile.save()
    user.is_staff = True
    user.save()
    allauth_email = EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
    allauth_email.save()
    p = UserProfile.objects.get(user=user)
    p.approved = True
    p.can_send_sms = True
    p.can_see_contact_nums = True
    p.can_import = True
    p.save()

    c = Client()
    c.login(username='test', password='top_secret')

    user2 = User.objects.create_user(username='test2', email='test2@example.com', password='top2_secret')
    user2.save()
    user2.profile.save()
    p = UserProfile.objects.get(user=user2)
    p.approved = True
    p.save()
    allauth_email = EmailAddress.objects.create(user=user2, email=user2.email, primary=True, verified=True)
    allauth_email.save()
    keywords['test'].owners.add(user2)

    user3 = User.objects.create_user(username='test3', email='test3@example.com', password='top2_secret')
    user3.save()
    user3.profile.save()
    p = UserProfile.objects.get(user=user3)
    p.approved = True
    p.save()
    user3.profile.approved = True
    user3.profile.save()
    allauth_email = EmailAddress.objects.create(user=user3, email=user3.email, primary=True, verified=True)
    allauth_email.save()

    c2 = Client()
    c2.login(username='test3', password='top2_secret')
    c_out = Client()

    objs = {'staff': user, 'notstaff': user2, 'notstaff2': user3, 'c_staff': c, 'c_in': c2, 'c_out': c_out}

    return objs


@pytest.fixture(scope='session')
def driver_wait_time():
    """Read web driver implicit wait time from env var. Defaults to 1s.

    If selenium tests are failing, try setting the env var to a higher value,
    e.g. 10.
    """
    return int(os.environ.get('SELENIUM_IMPLICIT_WAIT', 1))


def create_browser(request, driver_wait_time, tries=0):
    """This sometimes fails to start firefox on CI, so we retry..."""
    max_tries = 5
    options = Options()
    options.add_argument('-headless')
    try:
        driver = webdriver.Firefox(firefox_options=options)
        driver.implicitly_wait(driver_wait_time)
        driver.set_window_size(1200, 1800)

        request.node._driver = driver
        return driver
    except Exception as e:
        if tries < max_tries:
            return create_browser(request, driver_wait_time, tries=tries + 1)
        else:
            raise e


@pytest.fixture(scope='session')
def browser(request, driver_wait_time):
    """Setup selenium browser."""
    driver = create_browser(request, driver_wait_time)
    yield driver
    driver.quit()


@pytest.mark.usefixtures('users', 'live_server')
@pytest.yield_fixture()
def browser_in(request, live_server, users, driver_wait_time):
    """Setup selenium browser and log in."""
    driver = create_browser(request, driver_wait_time)
    driver.get(live_server + '/')
    driver.add_cookie(
        {
            u'name': u'sessionid',
            u'value': users['c_staff'].session.session_key,
            u'path': u'/',
            u'httponly': True,
            u'secure': False
        }
    )
    request.node._driver = driver
    yield driver
    driver.quit()


@pytest.mark.usefixtures('users', 'live_server')
@pytest.yield_fixture()
def browser_in_not_staff(request, live_server, users, driver_wait_time):
    """Setup selenium browser and log in."""
    driver = create_browser(request, driver_wait_time)
    driver.get(live_server + '/')
    driver.add_cookie(
        {
            u'name': u'sessionid',
            u'value': users['c_in'].session.session_key,
            u'path': u'/',
            u'httponly': True,
            u'secure': False
        }
    )
    request.node._driver = driver
    yield driver
    driver.quit()


@pytest.fixture()
def setup_twilio():
    config = SiteConfiguration.get_solo()
    config.twilio_account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    config.twilio_auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    config.twilio_from_num = os.environ.get('TWILIO_FROM_NUM')
    try:
        cost = float(os.environ.get('TWILIO_SENDING_COST'))
    except TypeError:
        cost = None
    config.twilio_sending_cost = cost
    config.save()


@pytest.mark.hookwrapper
def pytest_runtest_makereport(item, call):
    pytest_html = item.config.pluginmanager.getplugin('html')
    outcome = yield
    report = outcome.get_result()
    extra = getattr(report, 'extra', [])
    if report.when == 'call':
        xfail = hasattr(report, 'wasxfail')
        if (report.skipped and xfail) or (report.failed and not xfail):
            driver = getattr(item, '_driver', None)
            if driver is not None:
                extra.append(pytest_html.extras.image(driver.get_screenshot_as_base64(), 'Screenshot'))
        report.extra = extra


base_vcr = vcr.VCR(record_mode='none', ignore_localhost=True)
twilio_vcr = base_vcr.use_cassette(
    'tests/fixtures/vcr_cass/twilio.yaml',
    filter_headers=['authorization'],
    match_on=['method', 'scheme', 'host', 'port', 'path', 'query', 'body']
)
elvanto_vcr = base_vcr.use_cassette(
    'tests/fixtures/vcr_cass/elv.yaml',
    filter_headers=['authorization'],
)
onebody_vcr = base_vcr.use_cassette(
    'tests/fixtures/vcr_cass/onebody.yaml',
    filter_headers=['authorization'],
    ignore_localhost=False,
)
onebody_no_csv_vcr = base_vcr.use_cassette(
    'tests/fixtures/vcr_cass/onebody_no_csv.yaml',
    filter_headers=['authorization'],
    ignore_localhost=False,
)


def post_json(client, url, data):
    return client.post(
        url,
        json.dumps(data),
        content_type="application/json",
    )


MAX_RUNS = int(os.environ.get('FLAKY_RUNS', 5))
