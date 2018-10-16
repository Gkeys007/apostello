from time import sleep

import pytest
from tests.functional_tests.utils import assert_with_timeout, click_and_wait, load_page

from apostello import models

NEW_URI = '/recipient/new/'
DEFAULT_NUM = '+447777777771'


def send_form(b, wt):
    send_button = b.find_element_by_id('formSubmitButton')
    send_button.click()
    return b


def add_first_name(b, wt, name='first'):
    field = b.find_element_by_name('first_name')
    field.clear()
    field.send_keys(name)
    sleep(wt)
    return b


def add_last_name(b, wt, name='last'):
    field = b.find_element_by_name('last_name')
    field.clear()
    field.send_keys(name)
    sleep(wt)
    return b


def add_number(b, wt, num=DEFAULT_NUM):
    field = b.find_element_by_name('number')
    field.clear()
    field.send_keys(num)
    sleep(wt)
    return b


def tick_never_contact(b, wt):
    field = b.find_element_by_name('never_contact')
    field.click()
    sleep(wt)
    return b


@pytest.mark.slow
@pytest.mark.selenium
class TestContactForm:
    def test_create_new_contact(self, live_server, browser_in, recipients, users, driver_wait_time):
        """Test good form submission."""
        assert len(recipients) == models.Recipient.objects.count()
        b = load_page(browser_in, driver_wait_time, live_server + NEW_URI)
        b = add_first_name(b, driver_wait_time)
        b = add_last_name(b, driver_wait_time)
        b = add_number(b, driver_wait_time)
        b = send_form(b, driver_wait_time)

        def _test():
            assert len(recipients) + 1 == models.Recipient.objects.count()
            assert '/recipient/all/' in b.current_url

        assert_with_timeout(_test, 10 * driver_wait_time)

    def test_edit_contact(self, live_server, browser_in, recipients, users, driver_wait_time):
        assert len(recipients) == models.Recipient.objects.count()
        b = load_page(browser_in, driver_wait_time, live_server + '/recipient/edit/{}/'.format(recipients['calvin'].pk))
        b = add_first_name(b, driver_wait_time)
        b = add_last_name(b, driver_wait_time)
        b = tick_never_contact(b, driver_wait_time)
        b = send_form(b, driver_wait_time)

        def _test():
            assert len(recipients) == models.Recipient.objects.count()
            assert '/recipient/all/' in b.current_url
            assert 'first' in b.page_source
            assert 'last' in b.page_source
            r = models.Recipient.objects.get(pk=recipients['calvin'].pk)
            assert str(r.number) == str(recipients['calvin'].number)
            assert (r.never_contact)

        assert_with_timeout(_test, 10 * driver_wait_time)

    def test_create_existing_contact(self, live_server, browser_in, recipients, users, driver_wait_time):
        b = load_page(browser_in, driver_wait_time, live_server + NEW_URI)
        b = add_first_name(b, driver_wait_time)
        b = add_last_name(b, driver_wait_time)
        b = add_number(b, driver_wait_time, num=str(recipients['calvin'].number))
        b = send_form(b, driver_wait_time)

        def _test():
            assert '/recipient/new/' in b.current_url
            assert 'recipient with this number already exists' in b.page_source.lower()
            assert len(recipients) == models.Recipient.objects.count()

        assert_with_timeout(_test, 10 * driver_wait_time)

    def test_create_existing_archived_contact(self, live_server, browser_in, recipients, users, driver_wait_time):
        self.test_create_new_contact(live_server, browser_in, recipients, users, driver_wait_time)
        for g in models.Recipient.objects.all():
            g.is_archived = True
            g.save()
        b = load_page(browser_in, driver_wait_time, live_server + NEW_URI)
        b = add_first_name(b, driver_wait_time)
        b = add_last_name(b, driver_wait_time)
        b = add_number(b, driver_wait_time)

        def _test():
            assert '/recipient/new/' in b.current_url
            assert 'There is already a Contact that with that number in the archive'.lower() in b.page_source.lower()
            assert 'You can restore the contact here:'.lower() in b.page_source.lower()

        assert_with_timeout(_test, 10 * driver_wait_time)
