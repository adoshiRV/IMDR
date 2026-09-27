"""Unit tests for the shared RBI DBIE SAP-BO scraping scaffolding
(`imdr.domains.econ.rbi_dbie_sapbo`).

No network calls, no DB writes, no headed Chrome -- `scrape_iframe_table`
is tested against fake page/frame objects that mimic the Playwright
`Frame` surface (`.name`, `.url`, `.evaluate`) it actually uses.
"""
from __future__ import annotations

from imdr.domains.econ import rbi_dbie_sapbo as sapbo


class _FakeFrame:
    def __init__(self, name: str = "", url: str = "", result=None):
        self.name = name
        self.url = url
        self._result = result if result is not None else []
        self.evaluated = False

    def evaluate(self, script: str):
        self.evaluated = True
        return self._result


class _FakePage:
    def __init__(self, frames):
        self.frames = frames


# ---------------------------------------------------------------------------
# is_login_wall
# ---------------------------------------------------------------------------

class TestIsLoginWall:
    def test_true_when_ui5logon_jsp_present(self):
        assert sapbo.is_login_wall(
            "https://data.rbi.org.in/DBIE/opendoc/UI5logon.jsp?x=1"
        ) is True

    def test_false_for_normal_sap_bo_url(self):
        assert sapbo.is_login_wall(
            "https://data.rbi.org.in/DBIE/opendoc/openDocument.jsp"
        ) is False

    def test_false_for_dbie_home(self):
        assert sapbo.is_login_wall("https://data.rbi.org.in/DBIE/#/dbie/home") is False

    def test_false_for_empty_string(self):
        assert sapbo.is_login_wall("") is False

    def test_false_for_none(self):
        assert sapbo.is_login_wall(None) is False


# ---------------------------------------------------------------------------
# scrape_iframe_table — frame selection
# ---------------------------------------------------------------------------

class TestScrapeIframeTableFrameSelection:
    def test_no_matching_frame_returns_empty_list(self):
        page = _FakePage([_FakeFrame(name="main", url="https://x")])
        assert sapbo.scrape_iframe_table(page) == []

    def test_matches_by_open_doc_child_frame_name(self):
        target = _FakeFrame(name="openDocChildFrame1", url="https://x",
                             result=[["a", "b"]])
        page = _FakePage([_FakeFrame(name="main", url="https://x"), target])
        rows = sapbo.scrape_iframe_table(page)
        assert rows == [["a", "b"]]
        assert target.evaluated is True

    def test_matches_by_webiview_url(self):
        target = _FakeFrame(name="", url="https://x/WebiView/abc",
                             result=[["c", "d"]])
        page = _FakePage([target])
        assert sapbo.scrape_iframe_table(page) == [["c", "d"]]

    def test_no_frames_returns_empty_list(self):
        page = _FakePage([])
        assert sapbo.scrape_iframe_table(page) == []

    def test_picks_first_matching_frame(self):
        first = _FakeFrame(name="openDocChildFrame1", url="https://x",
                            result=[["first"]])
        second = _FakeFrame(name="openDocChildFrame2", url="https://x",
                             result=[["second"]])
        page = _FakePage([first, second])
        rows = sapbo.scrape_iframe_table(page)
        assert rows == [["first"]]
        assert first.evaluated is True
        assert second.evaluated is False


# ---------------------------------------------------------------------------
# profile_dir / constants
# ---------------------------------------------------------------------------

class TestProfileDir:
    def test_path_shape(self):
        p = sapbo.profile_dir()
        assert p.name == "_profile_dbie"
        assert p.parent.name == "rbi"

    def test_directory_is_created(self):
        p = sapbo.profile_dir()
        assert p.exists()
        assert p.is_dir()

    def test_idempotent(self):
        p1 = sapbo.profile_dir()
        p2 = sapbo.profile_dir()
        assert p1 == p2


class TestConstants:
    def test_dbie_home_url(self):
        assert sapbo.DBIE_HOME_URL == "https://data.rbi.org.in/DBIE/#/dbie/home"


# ---------------------------------------------------------------------------
# dismiss_modal
# ---------------------------------------------------------------------------
#
# A stale DBIE session greets the next run with a timeout/logout popup whose
# backdrop swallows every click, so the search box never receives the term and
# Playwright retries until it times out -- three full attempts and an empty
# result that reads as a scraping failure rather than a dialog. Observed live
# 2026-09-15. These fakes mimic only the Locator surface the function uses.

class _FakeLocator:
    def __init__(self, count: int = 1, visible: bool = True, click_raises=None):
        self._count = count
        self._visible = visible
        self._click_raises = click_raises
        self.clicked = False

    # `.first` on a Playwright Locator returns a Locator
    @property
    def first(self):
        return self

    def count(self):
        return self._count

    def is_visible(self):
        return self._visible

    def click(self, timeout=None):
        if self._click_raises is not None:
            raise self._click_raises
        self.clicked = True


class _FakeKeyboard:
    def __init__(self):
        self.pressed = []

    def press(self, key):
        self.pressed.append(key)


class _FakeModalPage:
    """`locator(sel)` returns whatever the selector map says, else empty."""

    def __init__(self, locators: dict):
        self._locators = locators
        self.keyboard = _FakeKeyboard()
        self.waited_ms = 0

    def locator(self, selector):
        return self._locators.get(selector, _FakeLocator(count=0, visible=False))

    def wait_for_timeout(self, ms):
        self.waited_ms += ms


class TestDismissModal:
    def test_no_modal_present_is_a_no_op(self):
        page = _FakeModalPage({})
        assert sapbo.dismiss_modal(page) is False
        assert page.keyboard.pressed == []

    def test_modal_present_but_not_visible_is_a_no_op(self):
        page = _FakeModalPage({"app-modal": _FakeLocator(count=1, visible=False)})
        assert sapbo.dismiss_modal(page) is False

    def test_closes_via_the_close_button(self):
        close = _FakeLocator()
        page = _FakeModalPage({
            "app-modal": _FakeLocator(),
            "app-modal button.close": close,
        })
        assert sapbo.dismiss_modal(page) is True
        assert close.clicked is True

    def test_falls_back_through_the_selector_chain(self):
        """The close control is not always `button.close`."""
        generic = _FakeLocator()
        page = _FakeModalPage({
            "app-modal": _FakeLocator(),
            "app-modal button.close": _FakeLocator(count=0),
            "app-modal .modal-header button": _FakeLocator(count=0),
            "app-modal button": generic,
        })
        assert sapbo.dismiss_modal(page) is True
        assert generic.clicked is True

    def test_a_click_that_raises_moves_on_to_the_next_selector(self):
        generic = _FakeLocator()
        page = _FakeModalPage({
            "app-modal": _FakeLocator(),
            "app-modal button.close": _FakeLocator(
                click_raises=RuntimeError("intercepted")),
            "app-modal button": generic,
        })
        assert sapbo.dismiss_modal(page) is True
        assert generic.clicked is True

    def test_no_usable_close_control_presses_escape_rather_than_giving_up(self):
        """Better to try Escape than let the backdrop eat the whole run."""
        page = _FakeModalPage({"app-modal": _FakeLocator()})
        # every close selector missing -> falls through to Escape
        assert sapbo.dismiss_modal(page) is False
        assert page.keyboard.pressed == ["Escape"]

    def test_a_page_that_raises_on_locator_is_survived(self):
        class _Hostile:
            def locator(self, selector):
                raise RuntimeError("page closed")
        assert sapbo.dismiss_modal(_Hostile()) is False
