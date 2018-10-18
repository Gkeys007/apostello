from time import sleep

import pytest
import vcr
from tests.functional_tests.utils import check_and_close_msg, click_and_wait

from elvanto.models import ElvantoGroup

my_vcr = vcr.VCR(record_mode="none", ignore_localhost=True)


@pytest.mark.django_db
@pytest.mark.slow
@pytest.mark.selenium
@pytest.mark.parametrize("uri", ["/elvanto/import/"])
class TestElvantoImport:
    @my_vcr.use_cassette("tests/fixtures/vcr_cass/elv.yaml", filter_headers=["authorization"])
    def test_page_load(self, uri, live_server, browser_in, driver_wait_time):
        """Test page loads and table renders."""
        # load groups
        ElvantoGroup.fetch_all_groups()
        # load page
        browser_in.get(live_server + uri)
        assert uri in browser_in.current_url
        # check table is there
        sleep(driver_wait_time)
        tables = browser_in.find_elements_by_xpath("//table")
        assert len(tables) == 1
        table = tables[0]
        assert "Geneva" in table.text
        assert "Scotland" in table.text
        assert "Disabled" in table.text

    @my_vcr.use_cassette("tests/fixtures/vcr_cass/elv.yaml", filter_headers=["authorization"])
    def test_pull_groups(self, uri, live_server, browser_in, driver_wait_time):
        """Test toggle syncing of a group and then pull groups."""
        # load groups
        ElvantoGroup.fetch_all_groups()
        # load page
        browser_in.get(live_server + uri)
        assert uri in browser_in.current_url
        # enable a group
        sleep(driver_wait_time)
        group_button = browser_in.find_element_by_id("elvantoGroupButton")
        click_and_wait(group_button, driver_wait_time)
        table = browser_in.find_elements_by_xpath("//table")[0]
        assert "Syncing" in table.text
        # pull groups
        browser_in.get(live_server + uri)
        assert uri in browser_in.current_url
        sleep(driver_wait_time)
        pull_button = browser_in.find_elements_by_id("pull_button")[0]
        pull_button.click()
        check_and_close_msg(browser_in, driver_wait_time)

    @my_vcr.use_cassette("tests/fixtures/vcr_cass/elv.yaml", filter_headers=["authorization"])
    def test_fetch_groups(self, uri, live_server, browser_in, driver_wait_time):
        "Test fetch group button." ""
        # fetch groups
        browser_in.get(live_server + uri)
        fetch_button = browser_in.find_element_by_id("fetch_button")
        click_and_wait(fetch_button, driver_wait_time)
        check_and_close_msg(browser_in, driver_wait_time)
